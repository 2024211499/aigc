"""完整课程资料入库流水线。"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Dict, Optional, Union

from ..processing.chunking import split_pages_by_structure
from ..config import ExtractionConfig
from ..storage.course_index import delete_document_vectors, rebuild_course_index, save_fragments_to_vector_store
from ..parsing.document_parser import detect_file_type, parse_document_result
from ..retrieval.embeddings import file_md5
from ..knowledge.extractor import summarize_knowledge_for_chapter
from ..reporting.reporting import generate_parse_report
from ..storage.sqlite import CourseDB, save_fragments_to_db
from ..processing.structure import detect_chapters


def _document_id(course_id: str, source_path: str) -> str:
    digest = file_md5(source_path)
    prefix = hashlib.md5(str(course_id).encode("utf-8", errors="ignore")).hexdigest()[:6]
    return f"doc_{prefix}_{digest[:16]}"


def parse_document(
    file_path: str,
    course_id: Optional[str] = None,
    *,
    course_name: Optional[str] = None,
    config: Optional[Union[ExtractionConfig, Dict]] = None,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
    build_vector: bool = True,
    force: bool = True,
    embedding_provider: Optional[str] = None,
) -> Dict:
    """
    统一入口：真实文档解析 -> 章节识别 -> 知识抽取 -> 结构化分块 -> 入库 -> 向量索引 -> 解析报告。

    返回包含 document_id、outline、fragments、knowledge、report，可直接给前端展示。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    course_id = course_id or "default_course"
    course_name = course_name or course_id
    abs_path = os.path.abspath(file_path)
    document_id = _document_id(course_id, abs_path)
    db = CourseDB(db_path)
    db.save_course(course_id, course_name)

    if not force and db.get_document(document_id):
        return {
            "document_id": document_id,
            "course_id": course_id,
            "skipped": True,
            "report": generate_parse_report(document_id, db_path=db_path),
        }

    for old_doc in db.get_documents(course_id):
        if os.path.abspath(old_doc.get("source_path", "")) == abs_path and old_doc["document_id"] != document_id:
            delete_document_vectors(old_doc["document_id"], db_path=db_path, persist_dir=persist_dir)
            db.delete_document(old_doc["document_id"])

    if force and db.get_document(document_id):
        delete_document_vectors(document_id, db_path=db_path, persist_dir=persist_dir)

    started_at = time.monotonic()
    vector_error = None
    try:
        parsed = parse_document_result(abs_path, config=config, course_id=course_id)
        file_type = parsed.metadata.get("file_type") or detect_file_type(abs_path)
        doc_md5 = file_md5(abs_path)
        failed_pages = parsed.metadata.get("failed_pages", [])
        db.save_document({
            "document_id": document_id,
            "course_id": course_id,
            "file_name": os.path.basename(abs_path),
            "file_type": file_type,
            "source_path": abs_path,
            "doc_md5": doc_md5,
            "page_count": parsed.metadata.get("page_count", 0) + len(failed_pages),
            "char_count": parsed.metadata.get("char_count", 0),
            "status": "parsed" if parsed.text.strip() else "parsed_empty",
            "errors": failed_pages,
        })
        db.save_pages(document_id, parsed.pages, failed_pages=failed_pages)

        chapters = detect_chapters(parsed.pages)
        outline = {
            "document_id": document_id,
            "course_id": course_id,
            "file_name": os.path.basename(abs_path),
            "chapter_count": len(chapters),
            "section_count": sum(len(ch.get("sections", [])) for ch in chapters),
            "chapters": chapters,
        }

        knowledge = []
        for chapter in chapters:
            chapter_knowledge = summarize_knowledge_for_chapter(chapter)
            knowledge.append(chapter_knowledge)
            db.save_knowledge_points(course_id, document_id, chapter, chapter_knowledge.get("knowledge_points", []))

        fragments = split_pages_by_structure(
            parsed.pages,
            course_id=course_id,
            course_name=course_name,
            document_id=document_id,
            file_name=os.path.basename(abs_path),
            source_path=abs_path,
        )
        save_fragments_to_db(fragments, db_path=db_path)

        vector_count = 0
        if build_vector and fragments:
            try:
                vector_count = save_fragments_to_vector_store(
                    fragments,
                    course_id=course_id,
                    db_path=db_path,
                    persist_dir=persist_dir,
                    provider=embedding_provider,
                )
            except Exception as exc:
                vector_error = str(exc)

        report = generate_parse_report(document_id, db_path=db_path)
        report["elapsed_time"] = round(time.monotonic() - started_at, 3)
        report["vector_count"] = vector_count or report.get("vector_count", 0)
        report["index_success"] = bool(fragments) and not vector_error and report["vector_count"] == len(fragments)
        if vector_error:
            report.setdefault("exceptions", []).append({"stage": "vector_index", "error": vector_error})
        db.update_document_report(document_id, report, status="indexed" if report["index_success"] else "parsed")

        return {
            "document_id": document_id,
            "course_id": course_id,
            "course_name": course_name,
            "outline": outline,
            "knowledge": knowledge,
            "fragments": fragments,
            "report": report,
        }
    except Exception as exc:
        file_type = "unknown"
        try:
            file_type = detect_file_type(abs_path)
        except Exception:
            pass
        db.save_document({
            "document_id": document_id,
            "course_id": course_id,
            "file_name": os.path.basename(abs_path),
            "file_type": file_type,
            "source_path": abs_path,
            "doc_md5": file_md5(abs_path),
            "page_count": 0,
            "char_count": 0,
            "status": "failed",
            "errors": [{"stage": "parse_document", "error": str(exc)}],
        })
        report = generate_parse_report(document_id, db_path=db_path)
        report["elapsed_time"] = round(time.monotonic() - started_at, 3)
        report.setdefault("exceptions", []).append({"stage": "parse_document", "error": str(exc)})
        db.update_document_report(document_id, report, status="failed")
        return {
            "document_id": document_id,
            "course_id": course_id,
            "outline": {"chapters": []},
            "knowledge": [],
            "fragments": [],
            "report": report,
            "error": str(exc),
        }


def reparse_document(
    document_id: str,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
    build_vector: bool = True,
) -> Dict:
    """重新解析、重新分块、重新入库。"""
    db = CourseDB(db_path)
    doc = db.get_document(document_id)
    if not doc:
        raise FileNotFoundError(f"文档不存在: {document_id}")
    delete_document_vectors(document_id, db_path=db_path, persist_dir=persist_dir)
    db.delete_document(document_id)
    return parse_document(
        doc["source_path"],
        course_id=doc["course_id"],
        course_name=doc.get("course_name") or doc["course_id"],
        db_path=db_path,
        persist_dir=persist_dir,
        build_vector=build_vector,
        force=True,
    )


def delete_document(
    document_id: str,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
) -> Dict:
    """删除资料及其页、片段、知识点、向量。"""
    db = CourseDB(db_path)
    doc = db.get_document(document_id)
    delete_document_vectors(document_id, db_path=db_path, persist_dir=persist_dir)
    db.delete_document(document_id)
    return {"document_id": document_id, "deleted": True, "course_id": doc.get("course_id") if doc else None}


def rebuild_course(
    course_id: str,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
    embedding_provider: Optional[str] = None,
    build_vector: bool = True,
) -> Dict:
    """重新构建某门课程的 Chroma 向量库。"""
    count = rebuild_course_index(course_id, db_path=db_path, persist_dir=persist_dir, provider=embedding_provider)
    return {"course_id": course_id, "vector_count": count, "index_success": count > 0}


def index_document(
    file_path: str,
    course_id: Optional[str] = None,
    *,
    course_name: Optional[str] = None,
    force: bool = False,
    config: Optional[Union[ExtractionConfig, Dict]] = None,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
    embedding_provider: Optional[str] = None,
    build_vector: bool = True,
) -> Dict:
    """Formal indexing entrypoint with md5 skip by default."""
    return parse_document(
        file_path,
        course_id=course_id,
        course_name=course_name,
        config=config,
        db_path=db_path,
        persist_dir=persist_dir,
        build_vector=build_vector,
        force=force,
        embedding_provider=embedding_provider,
    )


__all__ = [
    "parse_document",
    "index_document",
    "reparse_document",
    "delete_document",
    "rebuild_course",
]
