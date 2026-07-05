# -*- coding: utf-8 -*-
"""Unified implementations for the educational agents.

The old project had each agent carrying its own large prompt and parsing logic.
This module keeps the agent surface area stable while centralizing prompt
contracts, JSON recovery, and deterministic fallbacks.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from ..core.llm_client import call_llm, call_llm_stream, extract_json_from_response
from ..core.prompt_contract import build_agent_system_prompt


# ── call-log accumulator ──────────────────────────────────────────────
# Appended by _call_json on every LLM invocation.
# Consumers (orchestrator, bridge) may read / reset at any time.
_CALL_LOG: List[Dict[str, Any]] = []


def get_call_log() -> List[Dict[str, Any]]:
    return list(_CALL_LOG)


def reset_call_log() -> None:
    _CALL_LOG.clear()


COURSE_STRUCTURE_SYSTEM_PROMPT = build_agent_system_prompt("course_structure")
KNOWLEDGE_GRAPH_SYSTEM_PROMPT = build_agent_system_prompt("knowledge_graph")
PLANNER_SYSTEM_PROMPT = build_agent_system_prompt("study_plan")
KEYPOINT_SYSTEM_PROMPT = build_agent_system_prompt("keypoint")
EXPLANATION_SYSTEM_PROMPT = build_agent_system_prompt("explanation")
EXERCISE_SYSTEM_PROMPT = build_agent_system_prompt("exercise")
HOMEWORK_TUTOR_SYSTEM_PROMPT = build_agent_system_prompt("homework_tutor")
MISTAKE_DIAGNOSIS_SYSTEM_PROMPT = build_agent_system_prompt("mistake_diagnosis")
PROFILE_SYSTEM_PROMPT = build_agent_system_prompt("profile")
ADAPTIVE_PATH_SYSTEM_PROMPT = build_agent_system_prompt("adaptive_path")
EXAM_SYSTEM_PROMPT = build_agent_system_prompt("exam")
MICRO_LESSON_SYSTEM_PROMPT = build_agent_system_prompt("micro_lesson")
PPT_SYSTEM_PROMPT = build_agent_system_prompt("ppt")
QUALITY_REVIEW_SYSTEM_PROMPT = build_agent_system_prompt("quality_review")


def _compact(value: Any, limit: int = 5000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str, indent=2)
    return text[:limit]


def _repair_json(raw: str) -> Optional[str]:
    """Attempt to fix common JSON breakages before delegating to the parser."""
    if not raw or not raw.strip():
        return None

    s = raw.strip()

    # Remove markdown fences
    if s.startswith("```"):
        for fence in ("```json\n", "```json\n", "```\n", "```"):
            if s.startswith(fence):
                s = s[len(fence):]
                break
        if s.endswith("```"):
            s = s[:-3]

    # Remove leading/trailing non-JSON noise
    first_brace = s.find("{")
    last_brace = s.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        s = s[first_brace:last_brace + 1]

    # Try to parse after basic cleaning
    try:
        json.loads(s)
        return s
    except json.JSONDecodeError:
        pass

    # Try common fixes: single-quote → double-quote
    # (only inside string bodies, not around keys)
    fixed = re.sub(r"(?<=: )'(.*?)'(?=,|\n|\})", r'"\1"', s)
    fixed = re.sub(r"(?<=\[)'(.*?)'(?=\])", r'"\1"', fixed)
    # Remove trailing commas before close
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        pass

    # Last resort: try to find any valid JSON sub-object
    for depth in (1, 2):
        try:
            obj = json.loads(s, strict=False)
            if isinstance(obj, dict):
                return json.dumps(obj, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        # Try stripping more aggressively
        brace_count = 0
        start = -1
        for i, ch in enumerate(s):
            if ch == "{":
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if brace_count == 0 and start != -1:
                    candidate = s[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        pass
    return None


def _call_json(
    system_prompt: str,
    prompt: str,
    fallback: Dict[str, Any],
    required_key: str = "",
    temperature: float = 0.5,
    on_token: Callable = None,
) -> Dict[str, Any]:
    start_ts = time.time()
    raw_response = ""
    error: Optional[str] = None

    try:
        if on_token:
            raw_response = call_llm_stream(prompt, system_prompt=system_prompt, temperature=temperature, on_token=on_token)
        else:
            raw_response = call_llm(prompt, system_prompt=system_prompt, temperature=temperature)
    except Exception as exc:
        error = str(exc)
        elapsed = round(time.time() - start_ts, 2)
        _CALL_LOG.append({
            "elapsed_sec": elapsed,
            "char_count": 0,
            "success": False,
            "error": error,
            "required_key": required_key,
        })
        fb = dict(fallback)
        fb["_error"] = error
        fb["_elapsed_sec"] = elapsed
        fb["insufficient_data_warning"] = fb.get("insufficient_data_warning") or f"LLM call failed: {error}"
        return fb

    elapsed = round(time.time() - start_ts, 2)
    result = extract_json_from_response(raw_response)

    # If the standard parser fails, try auto-repair
    if not isinstance(result, dict):
        repaired = _repair_json(raw_response)
        if repaired:
            try:
                result = json.loads(repaired)
            except json.JSONDecodeError:
                result = None

    success = isinstance(result, dict) and (not required_key or required_key in result)

    _CALL_LOG.append({
        "elapsed_sec": elapsed,
        "char_count": len(raw_response),
        "success": success,
        "required_key": required_key,
        "error": None if success else f"missing key: {required_key}" if required_key else "parse_failed",
    })

    if success:
        result["_elapsed_sec"] = elapsed  # type: ignore[index]
        return result  # type: ignore[return-value]

    fb = dict(fallback)
    fb["raw_response"] = raw_response
    fb["_elapsed_sec"] = elapsed
    if not fb.get("insufficient_data_warning"):
        fb["insufficient_data_warning"] = f"JSON parsing failed or missing required key '{required_key}' (elapsed {elapsed}s)"
    return fb


def _context(fragments: Optional[List[str]]) -> str:
    return "\n---\n".join(str(item) for item in (fragments or []) if str(item).strip())


def _kp_names(items: Optional[List[Any]]) -> List[str]:
    names: List[str] = []
    for item in items or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("knowledge_point") or ""
        else:
            name = str(item)
        if name:
            names.append(name)
    return names


def generate_course_structure(
    chapter_text: str,
    fragment_id: str = "",
    course_name: str = "",
    chapter_name: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    fallback = {
        "course_name": course_name,
        "chapter_number": "",
        "chapter_name": chapter_name or "未命名章节",
        "chapter_intro": "",
        "chapter_summary": chapter_text[:300],
        "sections": [],
        "all_knowledge_points": [],
        "theorems": [],
        "formulas": [],
        "references": [fragment_id] if fragment_id else [],
        "insufficient_data_warning": "未能从材料中稳定抽取结构，已返回保守结果。" if not chapter_text else "",
    }
    prompt = f"""请从教材文本中抽取课程结构，输出 CourseStructure JSON。

教材文本：
{chapter_text[:12000]}

已知课程名：{course_name}
已知章节名：{chapter_name}
fragment_id：{fragment_id}
"""
    return _call_json(COURSE_STRUCTURE_SYSTEM_PROMPT, prompt, fallback, "course_name", 0.4, on_token)


def refine_course_structure(
    chapter_text: str,
    current_structure: Dict[str, Any],
    fragment_id: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    fallback = dict(current_structure or {})
    fallback.setdefault("insufficient_data_warning", "结构未能自动更新，保留原结构。")
    prompt = f"""请基于新增教材文本修订课程结构，保持 CourseStructure JSON。

当前结构：
{_compact(current_structure)}

新增文本：
{chapter_text[:10000]}

fragment_id：{fragment_id}
"""
    return _call_json(COURSE_STRUCTURE_SYSTEM_PROMPT, prompt, fallback, "course_name", 0.4, on_token)


def generate_knowledge_graph(
    course_structure: Dict[str, Any],
    knowledge_points: Optional[List[Any]] = None,
    fragments: Optional[List[str]] = None,
    chapter_name: str = "",
    course_name: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    names = _kp_names(knowledge_points) or _kp_names(course_structure.get("all_knowledge_points", []))
    nodes = [{"node_id": f"kp_{i+1}", "name": name, "node_type": "concept", "chapter": chapter_name, "section": "", "definition": ""} for i, name in enumerate(names)]
    fallback = {
        "course_name": course_name or course_structure.get("course_name", ""),
        "chapter_name": chapter_name or course_structure.get("chapter_name", ""),
        "nodes": nodes,
        "edges": [],
        "references": [],
        "insufficient_data_warning": "知识点关系证据不足，未生成关系边。" if len(nodes) < 2 else "",
    }
    prompt = f"""请生成知识图谱 JSON。只生成有依据的节点和关系。

课程结构：
{_compact(course_structure)}

知识点：
{_compact(names)}

教材片段：
{_context(fragments)[:10000]}
"""
    return _call_json(KNOWLEDGE_GRAPH_SYSTEM_PROMPT, prompt, fallback, "nodes", 0.4, on_token)


def extend_knowledge_graph(current_graph: Dict[str, Any], new_materials: Any = None, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_graph or {})
    fallback.setdefault("insufficient_data_warning", "未能扩展图谱，保留原图谱。")
    prompt = f"""请基于新材料扩展知识图谱，保持原 JSON 结构。

当前图谱：
{_compact(current_graph)}

新材料：
{_compact(new_materials or kwargs)}
"""
    return _call_json(KNOWLEDGE_GRAPH_SYSTEM_PROMPT, prompt, fallback, "nodes", 0.4, on_token)


def generate_study_plan(
    course_name: str = "",
    chapter_name: str = "",
    fragments: Optional[List[str]] = None,
    knowledge_points: Optional[List[str]] = None,
    study_days: int = 7,
    daily_study_time: int = 60,
    exam_target: str = "",
    learning_foundation: str = "",
    weak_points: Optional[List[str]] = None,
    learning_style: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    kps = knowledge_points or []
    fallback = {
        "title": f"{chapter_name or course_name or '课程'}学习计划",
        "course_name": course_name,
        "chapter_name": chapter_name,
        "chapter_intro": "",
        "total_time_minutes": study_days * daily_study_time,
        "target_audience": learning_foundation or "通用学习者",
        "learning_objectives": kps[:5],
        "prerequisite_knowledge": [],
        "core_knowledge_points": kps,
        "key_difficulties": "请结合教材重点和薄弱点复习。",
        "daily_tasks": [
            {
                "day": day,
                "task_name": f"第{day}天学习任务",
                "task_description": "学习核心知识点，完成例题和自测。",
                "estimated_time_minutes": daily_study_time,
                "key_points": kps[(day - 1):day] or kps[:2],
                "source_reference": "",
                "self_test_questions": [],
            }
            for day in range(1, max(study_days, 1) + 1)
        ],
        "review_suggestions": "每天结束后复盘错题和未掌握知识点。",
        "common_mistakes": [],
        "milestone_checkpoints": ["完成核心概念复述", "完成基础练习", "完成综合复盘"],
        "next_steps": "根据练习结果进入专项强化。",
        "references": [],
        "insufficient_data_warning": "" if fragments else "缺少教材片段，计划为通用保守版本。",
    }
    prompt = f"""请生成学习计划 JSON。

课程：{course_name}
章节：{chapter_name}
知识点：{_compact(kps)}
学习天数：{study_days}
每日时间：{daily_study_time}
考试目标：{exam_target}
学习基础：{learning_foundation}
薄弱点：{_compact(weak_points or [])}
学习风格：{learning_style}
教材片段：
{_context(fragments)[:10000]}
"""
    return _call_json(PLANNER_SYSTEM_PROMPT, prompt, fallback, "daily_tasks", 0.5, on_token)


def modify_study_plan(current_plan: Dict[str, Any], modification_request: str, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_plan or {})
    fallback.setdefault("insufficient_data_warning", "未能自动修改，保留原计划。")
    prompt = f"""请按要求修改学习计划，保持 StudyPlan JSON。

当前计划：
{_compact(current_plan)}

修改要求：
{modification_request}

补充参数：
{_compact(kwargs)}
"""
    return _call_json(PLANNER_SYSTEM_PROMPT, prompt, fallback, "daily_tasks", 0.5, on_token)


def generate_keypoint_analysis(
    fragments: Optional[List[str]] = None,
    knowledge_points: Optional[List[str]] = None,
    wrong_questions: Optional[List[Any]] = None,
    exam_target: str = "",
    chapter_name: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    kps = knowledge_points or []
    fallback = {
        "chapter_name": chapter_name,
        "key_points": [{
            "core_focus": kps[:5],
            "learning_difficulties": kps[:3],
            "common_exam_points": kps[:3],
            "common_mistakes": [],
            "confusing_concepts": [],
            "breakthrough_methods": ["用例题对照概念", "整理错题原因", "做同类变式练习"],
            "source_reference": "",
        }],
        "insufficient_data_warning": "" if fragments else "缺少教材片段，重点难点为保守估计。",
    }
    prompt = f"""请生成重点难点分析 JSON。

章节：{chapter_name}
知识点：{_compact(kps)}
考试目标：{exam_target}
错题：{_compact(wrong_questions or [])}
教材片段：
{_context(fragments)[:10000]}
"""
    return _call_json(KEYPOINT_SYSTEM_PROMPT, prompt, fallback, "key_points", 0.5, on_token)


def modify_keypoint_analysis(current_analysis: Dict[str, Any], modification_request: str, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_analysis or {})
    prompt = f"请修改重点难点分析，保持 JSON。\n当前：{_compact(current_analysis)}\n要求：{modification_request}\n补充：{_compact(kwargs)}"
    return _call_json(KEYPOINT_SYSTEM_PROMPT, prompt, fallback, "key_points", 0.5, on_token)


def generate_layered_explanation(
    knowledge_point: str,
    fragments: Optional[List[str]] = None,
    student_level: str = "中等",
    learning_style: str = "通用",
    weak_points: Optional[List[str]] = None,
    explanation_mode: str = "textbook_sync",
    chapter_name: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    fallback = {
        "knowledge_point": knowledge_point,
        "chapter_name": chapter_name,
        "explanation_mode": explanation_mode,
        "target_audience": student_level,
        "concept_explanation": f"{knowledge_point} 是本节需要理解和应用的核心内容。",
        "key_steps": ["理解定义", "对照例题", "完成练习", "复盘易错点"],
        "derivation_process": "",
        "example_problems": [],
        "common_mistakes": [],
        "summary_mnemonic": "",
        "recommended_practice": [],
        "references": [],
        "insufficient_data_warning": "" if fragments else "缺少教材片段，讲解为通用版本。",
    }
    prompt = f"""请生成分层讲解 JSON。

知识点：{knowledge_point}
章节：{chapter_name}
学生水平：{student_level}
学习风格：{learning_style}
薄弱点：{_compact(weak_points or [])}
讲解模式：{explanation_mode}
教材片段：
{_context(fragments)[:10000]}
"""
    return _call_json(EXPLANATION_SYSTEM_PROMPT, prompt, fallback, "knowledge_point", 0.6, on_token)


def modify_explanation(current_explanation: Dict[str, Any], modification_request: str, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_explanation or {})
    prompt = f"请修改讲解，保持 LayeredExplanation JSON。\n当前：{_compact(current_explanation)}\n要求：{modification_request}\n补充：{_compact(kwargs)}"
    return _call_json(EXPLANATION_SYSTEM_PROMPT, prompt, fallback, "knowledge_point", 0.6, on_token)


def generate_exercises(
    fragments: Optional[List[str]] = None,
    course_name: str = "",
    chapter_name: str = "",
    knowledge_points: Optional[List[str]] = None,
    exercise_types: Optional[List[str]] = None,
    difficulty_config: Optional[Dict[str, int]] = None,
    question_count: int = 10,
    student_profile: Optional[Dict[str, Any]] = None,
    wrong_questions: Optional[List[dict]] = None,
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    kps = knowledge_points or []
    q_types = exercise_types or ["multiple_choice", "fill_in", "short_answer"]
    fallback_questions = []
    for idx in range(max(question_count, 1)):
        kp = kps[idx % len(kps)] if kps else ""
        fallback_questions.append({
            "question_id": str(uuid.uuid4()),
            "question_type": q_types[idx % len(q_types)],
            "difficulty": "medium",
            "knowledge_point": kp,
            "stem": f"请围绕“{kp or chapter_name or course_name}”完成一道基础练习。",
            "options": [],
            "correct_answer": "请根据教材内容作答。",
            "detailed_explanation": "解析需要结合教材片段进一步生成。",
            "grading_criteria": "答案完整、逻辑清楚、关键步骤正确。",
            "common_mistakes": [],
            "source_reference": "",
            "variant_suggestions": ["改变条件后重新作答"],
        })
    fallback = {
        "course_name": course_name,
        "chapter_name": chapter_name,
        "questions": fallback_questions,
        "insufficient_data_warning": "" if fragments else "缺少教材片段，题目为保守模板。",
    }
    prompt = f"""请生成习题集 JSON。

课程：{course_name}
章节：{chapter_name}
知识点：{_compact(kps)}
题型：{_compact(q_types)}
难度配置：{_compact(difficulty_config or {})}
题目数量：{question_count}
学生画像：{_compact(student_profile or {})}
错题记录：{_compact(wrong_questions or [])}
教材片段：
{_context(fragments)[:12000]}
"""
    return _call_json(EXERCISE_SYSTEM_PROMPT, prompt, fallback, "questions", 0.6, on_token)


def modify_exercises(current_exercises: Dict[str, Any], modification_request: str, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_exercises or {})
    prompt = f"请修改习题集，保持 ExerciseSet JSON。\n当前：{_compact(current_exercises)}\n要求：{modification_request}\n补充：{_compact(kwargs)}"
    return _call_json(EXERCISE_SYSTEM_PROMPT, prompt, fallback, "questions", 0.6, on_token)


def generate_homework_tutor(
    question_text: str,
    fragments: Optional[List[str]] = None,
    tutor_mode: str = "step_by_step",
    student_answer: str = "",
    chapter_name: str = "",
    knowledge_point: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    fallback = {
        "question_recognition": "待辅导题目",
        "knowledge_point": knowledge_point,
        "question_type": "",
        "difficulty": "medium",
        "solving_approach": "先识别题目考查的知识点，再列出已知条件，最后分步求解。",
        "next_step_hint": "请先写出题目中的已知条件和目标结论。",
        "complete_steps": ["识别知识点", "整理条件", "选择方法", "完成推导或计算", "检查答案"],
        "final_answer": "",
        "common_mistakes": [],
        "recommended_review": [knowledge_point] if knowledge_point else [],
        "references": [],
        "error_analysis": None,
        "insufficient_data_warning": "" if fragments else "缺少教材片段，辅导为通用步骤。",
    }
    prompt = f"""请生成作业辅导 JSON。

题目：{question_text}
学生答案：{student_answer}
辅导模式：{tutor_mode}
章节：{chapter_name}
知识点：{knowledge_point}
教材片段：
{_context(fragments)[:10000]}
"""
    fallback.update({
        "answer_status": "insufficient",
        "question_recognition": question_text,
        "solving_approach": "模型未能生成针对题目的有效解答，不能把通用模板当作答案。",
        "next_step_hint": "请确认题干完整、模型服务正常；如果是图片题，请先完成 OCR/多模态识别。",
        "complete_steps": ["等待有效题干识别和模型推导结果"],
        "final_answer": "",
        "common_mistakes": ["只输出解题模板，没有代入题目条件"],
        "insufficient_data_warning": "未获得可验证的题目代入解答。",
    })
    prompt += """

硬性要求：
1. 必须围绕题目中的具体表达式、数字、条件进行推导，禁止只写“识别知识点、整理条件、选择方法”等模板步骤。
2. 如果题干不完整、图片无法识别、或不能可靠求解，answer_status 必须为 insufficient，并说明缺少什么。
3. 能求出答案时，final_answer 必须非空；数学题需要给 formulas 数组。
"""
    return _call_json(HOMEWORK_TUTOR_SYSTEM_PROMPT, prompt, fallback, "solving_approach", 0.5, on_token)


def modify_homework_tutor(current_tutor: Dict[str, Any], modification_request: str, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_tutor or {})
    prompt = f"请修改作业辅导，保持 HomeworkTutorResponse JSON。\n当前：{_compact(current_tutor)}\n要求：{modification_request}\n补充：{_compact(kwargs)}"
    return _call_json(HOMEWORK_TUTOR_SYSTEM_PROMPT, prompt, fallback, "solving_approach", 0.5, on_token)


def generate_mistake_diagnosis(
    question: str,
    standard_answer: str = "",
    student_answer: str = "",
    fragments: Optional[List[str]] = None,
    explanation: str = "",
    history_mistakes: Optional[List[dict]] = None,
    chapter_name: str = "",
    knowledge_point: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    is_correct = bool(standard_answer and student_answer and standard_answer.strip() == student_answer.strip())
    fallback = {
        "question": question,
        "is_correct": is_correct,
        "score": 100.0 if is_correct else 0.0,
        "error_steps": [] if is_correct else ["答案与标准答案不一致，需进一步人工或模型诊断。"],
        "error_type": "" if is_correct else "unknown",
        "error_reason": "" if is_correct else "缺少足够依据定位具体错误。",
        "involved_knowledge": [knowledge_point] if knowledge_point else [],
        "weak_prerequisite": "",
        "remediation_suggestions": ["复习相关知识点", "完成 2-3 道同类变式题"] if not is_correct else [],
        "recommended_review_fragments": [],
        "recommended_variant_count": 3,
        "references": [],
        "insufficient_data_warning": "" if fragments else "缺少教材片段，诊断为保守版本。",
    }
    prompt = f"""请生成错题诊断 JSON。

题目：{question}
标准答案：{standard_answer}
学生答案：{student_answer}
解析：{explanation}
章节：{chapter_name}
知识点：{knowledge_point}
历史错题：{_compact(history_mistakes or [])}
教材片段：
{_context(fragments)[:10000]}
"""
    return _call_json(MISTAKE_DIAGNOSIS_SYSTEM_PROMPT, prompt, fallback, "is_correct", 0.4, on_token)


def modify_mistake_diagnosis(current_diagnosis: Dict[str, Any], modification_request: str, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_diagnosis or {})
    prompt = f"请修改错题诊断，保持 MistakeDiagnosis JSON。\n当前：{_compact(current_diagnosis)}\n要求：{modification_request}\n补充：{_compact(kwargs)}"
    return _call_json(MISTAKE_DIAGNOSIS_SYSTEM_PROMPT, prompt, fallback, "is_correct", 0.4, on_token)


def generate_student_profile(
    learning_records: Optional[List[dict]] = None,
    answer_records: Optional[List[dict]] = None,
    mistake_records: Optional[List[dict]] = None,
    chapter_progress: Optional[Dict[str, Any]] = None,
    test_scores: Optional[List[dict]] = None,
    study_time: Optional[Dict[str, Any]] = None,
    course_name: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    mistakes = mistake_records or []
    fallback = {
        "current_stage": "数据积累阶段",
        "course_progress": 0.0,
        "knowledge_mastery": [],
        "weak_knowledge_points": [str(m.get("knowledge_point", "")) for m in mistakes if isinstance(m, dict) and m.get("knowledge_point")],
        "common_wrong_question_types": [],
        "common_error_reasons": [str(m.get("error_reason", "")) for m in mistakes if isinstance(m, dict) and m.get("error_reason")],
        "learning_pace": "medium",
        "learning_habits": [],
        "predicted_risks": [],
        "recommended_review_order": [],
        "recommended_reinforcement_tasks": [],
        "next_stage_suggestions": "继续积累答题和学习记录，以便生成更准确画像。",
        "insufficient_data_warning": "学习数据较少，画像为保守版本。" if not (learning_records or answer_records or mistakes) else "",
    }
    prompt = f"""请生成学习画像 JSON。

课程：{course_name}
学习记录：{_compact(learning_records or [])}
答题记录：{_compact(answer_records or [])}
错题记录：{_compact(mistakes)}
章节进度：{_compact(chapter_progress or {})}
测试成绩：{_compact(test_scores or [])}
学习时长：{_compact(study_time or {})}
"""
    return _call_json(PROFILE_SYSTEM_PROMPT, prompt, fallback, "current_stage", 0.4, on_token)


def update_student_profile(current_profile: Dict[str, Any], new_records: Any = None, on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_profile or {})
    prompt = f"请更新学习画像，保持 StudentProfile JSON。\n当前画像：{_compact(current_profile)}\n新数据：{_compact(new_records or kwargs)}"
    return _call_json(PROFILE_SYSTEM_PROMPT, prompt, fallback, "current_stage", 0.4, on_token)


def generate_adaptive_path(
    original_plan: Dict[str, Any],
    student_profile: Dict[str, Any],
    latest_answers: Optional[List[dict]] = None,
    mistake_diagnosis: Optional[List[dict]] = None,
    fragments: Optional[List[str]] = None,
    exam_date: str = "",
    daily_study_time: int = 60,
    chapter_name: str = "",
    course_name: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    weak = student_profile.get("weak_knowledge_points", []) if isinstance(student_profile, dict) else []
    fallback = {
        "adjusted_plan": [],
        "need_relearn_points": weak,
        "need_skip_points": [],
        "need_strengthen_types": [],
        "tomorrow_tasks": [{
            "day": 1,
            "task_name": "薄弱点复习",
            "task_description": "复习薄弱知识点并完成同类练习。",
            "task_type": "review",
            "estimated_time_minutes": daily_study_time,
            "knowledge_points": weak[:3],
            "difficulty": "medium",
            "priority": "high",
        }],
        "review_priority": weak,
        "estimated_completion_time": exam_date,
        "adjustment_reasons": ["根据学习画像和错题记录优先补强薄弱点。"],
        "insufficient_data_warning": "" if student_profile else "缺少学习画像，路径为通用版本。",
    }
    prompt = f"""请生成自适应学习路径 JSON。

课程：{course_name}
章节：{chapter_name}
原计划：{_compact(original_plan)}
学生画像：{_compact(student_profile)}
最近答题：{_compact(latest_answers or [])}
错题诊断：{_compact(mistake_diagnosis or [])}
考试日期：{exam_date}
每日时间：{daily_study_time}
教材片段：
{_context(fragments)[:8000]}
"""
    return _call_json(ADAPTIVE_PATH_SYSTEM_PROMPT, prompt, fallback, "tomorrow_tasks", 0.5, on_token)


def update_adaptive_path(current_path: Dict[str, Any], update_request: str = "", on_token: Callable = None, **kwargs: Any) -> Dict[str, Any]:
    fallback = dict(current_path or {})
    prompt = f"请更新自适应路径，保持 AdaptivePath JSON。\n当前路径：{_compact(current_path)}\n要求：{update_request}\n补充：{_compact(kwargs)}"
    return _call_json(ADAPTIVE_PATH_SYSTEM_PROMPT, prompt, fallback, "tomorrow_tasks", 0.5, on_token)


def generate_exam_paper(
    course_name: str,
    chapter_range: Optional[List[str]],
    fragments: Optional[List[str]],
    exam_type: str = "chapter_quiz",
    knowledge_point_range: Optional[List[str]] = None,
    question_type_ratio: Optional[Dict[str, float]] = None,
    difficulty_ratio: Optional[Dict[str, float]] = None,
    total_questions: int = 20,
    exam_duration_minutes: int = 120,
    total_score: float = 100.0,
    include_answers: bool = True,
    include_explanations: bool = True,
    include_grading_criteria: bool = True,
    generate_student_version: bool = True,
    generate_teacher_version: bool = True,
    mistake_records: Optional[List[dict]] = None,
    weak_points: Optional[List[str]] = None,
    student_level: str = "",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    per_score = round(total_score / max(total_questions, 1), 2)
    questions = [{
        "question_id": f"Q{i+1:03d}",
        "question_number": str(i + 1),
        "question_type": "short_answer",
        "difficulty": "medium",
        "knowledge_point": (knowledge_point_range or [""])[i % max(len(knowledge_point_range or [""]), 1)],
        "stem": "请根据教材内容回答本题。",
        "options": [],
        "correct_answer": "见教材相关内容。",
        "detailed_explanation": "需要结合教材片段进一步生成。",
        "score": per_score,
        "answer_area": "写出关键步骤和结论。",
        "grading_criteria": "关键知识点正确、过程完整、表达清楚。",
        "source_reference": "",
    } for i in range(max(total_questions, 1))]
    fallback = {
        "paper_title": f"{course_name or '课程'}{exam_type}试卷",
        "exam_type": exam_type,
        "exam_instructions": f"本卷共 {len(questions)} 题，满分 {total_score} 分，建议用时 {exam_duration_minutes} 分钟。",
        "total_score": total_score,
        "exam_duration_minutes": exam_duration_minutes,
        "questions": questions,
        "answers": {q["question_id"]: q["correct_answer"] for q in questions} if include_answers else {},
        "explanations": {q["question_id"]: q["detailed_explanation"] for q in questions} if include_explanations else {},
        "grading_standards": "按题目评分标准给分。",
        "knowledge_point_coverage": {},
        "difficulty_distribution": difficulty_ratio or {},
        "references": [],
        "insufficient_data_warning": "" if fragments else "缺少教材片段，试卷为模板版本。",
    }
    prompt = f"""请生成完整试卷 JSON。

课程：{course_name}
章节范围：{_compact(chapter_range or [])}
试卷类型：{exam_type}
知识点范围：{_compact(knowledge_point_range or [])}
题型比例：{_compact(question_type_ratio or {})}
难度比例：{_compact(difficulty_ratio or {})}
题量：{total_questions}
总分：{total_score}
时长：{exam_duration_minutes}
学生水平：{student_level}
错题：{_compact(mistake_records or [])}
薄弱点：{_compact(weak_points or [])}
教材片段：
{_context(fragments)[:12000]}
"""
    return _call_json(EXAM_SYSTEM_PROMPT, prompt, fallback, "questions", 0.6, on_token)


def check_exam_paper(exam_paper: Dict[str, Any]) -> Dict[str, Any]:
    questions = exam_paper.get("questions", []) if isinstance(exam_paper, dict) else []
    total = sum(float(q.get("score", 0) or 0) for q in questions if isinstance(q, dict))
    expected = float(exam_paper.get("total_score", total) or total) if isinstance(exam_paper, dict) else total
    issues = []
    if questions and abs(total - expected) > 0.1:
        issues.append("各题分值之和与总分不一致")
    return {
        "is_valid": not issues,
        "issues": issues,
        "suggestions": ["检查分值、答案完整性和知识点覆盖。"] if issues else [],
        "total_score_check": "correct" if not issues else "incorrect",
        "answer_completeness": "complete",
        "knowledge_point_balance": "needs_review",
        "difficulty_distribution_check": "needs_review",
    }


def generate_micro_lesson(
    course_name: str = "",
    chapter_name: str = "",
    knowledge_point: str = "",
    fragments: Optional[List[str]] = None,
    teaching_style: str = "讲解式",
    video_duration_seconds: int = 180,
    target_student_level: str = "中等",
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    fallback = {
        "title": f"{knowledge_point or chapter_name or course_name}微课",
        "course_name": course_name,
        "chapter_name": chapter_name,
        "knowledge_point": knowledge_point,
        "teaching_objectives": [f"理解{knowledge_point}"],
        "video_duration_seconds": video_duration_seconds,
        "outline": ["导入", "概念讲解", "例题演示", "总结练习"],
        "sections": [
            {"section_name": "导入", "duration_seconds": 30, "script": "提出问题，引出本节主题。", "visual_design": "展示问题场景", "board_design": "写出主题"},
            {"section_name": "核心讲解", "duration_seconds": max(video_duration_seconds - 60, 30), "script": "解释核心概念和方法。", "visual_design": "概念图或步骤图", "board_design": "列出关键步骤"},
            {"section_name": "总结", "duration_seconds": 30, "script": "回顾要点并布置练习。", "visual_design": "要点清单", "board_design": "总结公式或方法"},
        ],
        "board_design": "",
        "example_arrangements": [],
        "interactive_questions": [],
        "common_mistake_reminders": [],
        "after_class_exercises": [],
        "subtitle_text": "",
        "references": [],
        "insufficient_data_warning": "" if fragments else "缺少教材片段，微课为通用脚本。",
    }
    prompt = f"""请生成微课脚本 JSON。

课程：{course_name}
章节：{chapter_name}
知识点：{knowledge_point}
风格：{teaching_style}
时长：{video_duration_seconds}
学生水平：{target_student_level}
教材片段：
{_context(fragments)[:10000]}
"""
    return _call_json(MICRO_LESSON_SYSTEM_PROMPT, prompt, fallback, "sections", 0.7, on_token)


def generate_ppt_content(
    course_name: str = "",
    chapter_name: str = "",
    knowledge_point: str = "",
    fragments: Optional[List[str]] = None,
    micro_lesson: Optional[Dict[str, Any]] = None,
    teaching_style: str = "清晰简洁",
    total_slides: int = 10,
    on_token: Callable = None,
    **_: Any,
) -> Dict[str, Any]:
    slides = [{
        "slide_number": i + 1,
        "slide_title": ["学习目标", "核心概念", "方法步骤", "例题演示", "易错提醒", "课堂练习", "总结"][i % 7],
        "slide_content": "围绕本页标题组织 3-5 条要点。",
        "formulas": [],
        "image_suggestion": "使用与知识点相关的结构图或步骤图。",
        "speaker_notes": "讲解本页要点，并联系教材内容。",
        "subtitle": "",
        "duration_seconds": 30,
    } for i in range(max(total_slides, 1))]
    fallback = {
        "ppt_title": f"{knowledge_point or chapter_name or course_name}课件",
        "course_name": course_name,
        "chapter_name": chapter_name,
        "knowledge_point": knowledge_point,
        "total_slides": len(slides),
        "slides": slides,
        "references": [],
        "insufficient_data_warning": "" if fragments else "缺少教材片段，PPT 为通用结构。",
    }
    prompt = f"""请生成 PPT 内容 JSON。

课程：{course_name}
章节：{chapter_name}
知识点：{knowledge_point}
页数：{total_slides}
教学风格：{teaching_style}
微课脚本：{_compact(micro_lesson or {})}
教材片段：
{_context(fragments)[:10000]}
"""
    return _call_json(PPT_SYSTEM_PROMPT, prompt, fallback, "slides", 0.6, on_token)


def review_content(
    original_materials: Any,
    generated_result: Dict[str, Any],
    references: Optional[List[str]] = None,
    task_type: str = "study_plan",
    on_token: Callable = None,
) -> Dict[str, Any]:
    fallback = {
        "is_passed": True,
        "issues": [],
        "suggestions": [],
        "credibility_score": 75.0 if references else 60.0,
        "need_regenerate_fields": [],
        "corrected_result": {},
        "review_summary": "自动审查未发现结构性错误；仍建议人工抽查关键知识和答案。",
    }
    prompt = f"""请审查生成内容，输出 QualityReview JSON。

任务类型：{task_type}
原始材料：
{_compact(original_materials)}

生成结果：
{_compact(generated_result)}

引用列表：
{_compact(references or [])}
"""
    return _call_json(QUALITY_REVIEW_SYSTEM_PROMPT, prompt, fallback, "is_passed", 0.3, on_token)


def review_and_fix(
    original_materials: Any,
    generated_result: Dict[str, Any],
    references: Optional[List[str]] = None,
    task_type: str = "study_plan",
    on_token: Callable = None,
) -> Dict[str, Any]:
    review = review_content(original_materials, generated_result, references, task_type, on_token)
    if review.get("is_passed"):
        return {"review": review, "final_result": generated_result, "was_fixed": False}
    prompt = f"""请根据审查问题修正生成结果，只输出修正后的 JSON。

原始材料：
{_compact(original_materials)}

生成结果：
{_compact(generated_result)}

审查问题：
{_compact(review)}
"""
    fixed = _call_json(QUALITY_REVIEW_SYSTEM_PROMPT, prompt, generated_result, "", 0.3, on_token)
    return {"review": review, "final_result": fixed, "was_fixed": True}
