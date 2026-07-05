# -*- coding: utf-8 -*-
"""学习包生成接口。"""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agents.bridge import agent_service
from ..core.database import Chapter, Fragment, StudyPlan, gen_id, get_db
from ..core.exceptions import NotFoundError
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
    chapter_name = req.chapter_name or ""
    if not chapter_name and req.chapter_id:
        ch = db.query(Chapter).filter(Chapter.id == req.chapter_id).first()
        chapter_name = ch.chapter_name if ch else ""

    fragments = _retrieve_fragments(db, req.course_id, req.chapter_id or "", chapter_name)
    user_profile = {
        "student_level": req.student_level,
        "exam_type": req.exam_type,
        "learning_goal": req.learning_goal,
        "daily_minutes": req.daily_minutes,
    }

    try:
        result = agent_service.generate_learning_package(
            fragments=fragments,
            course_id=req.course_id,
            chapter_name=chapter_name,
            user_profile=user_profile,
            study_days=req.study_days,
            daily_time=req.daily_minutes,
            exercise_count=10 if req.need_exercises else 0,
        )
        if not isinstance(result, dict) or not result:
            result = _local_learning_package(req, chapter_name, fragments, user_profile)
    except Exception:
        result = _local_learning_package(req, chapter_name, fragments, user_profile)

    pkg = result.get("final_package_structure", {})
    plan_title = (
        pkg.get("study_plan", {}).get("title")
        or pkg.get("chapter_name")
        or result.get("title")
        or (f"{chapter_name} 学习计划" if chapter_name else "学习计划")
    )
    plan = StudyPlan(
        id=gen_id(),
        user_id=req.user_id,
        course_id=req.course_id,
        title=plan_title,
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
    fragments = _retrieve_fragments(db, course_id, "", chapter_name)
    result = _local_learning_package(
        LearningPackageRequest(
            course_id=course_id,
            chapter_name=chapter_name,
            study_days=study_days,
            daily_minutes=daily_minutes,
            student_level=student_level,
        ),
        chapter_name,
        fragments,
        {"student_level": student_level},
    )
    return {"success": True, "study_plan": result}


@router.get("/study-plans/{plan_id}", summary="获取学习计划详情")
def get_study_plan(plan_id: str, db: Session = Depends(get_db)):
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
    if not plan:
        raise NotFoundError("学习计划")
    return {
        "success": True,
        "plan": {"id": plan.id, "title": plan.title, "content": plan.content},
    }


@router.get("/courses/{course_id}/study-plans", summary="获取课程学习计划列表")
def list_study_plans(course_id: str, db: Session = Depends(get_db)):
    plans = (
        db.query(StudyPlan)
        .filter(StudyPlan.course_id == course_id)
        .order_by(StudyPlan.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "success": True,
        "plans": [
            {
                "id": p.id,
                "title": p.title,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plans
        ],
    }


def _retrieve_fragments(
    db: Session,
    course_id: str,
    chapter_id: str,
    chapter_name: str,
) -> List[str]:
    try:
        fragments = rag_service.retrieve(
            course_id=course_id,
            query=chapter_name or "核心知识点",
            top_k=8,
        )
    except Exception:
        fragments = []
    if fragments:
        return fragments

    query = db.query(Fragment).filter(Fragment.course_id == course_id)
    if chapter_id:
        query = query.filter(Fragment.chapter_id == chapter_id)
    frags_db = query.order_by(Fragment.page_start, Fragment.created_at).limit(8).all()
    return [f.text for f in frags_db]


def _local_learning_package(
    req: LearningPackageRequest,
    chapter_name: str,
    fragments: List[str],
    user_profile: dict,
) -> dict:
    title = chapter_name or "课程学习路径"
    text = "\n".join(fragments)[:1600]
    key_lines = [line.strip() for line in text.splitlines() if line.strip()][:6]
    if not key_lines and text:
        key_lines = [text[:180]]

    days = max(1, min(req.study_days or 5, 10))
    tasks = []
    for index in range(days):
        source = key_lines[index % len(key_lines)] if key_lines else title
        tasks.append(
            {
                "day": index + 1,
                "title": f"第 {index + 1} 天：{title}",
                "lecture": source,
                "practice": "完成本节 3 道练习，并把不会的题加入复盘。",
                "review": "用自己的话复述本节核心概念、公式和适用条件。",
            }
        )

    return {
        "fallback": True,
        "chapter_name": title,
        "user_profile": user_profile,
        "final_package_structure": {
            "study_plan": {
                "title": f"{title} 学习计划",
                "daily_minutes": req.daily_minutes,
                "tasks": tasks,
            },
            "lecture": {
                "title": f"{title} 讲义",
                "summary": key_lines[0] if key_lines else "根据已解析资料生成基础讲义。",
                "key_points": key_lines,
            },
        },
    }
