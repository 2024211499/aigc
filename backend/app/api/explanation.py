# -*- coding: utf-8 -*-
"""智能讲解接口"""

from typing import Optional
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db, Fragment
from ..agents.bridge import agent_service
from ..rag.bridge import rag_service

router = APIRouter()

STYLE_MAP = {
    "zero_basic": "零基础讲解",
    "textbook": "教材同步讲解",
    "exam": "考试提分讲解",
    "derivation": "推导理解讲解",
    "analogy": "类比图解讲解",
    "blackboard": "板书式讲解",
    "lecture_script": "课堂讲稿式讲解",
}


class ExplanationRequest(BaseModel):
    course_id: str
    knowledge_point: str
    explanation_style: Optional[str] = "textbook"
    user_level: Optional[str] = "中等"
    need_example: Optional[bool] = True
    chapter_id: Optional[str] = ""


@router.post("/explanation/generate", summary="生成知识点讲解")
def generate_explanation(req: ExplanationRequest, db: Session = Depends(get_db)):
    """调用 2号 ExplanationAgent 生成分层讲解"""
    fragments = rag_service.retrieve(req.course_id, req.knowledge_point, top_k=5)
    if not fragments:
        frags_db = db.query(Fragment).filter(Fragment.course_id == req.course_id).limit(5).all()
        fragments = [f.text for f in frags_db]

    style_label = STYLE_MAP.get(req.explanation_style, req.explanation_style)

    result = agent_service.generate_explanation(
        fragments=fragments,
        knowledge_point=req.knowledge_point,
        style=style_label,
        user_level=req.user_level,
        course_id=req.course_id,
    )

    return {
        "success": True,
        "knowledge_point": req.knowledge_point,
        "style": req.explanation_style,
        "explanation": result,
    }
