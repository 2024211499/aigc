# -*- coding: utf-8 -*-
"""微课生成接口"""

import os
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from ..core.database import get_db, Fragment, VideoLesson, gen_id
from ..core.exceptions import NotFoundError
from ..agents.bridge import agent_service
from ..rag.bridge import rag_service

router = APIRouter()


class MicroLessonRequest(BaseModel):
    course_id: str
    topic: str
    chapter_name: Optional[str] = ""
    style: Optional[str] = "讲解式"
    duration_seconds: Optional[int] = 300   # 5分钟
    target_level: Optional[str] = "大学本科"
    need_ppt: Optional[bool] = True
    need_tts: Optional[bool] = False
    need_video: Optional[bool] = False


class PPTRequest(BaseModel):
    course_id: str
    topic: str
    slide_count: Optional[int] = 10
    fragments: Optional[List[str]] = []


@router.post("/micro-lesson/script", summary="生成微课脚本")
def generate_script(req: MicroLessonRequest, db: Session = Depends(get_db)):
    """调用 2号 MicroLessonAgent 生成微课脚本"""
    fragments = rag_service.retrieve(req.course_id, req.topic, top_k=6)
    if not fragments:
        frags_db = db.query(Fragment).filter(Fragment.course_id == req.course_id).limit(6).all()
        fragments = [f.text for f in frags_db]

    script = agent_service.generate_micro_lesson(
        fragments=fragments,
        topic=req.topic,
        course_id=req.course_id,
        style=req.style,
        duration=req.duration_seconds,
    )

    lesson = VideoLesson(
        id=gen_id(),
        course_id=req.course_id,
        title=script.get("title", req.topic),
        topic=req.topic,
        script=script,
        status="script_ready",
        duration_sec=req.duration_seconds,
    )
    db.add(lesson)
    db.commit()

    return {
        "success": True,
        "lesson_id": lesson.id,
        "script": script,
        "next_steps": {
            "ppt": f"/api/micro-lesson/ppt  (lesson_id={lesson.id})",
            "tts": f"/api/micro-lesson/tts  (lesson_id={lesson.id})" if req.need_tts else None,
        },
    }


@router.post("/micro-lesson/ppt", summary="生成 PPT 内容")
def generate_ppt(req: PPTRequest, db: Session = Depends(get_db)):
    """调用 2号 PPTAgent 生成 PPT 内容结构"""
    fragments = req.fragments
    if not fragments:
        fragments = rag_service.retrieve(req.course_id, req.topic, top_k=5)
    if not fragments:
        frags_db = db.query(Fragment).filter(Fragment.course_id == req.course_id).limit(5).all()
        fragments = [f.text for f in frags_db]

    ppt_content = agent_service.generate_ppt_content(
        fragments=fragments,
        topic=req.topic,
        course_id=req.course_id,
    )

    return {
        "success": True,
        "topic": req.topic,
        "ppt_content": ppt_content,
        "slide_count": len(ppt_content.get("slides", [])),
    }


class TTSRequest(BaseModel):
    lesson_id: str
    vcn: Optional[str] = "x2_F25"  # 默认：倩倩-清甜

@router.post("/micro-lesson/tts", summary="生成语音（TTS）")
def generate_tts(req: TTSRequest, db: Session = Depends(get_db)):
    """调用 vivo TTS 接口生成语音文件"""
    lesson = db.query(VideoLesson).filter(VideoLesson.id == req.lesson_id).first()
    if not lesson:
        raise NotFoundError("微课")

    script = lesson.script or {}
    sections = script.get("sections", [])
    texts = [s.get("script", "") for s in sections if isinstance(s, dict) and s.get("script")]
    full_text = "。".join(texts) if texts else script.get("subtitle_text", "") or lesson.topic

    if not full_text.strip():
        return {"success": False, "error": "没有可合成的文本内容"}

    # 调用 vivo TTS
    from ..core.config import settings
    from ..services.vivo_tts import VivoTTS

    app_id = os.getenv("VIVO_OCR_APP_ID", settings.LLM_API_KEY)
    app_key = os.getenv("VIVO_OCR_APP_KEY", "")

    if not app_key or not app_id:
        return {
            "success": False,
            "lesson_id": req.lesson_id,
            "status": "error",
            "error": "未配置 vivo TTS 凭证（VIVO_OCR_APP_ID / VIVO_OCR_APP_KEY）",
        }

    try:
        tts = VivoTTS(app_id=app_id, app_key=app_key, engineid="long_audio_synthesis_screen")
        # 分段合成（长文本拆成短句）
        output_dir = settings.EXPORT_DIR / "tts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{req.lesson_id}.wav"

        # 如果文本过长，分段合成后拼接
        chunk_size = 200  # 每段最多 200 字
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        all_wav = b""
        for chunk in chunks:
            wav_bytes = tts.synthesize(chunk, vcn=req.vcn)
            all_wav += wav_bytes

        output_path.write_bytes(all_wav)
        lesson.audio_file_path = str(output_path)
        lesson.status = "tts_ready"
        db.commit()

        return {
            "success": True,
            "lesson_id": req.lesson_id,
            "status": "completed",
            "file_path": str(output_path),
            "duration_sec": lesson.duration_sec,
        }
    except Exception as e:
        logger.error("TTS 生成失败: %s", e, exc_info=True)
        return {
            "success": False,
            "lesson_id": req.lesson_id,
            "status": "failed",
            "error": str(e),
        }


@router.post("/micro-lesson/video", summary="合成视频")
def generate_video(lesson_id: str, db: Session = Depends(get_db)):
    """视频合成占位接口，可接入 MoviePy / D-ID / HeyGen"""
    lesson = db.query(VideoLesson).filter(VideoLesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError("微课")
    return {
        "success": True,
        "lesson_id": lesson_id,
        "status": "pending",
        "message": "视频合成需接入 MoviePy / D-ID 等服务，当前已准备好脚本与PPT内容",
    }


@router.get("/micro-lesson/{lesson_id}", summary="获取微课详情")
def get_lesson(lesson_id: str, db: Session = Depends(get_db)):
    lesson = db.query(VideoLesson).filter(VideoLesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError("微课")
    return {
        "success": True,
        "lesson": {
            "id": lesson.id,
            "title": lesson.title,
            "topic": lesson.topic,
            "status": lesson.status,
            "duration_sec": lesson.duration_sec,
            "script": lesson.script,
            "ppt_content": lesson.ppt_content,
            "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
        },
    }


@router.get("/micro-lesson/{lesson_id}/download", summary="下载微课文件")
def download_lesson(lesson_id: str, db: Session = Depends(get_db)):
    lesson = db.query(VideoLesson).filter(VideoLesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError("微课")
    return {
        "success": True,
        "lesson_id": lesson_id,
        "available_files": {
            "ppt": lesson.ppt_file_path or None,
            "audio": lesson.audio_file_path or None,
            "video": lesson.video_file_path or None,
        },
        "message": "如文件路径为空，请先调用对应生成接口",
    }
