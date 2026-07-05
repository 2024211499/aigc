# -*- coding: utf-8 -*-
"""学习画像接口"""

from typing import Optional
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from ..core.database import (
    get_db, User, UserProfile, AnswerRecord, Mistake, LearningLog,
    Exercise, StudyPlan, gen_id, now
)
from ..agents.bridge import agent_service

router = APIRouter()


def _ensure_user(user_id: str, db: Session) -> None:
    if not user_id:
        return
    if db.query(User).filter(User.id == user_id).first():
        return
    db.add(User(id=user_id, username=user_id, role="student"))
    db.flush()


def _collect_learning_records(user_id: str, db: Session) -> dict:
    """从 DB 聚合用户学习数据"""
    answers = db.query(AnswerRecord).filter(AnswerRecord.user_id == user_id)\
        .order_by(AnswerRecord.created_at.desc()).limit(200).all()
    mistakes = db.query(Mistake).filter(Mistake.user_id == user_id, Mistake.mastered == False).all()
    logs = db.query(LearningLog).filter(LearningLog.user_id == user_id)\
        .order_by(LearningLog.created_at.desc()).limit(100).all()

    total = len(answers)
    correct = sum(1 for a in answers if a.is_correct)
    accuracy = round(correct / total * 100, 1) if total > 0 else 0

    error_types = {}
    for m in mistakes:
        et = m.error_type or "未分类"
        error_types[et] = error_types.get(et, 0) + 1

    return {
        "total_answers": total,
        "correct_answers": correct,
        "accuracy_rate": accuracy,
        "mistake_count": len(mistakes),
        "mastered_count": db.query(Mistake).filter(
            Mistake.user_id == user_id, Mistake.mastered == True).count(),
        "error_type_distribution": error_types,
        "recent_actions": [
            {"action": l.action, "detail": l.detail,
             "created_at": l.created_at.isoformat() if l.created_at else None}
            for l in logs[:10]
        ],
    }


@router.get("/profile/{user_id}", summary="获取学习画像")
def get_profile(user_id: str, db: Session = Depends(get_db)):
    """获取或生成学生学习画像"""
    _ensure_user(user_id, db)
    # 先查缓存
    prof = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    records = _collect_learning_records(user_id, db)

    # 若无缓存或记录变化，调用 Agent 重新生成
    if not prof or records["total_answers"] > (prof.profile_data or {}).get("total_answers", -1):
        profile_data = agent_service.generate_profile(user_id, records)
        profile_data.update(records)   # 合并原始统计数据

        if prof:
            prof.profile_data = profile_data
            prof.updated_at = now()
        else:
            prof = UserProfile(
                id=gen_id(),
                user_id=user_id,
                profile_data=profile_data,
            )
            db.add(prof)
        db.commit()

    return {
        "success": True,
        "user_id": user_id,
        "profile": prof.profile_data,
        "stats": records,
    }


@router.post("/profile/update", summary="更新学习画像")
def update_profile(
    user_id: str = Body(..., embed=True),
    extra_data: dict = Body(default={}, embed=True),
    db: Session = Depends(get_db),
):
    _ensure_user(user_id, db)
    prof = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if prof:
        merged = {**(prof.profile_data or {}), **extra_data}
        prof.profile_data = merged
        prof.updated_at = now()
    else:
        prof = UserProfile(
            id=gen_id(),
            user_id=user_id,
            profile_data=extra_data,
        )
        db.add(prof)
    db.commit()
    return {"success": True}


@router.post("/learning-log", summary="记录学习行为")
def log_action(
    user_id: str = Body(..., embed=True),
    action: str = Body(..., embed=True),
    course_id: Optional[str] = Body(default="", embed=True),
    detail: dict = Body(default={}, embed=True),
    duration_sec: int = Body(default=0, embed=True),
    db: Session = Depends(get_db),
):
    _ensure_user(user_id, db)
    log = LearningLog(
        id=gen_id(),
        user_id=user_id,
        course_id=course_id or None,
        action=action,
        detail=detail,
        duration_sec=duration_sec,
    )
    db.add(log)
    db.commit()
    return {"success": True}
