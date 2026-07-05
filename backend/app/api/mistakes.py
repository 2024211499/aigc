# -*- coding: utf-8 -*-
"""错题本接口"""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db, Mistake, Exercise, gen_id, now
from ..core.exceptions import NotFoundError
from ..agents.bridge import agent_service

router = APIRouter()


@router.get("/mistakes", summary="获取错题列表")
def list_mistakes(
    user_id: str = "anonymous",
    course_id: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Mistake).filter(Mistake.user_id == user_id)
    if course_id:
        query = query.filter(Mistake.course_id == course_id)
    mistakes = query.order_by(Mistake.created_at.desc()).limit(100).all()

    result = []
    for m in mistakes:
        ex = db.query(Exercise).filter(Exercise.id == m.exercise_id).first()
        result.append({
            "id": m.id,
            "exercise_id": m.exercise_id,
            "stem": ex.stem[:100] if ex else "",
            "question_type": ex.question_type if ex else "",
            "error_type": m.error_type,
            "error_reason": m.error_reason,
            "mastered": m.mastered,
            "review_count": m.review_count,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return {"success": True, "total": len(result), "mistakes": result}


@router.post("/mistakes/{mistake_id}/review", summary="复习错题")
def review_mistake(mistake_id: str, db: Session = Depends(get_db)):
    m = db.query(Mistake).filter(Mistake.id == mistake_id).first()
    if not m:
        raise NotFoundError("错题")
    m.review_count += 1
    m.last_reviewed = now()
    db.commit()
    ex = db.query(Exercise).filter(Exercise.id == m.exercise_id).first()
    return {
        "success": True,
        "exercise": {
            "stem": ex.stem if ex else "",
            "answer": ex.answer if ex else "",
            "explanation": ex.explanation if ex else "",
            "mistake_tip": ex.mistake_tip if ex else "",
        },
        "error_type": m.error_type,
        "error_reason": m.error_reason,
    }


@router.post("/mistakes/{mistake_id}/variants", summary="生成变式题")
def mistake_variants(mistake_id: str, db: Session = Depends(get_db)):
    m = db.query(Mistake).filter(Mistake.id == mistake_id).first()
    if not m:
        raise NotFoundError("错题")
    ex = db.query(Exercise).filter(Exercise.id == m.exercise_id).first()
    result = agent_service.generate_exercises(
        fragments=[ex.stem, ex.explanation] if ex else [],
        knowledge_point=ex.stem[:50] if ex else "",
        count=3,
    )
    return {"success": True, "variants": result}


@router.patch("/mistakes/{mistake_id}/mastered", summary="标记已掌握")
def mark_mastered(mistake_id: str, db: Session = Depends(get_db)):
    m = db.query(Mistake).filter(Mistake.id == mistake_id).first()
    if not m:
        raise NotFoundError("错题")
    m.mastered = True
    db.commit()
    return {"success": True}
