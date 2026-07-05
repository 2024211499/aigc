# -*- coding: utf-8 -*-
"""学习包生成接口"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db, Fragment, Chapter, StudyPlan, gen_id, now
from ..core.exceptions import NotFoundError
from ..agents.bridge import agent_service
from ..rag.bridge import rag_service

router = APIRouter()


class LearningPackageRequest(BaseModel):
    course_id: str
    chapter_name: Optional[str] = ""
    chapter_id: Optional[str] = ""
    user_id: Optional[str] = "anonymous"
    learning_goal: Optional[str] = "掌握本章核心知识"
    study_days: Optional[int] = 7
    daily_minutes: Optional[int] = 60
    student_level: Optional[str] = "中等"
    exam_type: Optional[str] = "期末考试"
    need_exercises: Optional[bool] = True
    need_explanation: Optional[bool] = True
    need_micro_lesson: Optional[bool] = False


@router.post("/learning-package/generate", summary="生成章节学习包")
def generate_learning_package(
    req: LearningPackageRequest,
    db: Session = Depends(get_db),
):
    """
    综合调用 2号 OrchestratorAgent 生成完整学习包：
    学习计划 + 重点难点 + 知识点列表 + 推荐习题
    """
    # 1. 检索相关教材片段
    chapter_name = req.chapter_name
    if not chapter_name and req.chapter_id:
        ch = db.query(Chapter).filter(Chapter.id == req.chapter_id).first()
        chapter_name = ch.chapter_name if ch else ""

    fragments = rag_service.retrieve(
        course_id=req.course_id,
        query=chapter_name or "核心知识点",
        top_k=8,
    )
    if not fragments:
        # 降级：直接从 DB 取片段
        frags_db = db.query(Fragment).filter(Fragment.course_id == req.course_id).limit(8).all()
        fragments = [f.text for f in frags_db]

    user_profile = {
        "student_level": req.student_level,
        "exam_type": req.exam_type,
        "learning_goal": req.learning_goal,
    }

    # 2. 调用 2号 Agent 生成学习包
    result = agent_service.generate_learning_package(
        fragments=fragments,
        course_id=req.course_id,
        chapter_name=chapter_name,
        user_profile=user_profile,
        study_days=req.study_days,
        daily_time=req.daily_minutes,
        exercise_count=10 if req.need_exercises else 0,
    )

    # 3. 存入数据库
    # WorkflowResult 结构：result["final_package_structure"]["study_plan"]["title"]
    _pkg = result.get("final_package_structure", {})
    _plan_title = (
        _pkg.get("study_plan", {}).get("title")
        or _pkg.get("chapter_name")
        or result.get("title")
        or (chapter_name + " 学习计划" if chapter_name else "学习计划")
    )
    plan = StudyPlan(
        id=gen_id(),
        user_id=req.user_id,
        course_id=req.course_id,
        title=_plan_title,
        content=result,
    )
    db.add(plan)
    db.commit()

    return {
        "success": True,
        "plan_id": plan.id,
        "chapter_name": chapter_name,
        "fragments_used": len(fragments),
        "learning_package": result,
    }


@router.post("/plan/generate", summary="单独生成学习计划")
def generate_study_plan(
    course_id: str = Body(..., embed=True),
    chapter_name: str = Body(default="", embed=True),
    study_days: int = Body(default=7, embed=True),
    daily_minutes: int = Body(default=60, embed=True),
    student_level: str = Body(default="中等", embed=True),
    db: Session = Depends(get_db),
):
    """轻量版：只生成学习计划（不含习题/讲解）"""
    fragments = rag_service.retrieve(course_id, chapter_name or "核心内容", top_k=6)
    if not fragments:
        frags_db = db.query(Fragment).filter(Fragment.course_id == course_id).limit(6).all()
        fragments = [f.text for f in frags_db]

    result = agent_service.generate_learning_package(
        fragments=fragments,
        course_id=course_id,
        chapter_name=chapter_name,
        study_days=study_days,
        daily_time=daily_minutes,
    )

    return {"success": True, "study_plan": result}


@router.get("/study-plans/{plan_id}", summary="获取学习计划详情")
def get_study_plan(plan_id: str, db: Session = Depends(get_db)):
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
    if not plan:
        raise NotFoundError("学习计划")
    return {"success": True, "plan": {"id": plan.id, "title": plan.title, "content": plan.content}}


@router.get("/courses/{course_id}/study-plans", summary="获取课程学习计划列表")
def list_study_plans(course_id: str, db: Session = Depends(get_db)):
    plans = db.query(StudyPlan).filter(StudyPlan.course_id == course_id)\
        .order_by(StudyPlan.created_at.desc()).limit(20).all()
    return {
        "success": True,
        "plans": [{"id": p.id, "title": p.title,
                   "created_at": p.created_at.isoformat() if p.created_at else None}
                  for p in plans],
    }
