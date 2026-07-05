# -*- coding: utf-8 -*-
"""数据看板接口"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..core.database import (
    get_db, AnswerRecord, Mistake, StudyPlan, ExamPaper,
    VideoLesson, LearningLog, Exercise, Chapter, Document, Fragment
)

router = APIRouter()


@router.get("/dashboard/student/{user_id}", summary="学生看板数据")
def student_dashboard(user_id: str, db: Session = Depends(get_db)):
    """聚合学生端看板所需的全部数据"""

    # 答题统计
    answers = db.query(AnswerRecord).filter(AnswerRecord.user_id == user_id).all()
    total_ans = len(answers)
    correct_ans = sum(1 for a in answers if a.is_correct)
    accuracy = round(correct_ans / total_ans * 100, 1) if total_ans > 0 else 0

    # 错题统计
    all_mistakes = db.query(Mistake).filter(Mistake.user_id == user_id).all()
    unmastered = [m for m in all_mistakes if not m.mastered]
    mastered = [m for m in all_mistakes if m.mastered]

    # 错误类型分布（饼图）
    error_dist: dict = {}
    for m in unmastered:
        et = m.error_type or "未分类"
        error_dist[et] = error_dist.get(et, 0) + 1

    # 学习计划
    plans = db.query(StudyPlan).filter(StudyPlan.user_id == user_id)\
        .order_by(StudyPlan.created_at.desc()).limit(5).all()

    # 近期学习记录（折线图用）
    logs = db.query(LearningLog).filter(LearningLog.user_id == user_id)\
        .order_by(LearningLog.created_at.desc()).limit(30).all()

    daily_duration: dict = {}
    for log in logs:
        if log.created_at:
            day = log.created_at.date().isoformat()
            daily_duration[day] = daily_duration.get(day, 0) + log.duration_sec

    return {
        "success": True,
        "user_id": user_id,
        "overview": {
            "total_answers": total_ans,
            "correct_answers": correct_ans,
            "accuracy_rate": accuracy,
            "mistake_count": len(unmastered),
            "mastered_count": len(mastered),
            "plan_count": len(plans),
        },
        "error_type_distribution": error_dist,
        "recent_plans": [
            {"id": p.id, "title": p.title,
             "created_at": p.created_at.isoformat() if p.created_at else None}
            for p in plans
        ],
        "daily_study_seconds": daily_duration,
        "recent_mistakes": [
            {
                "id": m.id,
                "exercise_id": m.exercise_id,
                "error_type": m.error_type,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in unmastered[:10]
        ],
    }


@router.get("/dashboard/teacher/{course_id}", summary="教师看板数据")
def teacher_dashboard(course_id: str, db: Session = Depends(get_db)):
    """聚合教师端看板所需的全部数据"""

    # 课程文档
    docs = db.query(Document).filter(Document.course_id == course_id).all()
    chapters = db.query(Chapter).filter(Chapter.course_id == course_id).all()
    fragments = db.query(Fragment).filter(Fragment.course_id == course_id).count()

    # 题目与答题
    exercises = db.query(Exercise).filter(Exercise.course_id == course_id).all()
    ex_ids = [e.id for e in exercises]

    answer_records: list = []
    if ex_ids:
        answer_records = db.query(AnswerRecord)\
            .filter(AnswerRecord.exercise_id.in_(ex_ids)).all()

    total_submissions = len(answer_records)
    correct_submissions = sum(1 for a in answer_records if a.is_correct)
    avg_accuracy = round(correct_submissions / total_submissions * 100, 1) if total_submissions > 0 else 0

    # 题目错误率排行（前 10）
    ex_wrong: dict = {}
    for a in answer_records:
        if not a.is_correct:
            ex_wrong[a.exercise_id] = ex_wrong.get(a.exercise_id, 0) + 1
    ex_wrong_sorted = sorted(ex_wrong.items(), key=lambda x: x[1], reverse=True)[:10]
    hard_exercises = []
    for ex_id, wrong_count in ex_wrong_sorted:
        ex = db.query(Exercise).filter(Exercise.id == ex_id).first()
        if ex:
            hard_exercises.append({
                "exercise_id": ex_id,
                "stem": ex.stem[:80],
                "wrong_count": wrong_count,
                "difficulty": ex.difficulty,
            })

    # 高频错误知识点（从错题诊断中统计）
    mistakes = db.query(Mistake).filter(Mistake.course_id == course_id).all()
    error_type_dist: dict = {}
    for m in mistakes:
        et = m.error_type or "未分类"
        error_type_dist[et] = error_type_dist.get(et, 0) + 1

    # 最近生成的试卷
    exams = db.query(ExamPaper).filter(ExamPaper.course_id == course_id)\
        .order_by(ExamPaper.created_at.desc()).limit(5).all()

    # 最近生成的微课
    lessons = db.query(VideoLesson).filter(VideoLesson.course_id == course_id)\
        .order_by(VideoLesson.created_at.desc()).limit(5).all()

    return {
        "success": True,
        "course_id": course_id,
        "resource_overview": {
            "document_count": len(docs),
            "chapter_count": len(chapters),
            "fragment_count": fragments,
            "exercise_count": len(exercises),
        },
        "answer_stats": {
            "total_submissions": total_submissions,
            "correct_submissions": correct_submissions,
            "average_accuracy": avg_accuracy,
            "mistake_count": len(mistakes),
        },
        "hard_exercises": hard_exercises,
        "error_type_distribution": error_type_dist,
        "recent_exams": [
            {"id": e.id, "title": e.title, "exam_type": e.exam_type,
             "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in exams
        ],
        "recent_lessons": [
            {"id": l.id, "title": l.title, "topic": l.topic, "status": l.status,
             "created_at": l.created_at.isoformat() if l.created_at else None}
            for l in lessons
        ],
        "chapters": [
            {"id": c.id, "chapter_name": c.chapter_name, "order_index": c.order_index}
            for c in chapters
        ],
    }
