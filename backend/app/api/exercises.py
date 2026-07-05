# -*- coding: utf-8 -*-
"""习题与答题接口"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import (
    get_db, User, Fragment, Exercise, AnswerRecord, Mistake, gen_id, now
)
from ..core.exceptions import NotFoundError
from ..agents.bridge import agent_service
from ..rag.bridge import rag_service

router = APIRouter()


def _ensure_user(user_id: str, db: Session) -> None:
    if not user_id:
        return
    if db.query(User).filter(User.id == user_id).first():
        return
    db.add(User(id=user_id, username=user_id, role="student"))
    db.flush()


class ExerciseGenRequest(BaseModel):
    course_id: str
    chapter_id: Optional[str] = ""
    knowledge_point: Optional[str] = ""
    question_types: Optional[List[str]] = ["choice", "calc"]
    difficulty: Optional[str] = "medium"
    count: Optional[int] = 5
    weak_points: Optional[List[str]] = []
    fast_mode: Optional[bool] = True


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
    """生成习题集。默认走本地快速生成，避免移动端等待 40-60 秒。"""
    query = req.knowledge_point or "核心知识"
    fragments = []
    if not req.fast_mode:
        fragments = rag_service.retrieve(req.course_id, query, top_k=6)
    if not fragments:
        frags_query = db.query(Fragment).filter(Fragment.course_id == req.course_id)
        if req.chapter_id:
            frags_query = frags_query.filter(Fragment.chapter_id == req.chapter_id)
        frags_db = frags_query.order_by(Fragment.page_start, Fragment.created_at).limit(8).all()
        fragments = [f.text for f in frags_db]
    if not req.knowledge_point and fragments:
        query = _infer_point_from_fragments(fragments)

    if req.fast_mode:
        exercises_data = _fallback_exercises(
            fragments=fragments,
            knowledge_point=query,
            count=req.count or 5,
            difficulty=req.difficulty or "medium",
        )
        result = {"exercises": exercises_data, "fast_mode": True}
    else:
        result = agent_service.generate_exercises(
            fragments=fragments,
            course_id=req.course_id,
            knowledge_point=query,
            question_types=req.question_types,
            difficulty=req.difficulty,
            count=req.count,
        )

    # 将生成的题目存入 DB；Agent 异常时可能只返回工作流结构，不含题目。
    exercises_data = result.get("exercises") or result.get("questions") or []
    if isinstance(exercises_data, dict):
        exercises_data = exercises_data.get("questions") or exercises_data.get("items") or []
    if not exercises_data:
        exercises_data = _fallback_exercises(
            fragments=fragments,
            knowledge_point=req.knowledge_point or "核心知识",
            count=req.count or 5,
            difficulty=req.difficulty or "medium",
        )
        result = {"exercises": exercises_data, "fallback": True}
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
        ex["id"] = e.id
    db.commit()

    return {
        "success": True,
        "exercise_ids": saved_ids,
        "count": len(saved_ids),
        "exercises": exercises_data,
        "meta": {
            "fast_mode": bool(req.fast_mode),
            "fallback": bool(result.get("fallback")),
        },
    }


def _fallback_exercises(
    fragments: List[str],
    knowledge_point: str,
    count: int,
    difficulty: str,
) -> List[dict]:
    """LLM 未返回可用题目时的本地兜底，保证学习流程不断。"""
    source = _clean_source_text("\n".join(fragments))[:1200]
    point = (knowledge_point or "核心知识").strip()
    summary = source[:220] or f"当前小节围绕 {point} 展开。"
    items = [
        {
            "question_type": "short",
            "difficulty": difficulty,
            "stem": f"请用自己的话解释“{point}”，并结合当前小节说明它的作用。",
            "options": [],
            "answer": f"围绕 {point} 的定义、适用条件和典型用途作答。",
            "explanation": summary,
            "mistake_tip": "不要只背关键词，要说明适用条件和与相近概念的区别。",
        },
        {
            "question_type": "fill",
            "difficulty": difficulty,
            "stem": f"填空：学习“{point}”时，需要同时关注定义、适用条件和______。",
            "options": [],
            "answer": "典型例题或易错点",
            "explanation": "知识点掌握不只看定义，还要能迁移到题目。",
            "mistake_tip": "容易只记结论，忽略条件。",
        },
        {
            "question_type": "judge",
            "difficulty": difficulty,
            "stem": f"判断：只要记住“{point}”的名称，就算掌握了该知识点。",
            "options": ["正确", "错误"],
            "answer": "错误",
            "explanation": "还需要理解含义、条件、公式或步骤，并能用于解题。",
            "mistake_tip": "概念学习要避免停留在名词层面。",
        },
    ]
    if _looks_like_physics(source):
        items.insert(
            1,
            {
                "question_type": "calc",
                "difficulty": difficulty,
                "stem": f"结合当前小节，写出“{point}”相关的一个基本公式，并说明每个量的含义。",
                "options": [],
                "answer": _first_formula(source) or "应写出当前小节中的核心公式，并解释符号含义。",
                "explanation": summary,
                "mistake_tip": "公式题要同时说明适用条件，不能只写等式。",
            },
        )
    while len(items) < count:
        idx = len(items) + 1
        items.append(
            {
                "question_type": "short",
                "difficulty": difficulty,
                "stem": f"结合资料片段，列出“{point}”相关的第 {idx} 个关键问题，并尝试回答。",
                "options": [],
                "answer": "答案应来自当前资料片段，并包含理由。",
                "explanation": source[:300],
                "mistake_tip": "回答时要回到资料原文，不要脱离上下文。",
            }
        )
    return items[:count]


def _clean_source_text(text: str) -> str:
    import re
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _infer_point_from_fragments(fragments: List[str]) -> str:
    import re
    text = _clean_source_text("\n".join(fragments))
    formulas = re.findall(r"[\u4e00-\u9fa5A-Za-z_ ]{0,12}[A-Za-z]\s*=\s*[^，。；;\n]{1,60}", text)
    if formulas:
        return formulas[0].strip()
    for token in ["受力分析", "牛顿运动定律", "质点运动学", "动能定理", "机械能守恒", "条件概率", "随机事件"]:
        if token in text:
            return token
    return text[:20] or "核心知识"


def _looks_like_physics(text: str) -> bool:
    return any(word in text for word in ["速度", "加速度", "力", "质量", "牛顿", "动能", "机械能", "F =", "v ="])


def _first_formula(text: str) -> str:
    import re
    match = re.search(r"([A-Za-z_][A-Za-z0-9_ ]*\s*=\s*[^，。；;\n]{1,80})", text)
    return match.group(1).strip() if match else ""


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
            "answer": ex.answer,
            "explanation": ex.explanation,
            "mistake_tip": ex.mistake_tip,
        },
    }


@router.post("/exercises/submit", summary="提交答案")
def submit_answer(req: SubmitAnswerRequest, db: Session = Depends(get_db)):
    """学生提交答案，触发错题诊断"""
    _ensure_user(req.user_id or "anonymous", db)
    ex = db.query(Exercise).filter(Exercise.id == req.exercise_id).first()
    if not ex:
        raise NotFoundError("题目")

    # 简单判题：客观题精确匹配；快速生成的开放题用轻量规则避免“永远判错”污染画像。
    student = req.student_answer.strip()
    answer = (ex.answer or "").strip()
    is_correct = False
    if ex.question_type in ("choice", "fill", "judge"):
        is_correct = _normalize_answer(student) == _normalize_answer(answer)
    elif ex.question_type in ("short", "calc", "proof", "code"):
        is_correct = _is_open_answer_acceptable(
            student_answer=student,
            standard_answer=answer,
            question_type=ex.question_type,
        )

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
        "explanation": ex.explanation,
        "mistake_tip": ex.mistake_tip,
        "diagnosis": diagnosis,
        "record_id": record.id,
        "added_to_mistakes": not is_correct,
    }


def _normalize_answer(text: str) -> str:
    import re
    return re.sub(r"\s+", "", (text or "").strip().lower())


def _is_open_answer_acceptable(
    student_answer: str,
    standard_answer: str,
    question_type: str,
) -> bool:
    normalized = _normalize_answer(student_answer)
    if len(normalized) < 8:
        return False
    if question_type == "calc" and "=" not in student_answer and not any(ch.isdigit() for ch in student_answer):
        return False
    if standard_answer:
        keywords = [
            token for token in _normalize_answer(standard_answer).replace("，", ",").split(",")
            if len(token) >= 2
        ]
        if keywords and any(token in normalized for token in keywords[:4]):
            return True
    return len(normalized) >= 18


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

    try:
        result = agent_service.homework_tutor(
            question=req.question,
            student_answer=req.student_answer,
            mode=req.mode,
            fragments=fragments,
            image_base64=req.image_base64,
        )
    except Exception:
        result = _local_homework_tutor(req.question, fragments, req.mode or "step_by_step")
    if not isinstance(result, dict) or not _has_tutor_content(result):
        result = _local_homework_tutor(req.question, fragments, req.mode or "step_by_step")
    return {"success": True, "tutoring": result}


def _has_tutor_content(result: dict) -> bool:
    for key in ("answer", "explanation", "final_answer", "content"):
        if str(result.get(key, "")).strip():
            return True
    steps = result.get("steps")
    return isinstance(steps, list) and any(str(step).strip() for step in steps)


def _local_homework_tutor(question: str, fragments: List[str], mode: str) -> dict:
    context = "\n".join([f for f in fragments if f])[:900]
    title = context.splitlines()[0] if context else "当前小节"
    if mode == "hint":
        steps = [
            "先定位题目问的是概念、公式还是例题步骤。",
            "回到当前小节，找定义、条件和关键公式。",
            "尝试用自己的话写出第一步，再继续追问。",
        ]
    else:
        steps = [
            "先看当前小节的核心内容。",
            "把问题和本节知识点对应起来。",
            "按定义、条件、例子或公式逐步解释。",
        ]
    return {
        "answer_status": "ok",
        "answer": f"你问的是：{question}。这和“{title}”相关。{context[:220] if context else '当前没有更多片段，可先补充具体问题。'}",
        "steps": steps,
        "mistake_tips": ["不要脱离当前章节上下文。", "如果涉及公式，要同时说明适用条件。"],
        "followups": ["这节最重要的概念是什么？", "给我一个例题", "这部分容易错在哪里？"],
    }


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
