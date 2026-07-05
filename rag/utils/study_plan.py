import json
import re
from typing import List
from .llm_client import call_llm

# ─── Prompt 模板 ────────────────────────────────────────────
SYSTEM_PROMPT = """你是一位经验丰富的教育专家和学习规划师，擅长根据教材内容设计高效、可执行的学习计划。

## 你的任务
分析用户提供的教材片段，生成一份结构化、个性化的学习计划。

## 生成原则
1. **针对性**：紧密围绕教材内容，不偏离主题
2. **可执行性**：任务具体、可操作，避免空泛描述
3. **合理性**：时长分配符合认知规律，循序渐进
4. **完整性**：覆盖所有关键知识点，无遗漏
5. **简洁性**：文字精炼，重点突出

## JSON输出规范
【极其重要】只输出纯JSON字符串，不要包含：
- ❌ markdown代码块标记（```json 或 ```）
- ❌ 任何解释性文字、前言、后记
- ❌ 注释或其他非JSON内容

## JSON结构定义
{
  "title": "学习计划标题（10-20字，精准概括学习内容）",
  "total_duration_min": 整数（总学习时长，建议30-180分钟，根据内容复杂度调整）,
  "plan_reason": "制定此计划的简要理由（30-50字，说明学习重点和预期效果）",
  "key_points": [
    "核心知识点1（提炼最关键的概念）",
    "核心知识点2",
    "核心知识点3"
  ],
  "sections": [
    {
      "name": "章节名称（4-10字，清晰标识学习内容）",
      "duration_min": 整数（单章节时长，建议10-45分钟）,
      "summary": "本章核心内容概述（30-50字，说明学什么、为什么重要）",
      "tasks": [
        "具体学习任务1（动词开头，如'阅读...''练习...''总结...'）",
        "具体学习任务2（可量化、可检验）",
        "具体学习任务3（可选，根据内容复杂度）"
      ]
    }
  ]
}

## 字段详细说明

### title（标题）
- 要求：简洁有力，体现学习主题
- 示例："Python函数编程基础"、"数据结构：链表与树"

### total_duration_min（总时长）
- 要求：合理估算，考虑初学者接受能力
- 建议：简单内容30-60分钟，中等内容60-120分钟，复杂内容120-180分钟

### plan_reason（计划理由）
- 要求：说明学习价值和预期收获
- 示例："本计划帮助你系统掌握Python函数核心概念，通过实践任务巩固理解，为后续高级编程打下基础"

### key_points（知识点列表）
- 数量：3-5个核心知识点
- 要求：从教材中提炼，按重要性排序
- 示例：["函数定义与调用", "参数传递机制", "返回值处理"]

### sections（学习章节）
- 数量：2-5个章节，根据内容复杂度调整
- 每个章节必须包含：
  - name：章节标题，体现学习阶段
  - duration_min：该章节预计用时
  - summary：简述学习内容和目标
  - tasks：2-4个具体任务，用动词开头，可执行、可检验

## 任务编写指南
tasks中的任务应当：
- ✅ 使用行动动词：阅读、理解、练习、编写、总结、对比、分析
- ✅ 具体明确："阅读教材第3章关于函数的定义"而非"学习函数"
- ✅ 可检验：完成后能明确判断是否完成
- ✅ 循序渐进：从理解到应用到拓展

## 质量检查清单
生成前请自检：
□ 所有字段都已填写且不为空
□ total_duration_min ≈ 各章节duration_min之和（允许±5分钟误差）
□ key_points覆盖了教材的核心内容
□ tasks具体可执行，不是空泛描述
□ 章节顺序符合学习逻辑（由浅入深）
□ JSON格式完全正确，可直接解析

现在，请根据用户提供的教材片段，生成高质量的学习计划。"""


def _clean_json_string(raw: str) -> str:
    """
    清理模型输出，去掉可能包裹在外面的 markdown 代码块。
    例如：```json {...} ``` → {...}
    """
    # 去掉首尾空白
    raw = raw.strip()

    # 如果以 ```json 开头，去掉代码块标记
    if raw.startswith("```"):
        # 找到第一个 ``` 之后的内容
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    return raw.strip()


def _validate_plan(plan: dict) -> None:
    """校验返回的学习计划包含必要字段且内容合理"""
    required_fields = ["title", "total_duration_min", "plan_reason", "key_points", "sections"]
    for field in required_fields:
        if field not in plan:
            raise ValueError(f"模型返回的JSON缺少必要字段：'{field}'")

    # 校验 title
    if not isinstance(plan["title"], str) or len(plan["title"]) == 0:
        raise ValueError("title 必须是非空字符串")
    
    # 校验 total_duration_min
    if not isinstance(plan["total_duration_min"], int) or plan["total_duration_min"] <= 0:
        raise ValueError("total_duration_min 必须是正整数")
    
    # 校验 plan_reason
    if not isinstance(plan["plan_reason"], str) or len(plan["plan_reason"]) == 0:
        raise ValueError("plan_reason 必须是非空字符串")

    # 校验 key_points
    if not isinstance(plan["key_points"], list) or len(plan["key_points"]) == 0:
        raise ValueError("key_points 必须是非空列表")
    
    # 校验 sections
    if not isinstance(plan["sections"], list) or len(plan["sections"]) == 0:
        raise ValueError("sections 必须是非空列表")
    
    # 校验每个 section 的字段
    total_section_duration = 0
    for i, section in enumerate(plan["sections"]):
        if "name" not in section or not section["name"]:
            raise ValueError(f"sections[{i}] 缺少 name 字段或为空")
        if "duration_min" not in section or not isinstance(section["duration_min"], int):
            raise ValueError(f"sections[{i}] 缺少 duration_min 字段或不是整数")
        if "summary" not in section or not section["summary"]:
            raise ValueError(f"sections[{i}] 缺少 summary 字段或为空")
        if "tasks" not in section or not isinstance(section["tasks"], list) or len(section["tasks"]) == 0:
            raise ValueError(f"sections[{i}] 缺少 tasks 字段或为空列表")
        total_section_duration += section["duration_min"]
    
    # 校验总时长是否合理（允许±10分钟误差）
    if abs(total_section_duration - plan["total_duration_min"]) > 10:
        raise ValueError(
            f"总时长不合理：total_duration_min={plan['total_duration_min']}，"
            f"但各章节时长之和={total_section_duration}，差异过大"
        )


def generate_study_plan(fragments: List[str]) -> dict:
    """
    根据教材片段列表，生成结构化学习计划。

    参数：
        fragments: 教材文本片段列表（来自1号检索结果）
    返回：
        包含学习计划的字典
    """
    if not fragments:
        raise ValueError("fragments 不能为空列表")

    # 把片段拼成用户输入
    fragments_text = "\n\n---\n\n".join(
        [f"【片段{i + 1}】\n{frag}" for i, frag in enumerate(fragments)]
    )

    user_prompt = f"""请根据以下教材片段生成学习计划：

═══════════════════════════════════════
教材内容片段
═══════════════════════════════════════

{fragments_text}

═══════════════════════════════════════
生成要求
═══════════════════════════════════════

1. 仔细分析上述教材内容，提取核心知识点
2. 按照认知规律设计学习路径（基础→进阶→应用）
3. 确保学习任务具体、可执行、可检验
4. 时长分配合理，符合学习难度
5. 输出严格的JSON格式，不要包含任何其他内容

请直接输出JSON格式的学习计划："""

    # 调用大模型
    raw_output = call_llm(user_prompt, SYSTEM_PROMPT)

    # 清理输出
    cleaned = _clean_json_string(raw_output)

    # 解析JSON
    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"模型输出无法解析为JSON。\n"
            f"解析错误：{e}\n"
            f"模型原始输出：\n{raw_output}"
        )

    # 校验字段
    _validate_plan(plan)

    return plan


if __name__ == "__main__":
    # 简单功能测试
    test_fragments = [
        "Python是一种高级编程语言，以简洁易读著称。它支持多种编程范式，包括面向对象、函数式和过程式编程。",
        "函数是Python中的一等公民，使用def关键字定义。函数可以接受参数、返回值，也可以嵌套定义。",
        "列表推导式是Python的特色语法，允许用简洁的方式创建列表：[x*2 for x in range(10)]"
    ]


    print("调用 generate_study_plan ...")
    plan = generate_study_plan(test_fragments)
    print(json.dumps(plan, ensure_ascii=False, indent=2))