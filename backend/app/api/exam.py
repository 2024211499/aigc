# -*- coding: utf-8 -*-
"""智能组卷接口"""

from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db, Fragment, ExamPaper, gen_id
from ..core.exceptions import NotFoundError
from ..agents.bridge import agent_service
from ..rag.bridge import rag_service

router = APIRouter()


class ExamGenRequest(BaseModel):
    course_id: str
    chapters: Optional[List[str]] = []
    knowledge_points: Optional[List[str]] = []
    exam_type: Optional[str] = "单元测试"
    total_questions: Optional[int] = 20
    duration_minutes: Optional[int] = 90
    total_score: Optional[float] = 100.0
    include_answers: Optional[bool] = True
    include_explanations: Optional[bool] = True
    include_scoring: Optional[bool] = True
    student_version: Optional[bool] = True
    teacher_version: Optional[bool] = True
    difficulty_ratio: Optional[dict] = {"easy": 0.3, "medium": 0.5, "hard": 0.2}
    type_ratio: Optional[dict] = {"choice": 0.4, "fill": 0.2, "calc": 0.4}
    weak_points: Optional[List[str]] = []
    mistake_records: Optional[List[str]] = []


@router.post("/exam/generate", summary="生成试卷")
def generate_exam(req: ExamGenRequest, db: Session = Depends(get_db)):
    """调用 2号 ExamAgent 生成试卷"""
    fragments = rag_service.retrieve(
        req.course_id,
        " ".join(req.chapters[:3]) if req.chapters else "核心考点",
        top_k=8,
    )
    if not fragments:
        frags_db = db.query(Fragment).filter(Fragment.course_id == req.course_id).limit(8).all()
        fragments = [f.text for f in frags_db]

    exam_config = {
        "exam_type": req.exam_type,
        "total_questions": req.total_questions,
        "exam_duration_minutes": req.duration_minutes,
        "total_score": req.total_score,
        "include_answers": req.include_answers,
        "include_explanations": req.include_explanations,
        "difficulty_ratio": req.difficulty_ratio,
        "type_ratio": req.type_ratio,
        "weak_points": req.weak_points,
        "mistake_records": req.mistake_records,
    }

    result = agent_service.generate_exam(
        fragments=fragments,
        course_id=req.course_id,
        chapters=req.chapters,
        exam_config=exam_config,
    )

    paper = ExamPaper(
        id=gen_id(),
        course_id=req.course_id,
        title=result.get("title", f"{req.exam_type}试卷"),
        exam_type=req.exam_type,
        content=result,
        total_score=req.total_score,
        duration_min=req.duration_minutes,
        with_answer=req.include_answers,
        with_analysis=req.include_explanations,
    )
    db.add(paper)
    db.commit()

    return {
        "success": True,
        "exam_id": paper.id,
        "exam": result,
    }


@router.get("/exam/{exam_id}", summary="获取试卷详情")
def get_exam(exam_id: str, db: Session = Depends(get_db)):
    paper = db.query(ExamPaper).filter(ExamPaper.id == exam_id).first()
    if not paper:
        raise NotFoundError("试卷")
    return {
        "success": True,
        "exam": {
            "id": paper.id,
            "title": paper.title,
            "exam_type": paper.exam_type,
            "total_score": paper.total_score,
            "duration_min": paper.duration_min,
            "content": paper.content,
        },
    }


@router.post("/exam/{exam_id}/regenerate", summary="重新生成试卷")
def regenerate_exam(exam_id: str, db: Session = Depends(get_db)):
    paper = db.query(ExamPaper).filter(ExamPaper.id == exam_id).first()
    if not paper:
        raise NotFoundError("试卷")

    frags_db = db.query(Fragment).filter(Fragment.course_id == paper.course_id).limit(8).all()
    fragments = [f.text for f in frags_db]

    result = agent_service.generate_exam(
        fragments=fragments,
        course_id=paper.course_id,
        exam_config={"exam_type": paper.exam_type, "total_questions": 20},
    )
    paper.content = result
    db.commit()
    return {"success": True, "exam_id": exam_id, "exam": result}
