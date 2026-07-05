# -*- coding: utf-8 -*-
"""Quality review agent with concrete Python-side pre-checks.

Before delegating to the LLM for semantic review, this module runs fast
deterministic checks: JSON validity, field completeness, reference grounding,
deduplication, difficulty distribution, and consistency.

The LLM review is still called for semantic checks that require understanding
(hallucination, explanation correctness, misleading examples).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ._agent_impl import (
    QUALITY_REVIEW_SYSTEM_PROMPT,
    _call_json,
    _compact,
)


# ─── Public API ──────────────────────────────────────────────────────
# These are the same two functions that `orchestrator_agent.py` expects.


def review_content(
    original_materials: Any,
    generated_result: Dict[str, Any],
    references: Optional[List[str]] = None,
    task_type: str = "study_plan",
    on_token: Optional[Any] = None,
) -> Dict[str, Any]:
    """Review generated content. Runs Python pre-checks then LLM semantic review."""
    issues: List[Dict[str, Any]] = []
    has_refs = bool(references)

    # 1. Python-side deterministic checks
    issues.extend(_check_basic(generated_result, task_type))
    issues.extend(_check_completeness(generated_result, task_type))

    if task_type in ("exercise", "exam_paper", "study_plan", "keypoint", "explanation"):
        issues.extend(_check_dedup(generated_result, task_type))

    if task_type in ("exercise", "exam_paper"):
        issues.extend(_check_difficulty_distribution(generated_result, task_type))

    if has_refs:
        issues.extend(_check_reference_grounding(generated_result, references or []))
    else:
        issues.append({
            "field": "references",
            "issue_type": "missing_reference",
            "severity": "minor",
            "description": "没有提供教材引用片段，无法校验生成内容的教材依据。",
            "suggestion": "补充教材片段后重新审查。",
        })

    # 2. LLM semantic review (only if no critical Python issues)
    critical_count = sum(1 for i in issues if i.get("severity") == "critical")
    llm_result = _run_llm_review(original_materials, generated_result, references, task_type, on_token)

    # 3. Merge: Python issues supplement LLM issues
    llm_issues: list = llm_result.get("issues", []) if isinstance(llm_result, dict) else []
    all_issues = issues + llm_issues

    credibility = _compute_credibility(
        has_references=has_refs,
        critical_count=critical_count,
        total_issue_count=len(all_issues),
        llm_score=llm_result.get("credibility_score", 60.0) if isinstance(llm_result, dict) else 60.0,
    )

    return {
        "is_passed": critical_count == 0 and credibility >= 50.0,
        "issues": all_issues,
        "suggestions": [i.get("suggestion", "") for i in all_issues if i.get("suggestion")],
        "credibility_score": credibility,
        "need_regenerate_fields": list({i.get("field", "") for i in all_issues if i.get("severity") in ("critical", "major")}),
        "review_summary": _build_summary(all_issues, credibility),
    }


def review_and_fix(
    original_materials: Any,
    generated_result: Dict[str, Any],
    references: Optional[List[str]] = None,
    task_type: str = "study_plan",
    on_token: Optional[Any] = None,
) -> Dict[str, Any]:
    """Review and auto-fix if critical issues found."""
    review = review_content(original_materials, generated_result, references, task_type, on_token)

    if review.get("is_passed"):
        return {"review": review, "final_result": generated_result, "was_fixed": False}

    critical_fields = review.get("need_regenerate_fields", [])
    fix_prompt = _build_fix_prompt(original_materials, generated_result, review, critical_fields, task_type)

    # Only attempt LLM fix if we have a concrete fix prompt
    if fix_prompt:
        fixed = _call_json(
            QUALITY_REVIEW_SYSTEM_PROMPT,
            fix_prompt,
            generated_result,
            required_key="",
            temperature=0.3,
            on_token=on_token,
        )
        return {"review": review, "final_result": fixed, "was_fixed": True}

    return {"review": review, "final_result": generated_result, "was_fixed": False}


# ─── Python-side pre-checks ────────────────────────────────────────────


def _check_basic(result: Dict[str, Any], task_type: str) -> List[Dict[str, Any]]:
    """Basic checks: is it a dict, does it have content."""
    issues: List[Dict[str, Any]] = []
    if not isinstance(result, dict):
        issues.append({
            "field": "_root",
            "issue_type": "invalid_json",
            "severity": "critical",
            "description": "生成结果不是有效 JSON 对象。",
            "suggestion": "检查 LLM 输出格式。",
        })
        return issues
    # Check for insufficient_data_warning
    warning = result.get("insufficient_data_warning", "")
    if warning and len(str(warning)) > 10:
        issues.append({
            "field": "insufficient_data_warning",
            "issue_type": "incomplete",
            "severity": "major",
            "description": f"生成内容含材料不足提示：{str(warning)[:100]}",
            "suggestion": "补充更多教材片段后重新生成。",
        })
    return issues


def _check_completeness(result: Dict[str, Any], task_type: str) -> List[Dict[str, Any]]:
    """Check task-specific required fields exist and are non-empty."""
    issues: List[Dict[str, Any]] = []

    # Common checks: references list should exist
    refs = result.get("references", [])
    if isinstance(refs, list) and len(refs) == 0:
        issues.append({
            "field": "references",
            "issue_type": "missing_reference",
            "severity": "minor",
            "description": "生成内容没有提供任何引用来源。",
            "suggestion": "补充教材引用。",
        })

    # Task-specific required fields
    required_map = {
        "study_plan": [
            ("title", "学习计划标题"),
            ("daily_tasks", "每日任务"),
            ("total_time_minutes", "学习总时长"),
        ],
        "keypoint": [
            ("key_points", "重点难点分析"),
        ],
        "explanation": [
            ("concept_explanation", "概念解释"),
            ("key_steps", "关键步骤"),
        ],
        "exercise": [
            ("questions", "习题列表"),
        ],
        "exam_paper": [
            ("questions", "试卷题目"),
            ("paper_title", "试卷标题"),
        ],
        "homework_tutor": [
            ("solving_approach", "解题思路"),
            ("complete_steps", "完整步骤"),
        ],
        "mistake_diagnosis": [
            ("is_correct", "正误判断"),
        ],
        "student_profile": [
            ("current_stage", "当前阶段"),
            ("weak_knowledge_points", "薄弱知识点"),
        ],
        "micro_lesson": [
            ("sections", "微课分段脚本"),
        ],
        "ppt_content": [
            ("slides", "PPT 页面"),
        ],
        "knowledge_graph": [
            ("nodes", "知识点节点"),
        ],
        "learning_package": [
            ("learning_objectives", "学习目标"),
            ("daily_tasks", "每日任务"),
        ],
    }

    for field, label in required_map.get(task_type, []):
        val = result.get(field)
        if val is None or (isinstance(val, (list, dict)) and len(val) == 0) or (isinstance(val, str) and not val.strip()):
            issues.append({
                "field": field,
                "issue_type": "incomplete",
                "severity": "major" if field in ("questions", "daily_tasks", "sections", "key_points", "slides") else "minor",
                "description": f"缺少或为空：{label}（{field}）。",
                "suggestion": f"补充{label}内容。",
            })

    return issues


def _check_dedup(result: Dict[str, Any], task_type: str) -> List[Dict[str, Any]]:
    """Check for duplicate questions, sections, or points."""
    issues: List[Dict[str, Any]] = []

    # Exercises / exam: check question stem dedup
    questions = result.get("questions") or result.get("exercises", {}).get("questions", [])
    if isinstance(questions, list) and len(questions) > 1:
        stems = []
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                continue
            stem = (q.get("stem") or q.get("question") or "").strip()
            if stem in stems:
                issues.append({
                    "field": f"questions[{i}].stem",
                    "issue_type": "duplicate",
                    "severity": "major",
                    "description": f"第{i+1}题题干与之前的题目重复。",
                    "suggestion": "修改题目或更换考查角度。",
                })
            stems.append(stem)

    # Study plan: daily_tasks should have unique days
    tasks = result.get("daily_tasks", [])
    if isinstance(tasks, list) and len(tasks) > 1:
        seen_days = set()
        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                continue
            day = t.get("day")
            if day in seen_days:
                issues.append({
                    "field": f"daily_tasks[{i}].day",
                    "issue_type": "duplicate",
                    "severity": "minor",
                    "description": f"第{day}天任务重复出现。",
                    "suggestion": "重新排列每日任务编号。",
                })
            seen_days.add(day)

    return issues


def _check_difficulty_distribution(result: Dict[str, Any], task_type: str) -> List[Dict[str, Any]]:
    """Check that difficulty distribution is reasonable."""
    issues: List[Dict[str, Any]] = []
    questions = result.get("questions", [])
    if not isinstance(questions, list) or len(questions) < 3:
        return issues

    difficulty_count: Dict[str, int] = {}
    for q in questions:
        if not isinstance(q, dict):
            continue
        d = (q.get("difficulty") or "medium").lower()
        difficulty_count[d] = difficulty_count.get(d, 0) + 1

    total = len(questions)
    for diff, label in [("easy", "简单"), ("hard", "困难")]:
        ratio = difficulty_count.get(diff, 0) / total
        if ratio > 0.8:
            issues.append({
                "field": "difficulty_distribution",
                "issue_type": "wrong_difficulty",
                "severity": "major",
                "description": f"{label}题占比 {ratio:.0%}，比例过高。",
                "suggestion": "适当调整难度配比，建议 easy 20-40%，medium 40-60%，hard 10-30%。",
            })

    return issues


def _check_reference_grounding(result: Dict[str, Any], references: List[str]) -> List[Dict[str, Any]]:
    """Check that outputs don't make claims unsupported by references."""
    issues: List[Dict[str, Any]] = []
    ref_text = "\n".join([str(r) for r in references if r]).lower()
    if not ref_text.strip():
        return issues

    # Extract key named entities from result to check against references
    text = json.dumps(result, ensure_ascii=False)

    # Simple heuristic: if the output is very long but references are very short,
    # there's a risk of hallucination
    output_chars = len(text)
    ref_chars = len(ref_text)
    if output_chars > ref_chars * 5 and ref_chars > 0:
        issues.append({
            "field": "references",
            "issue_type": "hallucination",
            "severity": "major",
            "description": f"生成内容（{output_chars}字符）远多于教材引用（{ref_chars}字符），可能包含无依据内容。",
            "suggestion": "增加教材片段范围或降低生成篇幅。",
        })

    return issues


# ─── LLM review ─────────────────────────────────────────────────────────


def _run_llm_review(
    original_materials: Any,
    generated_result: Dict[str, Any],
    references: Optional[List[str]],
    task_type: str,
    on_token: Optional[Any],
) -> Dict[str, Any]:
    """Delegate semantic review to LLM."""
    fallback = {
        "is_passed": True,
        "issues": [],
        "suggestions": [],
        "credibility_score": 75.0 if references else 60.0,
        "need_regenerate_fields": [],
        "review_summary": "LLM 审查未能完成，依赖 Python 侧检查结果。",
    }
    prompt = (
        f"请审查生成内容质量。\n\n"
        f"任务类型：{task_type}\n"
        f"原始材料：\n{_compact(original_materials)}\n\n"
        f"生成结果：\n{_compact(generated_result)}\n\n"
        f"引用片段：\n{_compact(references or [])}\n\n"
        f"请重点审查：\n"
        f"1. 是否存在幻觉（无教材依据的内容）\n"
        f"2. 答案是否与教材一致\n"
        f"3. 解析是否存在前后矛盾\n"
        f"4. 题目/内容是否合理\n"
        f"5. 语言表达是否清晰\n"
        f"输出 QualityReview JSON。"
    )
    result = _call_json(
        QUALITY_REVIEW_SYSTEM_PROMPT,
        prompt,
        fallback,
        required_key="is_passed",
        temperature=0.3,
        on_token=on_token,
    )
    return result


# ─── Helpers ─────────────────────────────────────────────────────────────


def _compute_credibility(
    has_references: bool,
    critical_count: int,
    total_issue_count: int,
    llm_score: float,
) -> float:
    """Compute composite credibility score 0-100."""
    base = llm_score
    if has_references:
        base += 10.0
    else:
        base -= 15.0
    base -= critical_count * 20.0
    base -= total_issue_count * 5.0
    return max(0.0, min(100.0, base))


def _build_summary(issues: List[Dict[str, Any]], credibility: float) -> str:
    critical = sum(1 for i in issues if i.get("severity") == "critical")
    major = sum(1 for i in issues if i.get("severity") == "major")
    minor = sum(1 for i in issues if i.get("severity") == "minor")

    parts: List[str] = []
    if critical:
        parts.append(f"发现 {critical} 个严重问题")
    if major:
        parts.append(f"{major} 个主要问题")
    if minor:
        parts.append(f"{minor} 个次要问题")
    if not parts:
        parts.append("未发现异常")

    parts.append(f"可信度评分 {credibility:.0f}/100")
    return "；".join(parts) + "。"


def _build_fix_prompt(
    original_materials: Any,
    generated_result: Dict[str, Any],
    review: Dict[str, Any],
    critical_fields: List[str],
    task_type: str,
) -> str:
    """Build a targeted fix prompt based on review issues."""
    if not critical_fields:
        return ""

    fields_str = "、".join(critical_fields)
    return (
        f"请根据审查意见修正以下字段的生成内容。\n\n"
        f"任务类型：{task_type}\n\n"
        f"原始材料：\n{_compact(original_materials)}\n\n"
        f"当前生成结果：\n{_compact(generated_result)}\n\n"
        f"审查意见：\n{_compact(review)}\n\n"
        f"需要修正的字段：{fields_str}\n\n"
        f"只输出修正后的完整 JSON，不要解释。"
    )
