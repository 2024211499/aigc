# -*- coding: utf-8 -*-
"""查询改写模块：将用户口语化问题改写为适合向量检索的表述。

用法：
    from rag.retrieval.query_rewriter import rewrite_query

    # 走 LLM 改写（推荐）
    rewritten = rewrite_query("这个为什么这样变？", course_name="高等数学", chapter_name="导数")

    # 不走 LLM 的轻量改写
    rewritten = rewrite_query("这个为什么这样变？", use_llm=False)
"""

from __future__ import annotations

import json as _json
import re
from typing import Callable, Optional


def rewrite_query(
    raw_query: str,
    course_name: str = "",
    chapter_name: str = "",
    knowledge_point: str = "",
    use_llm: bool = True,
    llm_fallback: bool = True,
    llm_callable: Optional[Callable] = None,
) -> str:
    """将原始用户问题改写为检索友好的查询字符串。

    Args:
        raw_query: 用户输入的原始问题。
        course_name: 当前课程名（可选）。
        chapter_name: 当前章节名（可选）。
        knowledge_point: 当前知识点（可选）。
        use_llm: 是否使用 LLM 改写。
        llm_fallback: LLM 失败时是否回退到轻量改写。
        llm_callable: 外部传入的 LLM 调用函数，签名为 (prompt, system_prompt) -> str。
                      不传时走本地规则改写。

    Returns:
        改写后的查询字符串。
    """
    cleaned = raw_query.strip()
    if not cleaned:
        return ""

    if use_llm and llm_callable:
        try:
            return _llm_rewrite(cleaned, course_name, chapter_name, knowledge_point, llm_callable)
        except Exception:
            if not llm_fallback:
                raise

    return _light_rewrite(cleaned, course_name, chapter_name, knowledge_point)


def _llm_rewrite(
    raw_query: str,
    course_name: str,
    chapter_name: str,
    knowledge_point: str,
    llm_callable: Callable,
) -> str:
    """用 LLM 改写查询。"""
    context_parts = []
    if course_name:
        context_parts.append(f"课程：{course_name}")
    if chapter_name:
        context_parts.append(f"章节：{chapter_name}")
    if knowledge_point:
        context_parts.append(f"知识点：{knowledge_point}")
    context = " | ".join(context_parts)

    prompt = f"""你是一个检索查询改写专家。请将用户的学习问题改写为**适合向量检索**的关键词式查询。

要求：
1. 提取核心概念和关键术语，去掉口语化表达（"这个"、"那个"、"为什么"等）。
2. 如果问题包含指代（"这个"、"它"、"该公式"），结合上下文明确具体对象。
3. 输出应为简洁的查询关键词或短句，适合在教材中进行向量检索。
4. 保留专业术语、公式名称、定理名称不变。

用户问题：{raw_query}
{("上下文：" + context) if context else ""}

输出 JSON 格式：
{{"rewritten_query": "改写后的查询语句"}}

示例：
用户问题："这个为什么这样变？"
上下文：课程：高等数学 | 章节：导数
输出：{{"rewritten_query": "导数公式变形 推导步骤 适用条件"}}

用户问题："告诉我一下那个定理"
上下文：章节：函数与极限
输出：{{"rewritten_query": "函数与极限 定理 夹逼定理 定义"}}

用户问题："什么是罗尔定理"
输出：{{"rewritten_query": "罗尔定理 定义 条件 结论"}}

用户问题："这道题怎么做？"
上下文：课程：高等数学 | 知识点：定积分
输出：{{"rewritten_query": "定积分 计算 例题 解题步骤"}}"""

    response = llm_callable(
        prompt,
        "你是一个检索查询改写助手。请将用户口语问题改写为精准的关键词检索查询。",
    )
    # Try to parse JSON from the response
    match = re.search(r'\{[^}]+\}', response)
    if match:
        try:
            result = _json.loads(match.group(0))
            rewritten = result.get("rewritten_query", "").strip()
            if rewritten:
                return rewritten
        except _json.JSONDecodeError:
            pass
    # If JSON parsing failed, use the raw response (trimmed)
    trimmed = response.strip().strip('"\'')
    if trimmed and len(trimmed) < 200:
        return trimmed
    return _light_rewrite(raw_query, course_name, chapter_name, knowledge_point)


def _light_rewrite(
    raw_query: str,
    course_name: str,
    chapter_name: str,
    knowledge_point: str,
) -> str:
    """轻量规则改写：去掉疑问词、补充上下文关键词。"""
    q = raw_query.strip()

    # 去掉口语化前缀
    q = re.sub(r"^(请问|告诉我|我想知道|帮我|能不能|可以|请问一下|问一下)\s*", "", q)

    # 替换常见指代
    replacements = {
        "这个": "",
        "那个": "",
        "它": "",
        "该公式": "",
        "该定理": "",
    }
    for old, new in replacements.items():
        q = q.replace(old, new)

    q = re.sub(r"[吗？?]$", "", q).strip()

    # 补充上下文
    parts = [q]
    if knowledge_point and knowledge_point not in q:
        parts.append(knowledge_point)
    if chapter_name and chapter_name not in q:
        parts.append(chapter_name)
    if course_name and course_name not in q:
        parts.append(course_name)

    return " ".join(parts)


def batch_rewrite(
    queries: list[str],
    course_name: str = "",
    chapter_name: str = "",
    knowledge_point: str = "",
    use_llm: bool = True,
    llm_fallback: bool = True,
    llm_callable=None,
) -> list[str]:
    """批量改写查询。"""
    return [
        rewrite_query(q, course_name, chapter_name, knowledge_point, use_llm, llm_fallback, llm_callable)
        for q in queries
    ]


__all__ = ["rewrite_query", "batch_rewrite"]
