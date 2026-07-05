# -*- coding: utf-8 -*-
"""习题与答题接口"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import (
    get_db, Fragment, Exercise, AnswerRecord, Mistake, gen_id, now
)
from ..core.exceptions import NotFoundError
from ..agents.bridge import agent_service
from ..rag.bridge import rag_service

router = APIRouter()


class ExerciseGenRequest(BaseModel):
    course_id: str
    chapter_id: Optional[str] = ""
    knowledge_point: Optional[str] = ""
    question_types: Optional[List[str]] = ["choice", "calc"]
    difficulty: Optional[str] = "medium"
    count: Optional[int] = 5
    weak_points: Optional[List[str]] = []


class SubmitAnswerRequest(BaseModel):
    exercise_id: str
    student_answer: str
    user_id: Optional[str] = "anonymous"
    time_spent_sec: Optional[int] = 0


class HomeworkRequest(BaseModel):
    question: str
    student_answer: Optional[str] = ""
    mode: Optional[str] = "step_by_step"   # hint / step_by_step / correction
    course_id: Optional[str] = ""
    fragments: Optional[List[str]] = []
    image_base64: Optional[str] = None  # 截图/拍照的 base64 编码图片


@router.post("/exercises/generate", summary="生成习题")
def generate_exercises(req: ExerciseGenRequest, db: Session = Depends(get_db)):
    """调用 2号 ExerciseAgent 生成习题集"""
    fragments = rag_service.retrieve(
        req.course_id, req.knowledge_point or "核心知识", top_k=6
    )
    if not fragments:
        frags_db = db.query(Fragment).filter(Fragment.course_id == req.course_id).limit(6).all()
        fragments = [f.text for f in frags_db]

    result = agent_service.generate_exercises(
        fragments=fragments,
        course_id=req.course_id,
        knowledge_point=req.knowledge_point or "",
        question_types=req.question_types,
        difficulty=req.difficulty,
        count=req.count,
    )

    # 将生成的题目存入 DB
    exercises_data = result.get("exercises", [])
    saved_ids = []
    for ex in exercises_data:
        if not isinstance(ex, dict):
            continue
        e = Exercise(
            id=gen_id(),
            course_id=req.course_id,
            chapter_id=req.chapter_id or None,
            question_type=ex.get("question_type", "calc"),
            difficulty=ex.get("difficulty", "medium"),
            stem=ex.get("stem", ex.get("question", "")),
            options=ex.get("options", []),
            answer=str(ex.get("answer", "")),
            explanation=ex.get("explanation", ""),
            score_criteria=ex.get("score_criteria", ""),
            mistake_tip=ex.get("mistake_tip", ex.get("mistake_tips", "")),
            source_ref=ex.get("source_ref", ""),
        )
        db.add(e)
        saved_ids.append(e.id)
    db.commit()

    return {
        "success": True,
        "exercise_ids": saved_ids,
        "count": len(saved_ids),
        "exercises": result,
    }


@router.get("/exercises/{exercise_id}", summary="获取题目详情")
def get_exercise(exercise_id: str, db: Session = Depends(get_db)):
    ex = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not ex:
        raise NotFoundError("题目")
    return {
        "success": True,
        "exercise": {
            "id": ex.id,
            "question_type": ex.question_type,
            "difficulty": ex.difficulty,
            "stem": ex.stem,
            "options": ex.options,
        },
    }


@router.post("/exercises/submit", summary="提交答案")
def submit_answer(req: SubmitAnswerRequest, db: Session = Depends(get_db)):
    """学生提交答案，触发错题诊断"""
    ex = db.query(Exercise).filter(Exercise.id == req.exercise_id).first()
    if not ex:
        raise NotFoundError("题目")

    # 简单判题（对于选择/填空/判断题精确匹配；主观题由 Agent 诊断）
    is_correct = False
    if ex.question_type in ("choice", "fill", "judge"):
        is_correct = req.student_answer.strip().lower() == ex.answer.strip().lower()
    else:
        # 主观题交给 Agent 诊断
        pass

    # 错题诊断（主观题 or 客观题做错时）
    diagnosis = {}
    if not is_correct:
        # 从 DB 取该课程相关片段，给 Agent 提供上下文
        ref_frags = []
        if ex.course_id:
            ref_frags = [
                f.text for f in db.query(Fragment)
                .filter(Fragment.course_id == ex.course_id)
                .limit(4).all()
            ]
        diagnosis = agent_service.diagnose_mistake(
            question=ex.stem,
            standard_answer=ex.answer,
            student_answer=req.student_answer,
            explanation=ex.explanation,
            fragments=ref_frags,
        )

    # 记录答题
    record = AnswerRecord(
        id=gen_id(),
        user_id=req.user_id or "anonymous",
        exercise_id=req.exercise_id,
        student_answer=req.student_answer,
        is_correct=is_correct,
        score=10.0 if is_correct else 0.0,
        diagnosis=diagnosis,
        time_spent_sec=req.time_spent_sec,
    )
    db.add(record)

    # 写入错题本
    if not is_correct:
        mistake = Mistake(
            id=gen_id(),
            user_id=req.user_id or "anonymous",
            exercise_id=req.exercise_id,
            course_id=ex.course_id,
            chapter_id=ex.chapter_id,
            error_type=diagnosis.get("error_type", ""),
            error_reason=diagnosis.get("error_reason", ""),
        )
        db.add(mistake)

    db.commit()

    return {
        "success": True,
        "is_correct": is_correct,
        "score": record.score,
        "answer": ex.answer,
        "explanation": ex.explanation if not is_correct else "",
        "diagnosis": diagnosis,
        "record_id": record.id,
    }


@router.post("/exercises/{exercise_id}/explain", summary="查看题目解析")
def explain_exercise(exercise_id: str, db: Session = Depends(get_db)):
    ex = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not ex:
        raise NotFoundError("题目")
    return {
        "success": True,
        "stem": ex.stem,
        "answer": ex.answer,
        "explanation": ex.explanation,
        "mistake_tip": ex.mistake_tip,
    }


@router.post("/exercises/{exercise_id}/variants", summary="生成变式题")
def generate_variants(exercise_id: str, db: Session = Depends(get_db)):
    ex = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not ex:
        raise NotFoundError("题目")

    result = agent_service.generate_exercises(
        fragments=[ex.stem, ex.explanation],
        knowledge_point=ex.stem[:50],
        count=3,
    )
    return {"success": True, "variants": result}


@router.post("/homework/tutor", summary="作业辅导")
def homework_tutor(req: HomeworkRequest, db: Session = Depends(get_db)):
    """调用 2号 HomeworkTutorAgent"""
    fragments = req.fragments or []
    if req.course_id and not fragments:
        frags_db = db.query(Fragment).filter(Fragment.course_id == req.course_id).limit(4).all()
        fragments = [f.text for f in frags_db]

    result = agent_service.homework_tutor(
        question=req.question,
        student_answer=req.student_answer,
        mode=req.mode,
        fragments=fragments,
        image_base64=req.image_base64,
    )
    return {"success": True, "tutoring": result}


@router.post("/homework/diagnose", summary="上传解答并诊断")
def diagnose_homework(
    question: str = Body(..., embed=True),
    student_answer: str = Body(..., embed=True),
    standard_answer: str = Body(default="", embed=True),
):
    result = agent_service.diagnose_mistake(
        question=question,
        standard_answer=standard_answer,
        student_answer=student_answer,
    )
    return {"success": True, "diagnosis": result}
