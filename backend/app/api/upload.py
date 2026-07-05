# -*- coding: utf-8 -*-
"""
文件上传与解析接口
POST /api/upload
GET  /api/documents/{id}/status
GET  /api/documents/{id}/report
DELETE /api/documents/{id}
POST /api/documents/{id}/reparse
"""

import os
import time
import hashlib
import logging
import threading
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db, Document, Course, Chapter, Fragment, KnowledgePoint, ParseTask, gen_id, now
from ..core.exceptions import FileTooLargeError, UnsupportedFileType, NotFoundError
from ..schemas.common import SuccessResponse, ErrorResponse
from ..rag.bridge import parse_service, rag_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── 辅助 ────────────────────────────────────────────────────

def _file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _guess_kp_type(line: str) -> str:
    """从知识点文本推断类型"""
    if line.startswith("定理") or line.startswith("引理") or line.startswith("推论"):
        return "theorem"
    if line.startswith("定义"):
        return "concept"
    if line.startswith("性质"):
        return "property"
    if line.startswith("命题"):
        return "proposition"
    return "concept"


def _update_doc_status(db: Session, doc_id: str, status: str, **kwargs):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        doc.parse_status = status
        doc.updated_at = now()
        for k, v in kwargs.items():
            if hasattr(doc, k):
                setattr(doc, k, v)
        db.commit()


def _background_parse(doc_id: str, file_path: str, course_id: str):
    """后台异步解析任务"""
    from ..core.database import SessionLocal
    db = SessionLocal()
    start = time.time()
    try:
        _update_doc_status(db, doc_id, "parsing")
        logger.info(f"开始解析文档: {doc_id}")

        # 1. 文档解析
        _update_doc_status(db, doc_id, "parsing")
        result = parse_service.parse(file_path)

        if result["error"]:
            raise Exception(result["error"])

        _update_doc_status(db, doc_id, "chunking")

        # 2. 将章节存入 DB，并记录 chapter_id 列表
        chapter_ids: list = []
        for i, ch_name in enumerate(result["chapters"][:50]):
            ch = Chapter(
                id=gen_id(),
                course_id=course_id,
                document_id=doc_id,
                chapter_name=ch_name[:255],
                order_index=i,
            )
            db.add(ch)
            chapter_ids.append(ch.id)
        db.commit()

        # 3a. 将知识点存入 knowledge_points 表
        kp_lines = result.get("knowledge_points", [])
        if kp_lines:
            # 若没有识别出章节，自动补一个"通用章节"作为载体
            if not chapter_ids:
                fallback_ch = Chapter(
                    id=gen_id(),
                    course_id=course_id,
                    document_id=doc_id,
                    chapter_name="文档知识点",
                    order_index=0,
                )
                db.add(fallback_ch)
                db.commit()
                chapter_ids.append(fallback_ch.id)

            # 将知识点均匀分配到各章节
            total_ch = len(chapter_ids)
            for idx, kp_line in enumerate(kp_lines[:100]):
                assigned_chapter_id = chapter_ids[idx % total_ch]
                kp = KnowledgePoint(
                    id=gen_id(),
                    chapter_id=assigned_chapter_id,
                    course_id=course_id,
                    name=kp_line[:256],
                    definition=kp_line,
                    kp_type=_guess_kp_type(kp_line),
                )
                db.add(kp)
            db.commit()
            logger.info(f"✅ 保存知识点 {len(kp_lines)} 条: {doc_id}")

        # 3b. 简单分块存入 Fragment
        text = result["text"]
        chunk_size = 800
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        for chunk in chunks:
            if chunk.strip():
                frag = Fragment(
                    id=gen_id(),
                    document_id=doc_id,
                    course_id=course_id,
                    text=chunk,
                    from_ocr=result["from_ocr"],
                )
                db.add(frag)
        db.commit()

        _update_doc_status(db, doc_id, "embedding")

        # 4. 向量化（调用 1号模块）
        vec_count = rag_service.index_document(course_id, file_path, force=False)

        elapsed = round(time.time() - start, 2)
        _update_doc_status(
            db, doc_id, "completed",
            total_pages=result["pages"],
            parsed_pages=result["pages"],
            ocr_pages=1 if result["from_ocr"] else 0,
            total_chars=result["total_chars"],
            chapter_count=len(result["chapters"]),
            kp_count=len(result["knowledge_points"]),
            formula_count=len(result["formulas"]),
            example_count=len(result["examples"]),
            exercise_count=len(result["exercises"]),
            chunk_count=len(chunks),
            vector_count=vec_count or len(chunks),
            parse_seconds=elapsed,
        )
        logger.info(f"✅ 文档解析完成: {doc_id}  耗时: {elapsed}s")

    except Exception as e:
        logger.error(f"文档解析失败: {doc_id}  {e}", exc_info=True)
        _update_doc_status(db, doc_id, "failed", parse_error=str(e)[:500])
    finally:
        db.close()


# ─── 接口 ────────────────────────────────────────────────────

@router.post("/upload", summary="上传文档")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    course_id: str = Form(default=""),
    course_name: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """
    上传 PDF/Word/PPT 等文档，触发后台异步解析建库流程。
    返回 document_id 和 task_id，前端可轮询 /documents/{id}/status。
    """
    # ── 校验文件类型 ──────────────────────────
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(ext)

    # ── 读取并校验大小 ────────────────────────
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise FileTooLargeError()

    # ── 确保课程存在 ──────────────────────────
    if not course_id:
        from ..core.database import Course as CourseModel
        cname = course_name or Path(file.filename).stem
        course = CourseModel(id=gen_id(), name=cname)
        db.add(course)
        db.commit()
        course_id = course.id
    else:
        from ..core.database import Course as CourseModel
        if not db.query(CourseModel).filter(CourseModel.id == course_id).first():
            cname = course_name or "未命名课程"
            course = CourseModel(id=gen_id(), name=cname)
            db.add(course)
            db.commit()
            course_id = course.id

    # ── 保存文件 ──────────────────────────────
    save_path = settings.UPLOAD_DIR / f"{gen_id()}{ext}"
    with open(save_path, "wb") as f:
        f.write(content)

    md5 = _file_md5(str(save_path))

    # ── 创建 Document 记录 ────────────────────
    doc = Document(
        id=gen_id(),
        course_id=course_id,
        file_name=file.filename,
        file_type=ext.lstrip("."),
        file_path=str(save_path),
        file_size=len(content),
        file_md5=md5,
        parse_status="uploaded",
    )
    db.add(doc)
    db.commit()

    # ── 启动后台解析 ──────────────────────────
    background_tasks.add_task(_background_parse, doc.id, str(save_path), course_id)

    return {
        "success": True,
        "document_id": doc.id,
        "course_id": course_id,
        "file_name": file.filename,
        "file_size": len(content),
        "parse_status": "parsing",
        "message": "文件已上传，正在后台解析，请轮询 /api/documents/{id}/status 查看进度",
    }


@router.get("/documents/{doc_id}/status", summary="查询解析状态")
def get_parse_status(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise NotFoundError("文档")

    status_labels = {
        "uploaded": "已上传",
        "parsing": "文本解析中",
        "ocr_processing": "OCR 识别中",
        "chunking": "分块处理中",
        "embedding": "向量化中",
        "indexed": "索引完成",
        "completed": "全部完成",
        "failed": "解析失败",
    }

    return {
        "success": True,
        "document_id": doc_id,
        "file_name": doc.file_name,
        "parse_status": doc.parse_status,
        "status_label": status_labels.get(doc.parse_status, doc.parse_status),
        "error": doc.parse_error,
    }


@router.get("/documents/{doc_id}/report", summary="获取解析报告")
def get_parse_report(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise NotFoundError("文档")

    chapters = db.query(Chapter).filter(Chapter.document_id == doc_id).all()

    return {
        "success": True,
        "report": {
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "parse_status": doc.parse_status,
            "total_pages": doc.total_pages,
            "parsed_pages": doc.parsed_pages,
            "ocr_pages": doc.ocr_pages,
            "failed_pages": doc.failed_pages,
            "total_chars": doc.total_chars,
            "chapter_count": doc.chapter_count,
            "section_count": doc.section_count,
            "kp_count": doc.kp_count,
            "formula_count": doc.formula_count,
            "example_count": doc.example_count,
            "exercise_count": doc.exercise_count,
            "chunk_count": doc.chunk_count,
            "vector_count": doc.vector_count,
            "parse_seconds": doc.parse_seconds,
            "parse_error": doc.parse_error,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        },
        "chapters": [
            {
                "id": c.id,
                "chapter_number": c.chapter_number,
                "chapter_name": c.chapter_name,
                "order_index": c.order_index,
            }
            for c in chapters
        ],
    }


@router.delete("/documents/{doc_id}", summary="删除文档")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise NotFoundError("文档")

    # 删除磁盘文件
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception as e:
        logger.warning(f"文件删除失败: {e}")

    # 清理向量库（尝试删除该课程的向量索引缓存）
    try:
        if doc.course_id and doc.course_id in rag_service._index_managers:
            del rag_service._index_managers[doc.course_id]
    except Exception:
        pass

    # 删除 DB 记录（关联的 chapters/fragments/knowledge_points 也删除）
    # 先找到本文档的章节 ID，再删除知识点（有 FK 约束）
    ch_ids = [c.id for c in db.query(Chapter).filter(Chapter.document_id == doc_id).all()]
    if ch_ids:
        db.query(KnowledgePoint).filter(KnowledgePoint.chapter_id.in_(ch_ids)).delete(synchronize_session=False)
    db.query(Fragment).filter(Fragment.document_id == doc_id).delete()
    db.query(Chapter).filter(Chapter.document_id == doc_id).delete()
    db.delete(doc)
    db.commit()

    return {"success": True, "message": "文档已删除"}


@router.post("/documents/{doc_id}/reparse", summary="重新解析文档")
def reparse_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise NotFoundError("文档")

    # 清理旧数据（先删知识点，再删章节，维持 FK 顺序）
    ch_ids = [c.id for c in db.query(Chapter).filter(Chapter.document_id == doc_id).all()]
    if ch_ids:
        db.query(KnowledgePoint).filter(KnowledgePoint.chapter_id.in_(ch_ids)).delete(synchronize_session=False)
    db.query(Fragment).filter(Fragment.document_id == doc_id).delete()
    db.query(Chapter).filter(Chapter.document_id == doc_id).delete()
    _update_doc_status(db, doc_id, "uploaded",
                       chunk_count=0, vector_count=0, parse_error="")

    background_tasks.add_task(
        _background_parse, doc_id, doc.file_path, doc.course_id or ""
    )

    return {"success": True, "message": "已重新触发解析"}


@router.get("/documents", summary="获取文档列表")
def list_documents(
    course_id: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Document)
    if course_id:
        query = query.filter(Document.course_id == course_id)
    docs = query.order_by(Document.created_at.desc()).limit(100).all()

    return {
        "success": True,
        "total": len(docs),
        "documents": [
            {
                "id": d.id,
                "file_name": d.file_name,
                "file_type": d.file_type,
                "file_size": d.file_size,
                "course_id": d.course_id,
                "parse_status": d.parse_status,
                "chapter_count": d.chapter_count,
                "kp_count": d.kp_count,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
    }
