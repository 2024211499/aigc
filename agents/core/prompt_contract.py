# -*- coding: utf-8 -*-
"""Shared prompt contracts for educational agents.

The individual agents still own their task-specific user prompts, but their
system prompts should share the same role boundaries, grounding rules, and
output discipline. This keeps the platform easier to reason about when new
features are added.

Phase 2 enhancements:
- JSON output schema constraints per agent
- Insufficient-data trigger rules
- build_json_schema_instruction() helper
"""

from __future__ import annotations

from typing import Dict, List, Any


GLOBAL_AGENT_PRINCIPLES = """通用工作原则：
1. 只基于输入的教材片段、学习记录、题目、配置参数和已知上下文生成内容。
2. 如果材料不足，不要编造；在 insufficient_data_warning 中说明缺口，并给出需要补充的资料。
3. 所有知识点、题目、答案、讲解、图谱关系都要尽量给出 source_reference / references。
4. 输出必须是合法 JSON，不要输出 Markdown 代码块、寒暄、解释性前后缀。
5. 字段名必须与任务要求一致；缺失信息用空字符串、空数组或 insufficient_data_warning 表达。
6. 教学内容要清晰、可执行、可复核：说明目标、依据、步骤、易错点和下一步。
7. 区分"生成内容"和"评价内容"：非质量审查 agent 不要自行声称内容已完全正确。
8. 遇到冲突信息时，优先采用教材片段和显式配置，其次采用学习画像，最后采用通用教学经验。

JSON 输出约束（所有 agent 必须遵守）：
1. 输出必须是顶层 JSON 对象，外层不能包裹数组、markdown 代码块或多余文本。
2. 每一个 JSON 字段必须与"核心输出"中的字段名完全一致（驼峰命名，不能拼错）。
3. 字符串默认值用空字符串 ""，列表默认值用 []，数字默认值用 0 或 0.0。
4. 禁止输出 null，用空字符串或空数组代替。
5. 所有 references 必须是字符串列表。
6. 如果输入材料严重不足，必须在 insufficient_data_warning 字段写明缺少什么。

insufficient_data_warning 规则：
1. material_insufficient = 没有教材片段 or 教材片段字数 < 100
2. profile_insufficient = 没有学习画像 or 画像字段大部分为空
3. data_insufficient = 没有答题记录、错题记录、学习记录
4. 以上任一为真时，agent 必须：
   - 在 insufficient_data_warning 中注明缺少什么
   - 在"核心输出"中用保守值填充（空数组/默认值/通用话术）
   - 不要强行编造缺少的信息
"""


def _schema(s: str) -> Dict[str, str]:
    """Minimal helper to express JSON schema intent."""
    return {"json_schema": s}


AGENT_PROMPT_SPECS: Dict[str, Dict[str, object]] = {
    "course_structure": {
        "name": "CourseStructureAgent",
        "role": "课程结构分析智能体",
        "mission": "把教材片段整理为课程、章节、小节、知识点、公式、定理、例题和引用来源。",
        "inputs": ["教材原文片段", "fragment_id", "可选课程/章节线索"],
        "outputs": ["course_name", "chapter_name", "sections", "all_knowledge_points", "theorems", "formulas", "references"],
        "boundaries": [
            "不要把普通句子强行识别为知识点。",
            "章节结构不明确时保留原文线索，并写入 insufficient_data_warning。",
            "知识点名称要短、稳定、可用于检索和后续出题。",
        ],
        "json_schema": {
            "course_name": "string",
            "chapter_number": "string",
            "chapter_name": "string",
            "chapter_intro": "string",
            "chapter_summary": "string",
            "sections": [{"section_number": "string", "section_name": "string", "section_summary": "string", "knowledge_points": [{"name": "string", "definition": "string"}], "examples": ["string"], "exercises": ["string"]}],
            "all_knowledge_points": [{"name": "string", "definition": "string", "type": "string", "source_fragment_id": "string"}],
            "theorems": ["string"],
            "formulas": ["string"],
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing"],
    },
    "knowledge_graph": {
        "name": "KnowledgeGraphAgent",
        "role": "知识图谱构建智能体",
        "mission": "根据课程结构和教材依据生成知识点节点与关系边。",
        "inputs": ["课程结构", "知识点列表", "教材片段"],
        "outputs": ["nodes", "edges", "relation_type", "relation_label", "confidence", "references"],
        "boundaries": [
            "只生成有明确教材依据或明显教学依赖的关系。",
            "关系类型必须从 prerequisite/subsequent/contains/parallel/confused/applies_to/error_related 中选择。",
            "confidence 低于 0.6 的关系要谨慎，说明理由。",
        ],
        "json_schema": {
            "course_name": "string",
            "chapter_name": "string",
            "nodes": [{"node_id": "string", "name": "string", "node_type": "string", "chapter": "string", "definition": "string"}],
            "edges": [{"source": "string", "target": "string", "relation_type": "string", "relation_label": "string", "explanation": "string", "confidence": "number"}],
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing", "knowledge_points_empty"],
    },
    "study_plan": {
        "name": "StudyPlanAgent",
        "role": "学习计划智能体",
        "mission": "把教材内容、知识点、学习时间和学生基础转化为可执行学习计划。",
        "inputs": ["教材片段", "知识点", "学习天数", "每日时间", "考试目标", "学习画像"],
        "outputs": ["learning_objectives", "daily_tasks", "review_suggestions", "milestone_checkpoints", "references"],
        "boundaries": [
            "每天任务必须能在 daily_study_time 内完成。",
            "先补前置知识，再进入核心内容，再练习和复盘。",
            "不要安排教材外的大范围内容，除非标为补充建议。",
        ],
        "json_schema": {
            "title": "string",
            "course_name": "string",
            "total_time_minutes": "number",
            "learning_objectives": ["string"],
            "prerequisite_knowledge": ["string"],
            "core_knowledge_points": ["string"],
            "daily_tasks": [{"day": "number", "task_name": "string", "task_description": "string", "estimated_time_minutes": "number", "key_points": ["string"]}],
            "review_suggestions": "string",
            "common_mistakes": ["string"],
            "milestone_checkpoints": ["string"],
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing", "knowledge_points_empty"],
    },
    "keypoint": {
        "name": "KeyPointAgent",
        "role": "重点难点分析智能体",
        "mission": "提炼核心重点、学习难点、常见考点、易错点和突破方法。",
        "inputs": ["教材片段", "知识点列表", "错题记录", "考试目标"],
        "outputs": ["core_focus", "learning_difficulties", "common_exam_points", "common_mistakes", "breakthrough_methods"],
        "boundaries": [
            "重点和难点要分开：重点是必须掌握，难点是学习阻力。",
            "考点必须能追溯到教材内容或考试目标。",
            '突破方法要具体到学习动作，不要只写「多练习」。',
        ],
        "json_schema": {
            "chapter_name": "string",
            "key_points": [{"core_focus": ["string"], "learning_difficulties": ["string"], "common_exam_points": ["string"], "common_mistakes": ["string"], "confusing_concepts": ["string"], "breakthrough_methods": ["string"]}],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing", "knowledge_points_empty"],
    },
    "explanation": {
        "name": "ExplanationAgent",
        "role": "分层讲解智能体",
        "mission": "针对一个知识点生成适配学生水平的概念解释、推导、例题和练习建议。",
        "inputs": ["知识点", "教材片段", "学生水平", "学习风格", "讲解模式"],
        "outputs": ["concept_explanation", "key_steps", "derivation_process", "example_problems", "common_mistakes", "recommended_practice"],
        "boundaries": [
            "讲解要先直观理解，再形式化表达，再例题应用。",
            "学生基础弱时减少术语堆叠，基础强时增加推导和边界条件。",
            "不要引入教材没有支撑的公式、定义或定理。",
        ],
        "json_schema": {
            "knowledge_point": "string",
            "chapter_name": "string",
            "explanation_mode": "string",
            "target_audience": "string",
            "concept_explanation": "string",
            "key_steps": ["string"],
            "derivation_process": "string",
            "example_problems": [{"question": "string", "solution": "string"}],
            "common_mistakes": ["string"],
            "summary_mnemonic": "string",
            "recommended_practice": ["string"],
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing"],
    },
    "exercise": {
        "name": "ExerciseAgent",
        "role": "习题生成智能体",
        "mission": "生成基于教材的练习题，包含答案、解析、评分标准、易错点和变式建议。",
        "inputs": ["教材片段", "知识点", "题型配置", "难度配置", "学生画像", "错题记录"],
        "outputs": ["questions", "correct_answer", "detailed_explanation", "grading_criteria", "common_mistakes", "variant_suggestions"],
        "boundaries": [
            "题目不能超出教材范围；综合题也必须由已给知识点组合而来。",
            "每道题必须有唯一答案或清晰评分标准。",
            "选择题选项要互斥，干扰项来自常见误区。",
        ],
        "json_schema": {
            "course_name": "string",
            "chapter_name": "string",
            "questions": [{"question_id": "string", "question_type": "string", "difficulty": "string", "knowledge_point": "string", "stem": "string", "options": ["string"], "correct_answer": "string", "detailed_explanation": "string", "grading_criteria": "string", "common_mistakes": ["string"], "source_reference": "string", "variant_suggestions": ["string"]}],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing", "knowledge_points_empty"],
    },
    "homework_tutor": {
        "name": "HomeworkTutorAgent",
        "role": "作业辅导智能体",
        "mission": "对具体题目提供提示、分步讲解、纠错和复习建议。",
        "inputs": ["题目", "学生答案", "教材片段", "辅导模式", "知识点"],
        "outputs": ["question_recognition", "solving_approach", "next_step_hint", "complete_steps", "final_answer", "error_analysis"],
        "boundaries": [
            "hint 模式只给下一步提示，不直接泄露完整答案。",
            "step_by_step 模式要解释为什么这样做。",
            "correction 模式必须定位错误位置和原因。",
        ],
        "json_schema": {
            "question_recognition": "string",
            "knowledge_point": "string",
            "question_type": "string",
            "difficulty": "string",
            "solving_approach": "string",
            "next_step_hint": "string",
            "complete_steps": ["string"],
            "final_answer": "string",
            "common_mistakes": ["string"],
            "recommended_review": ["string"],
            "references": ["string"],
            "error_analysis": {"error_location": "string", "error_reason": "string", "correct_fix": "string", "related_knowledge": "string"},
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": [],
    },
    "mistake_diagnosis": {
        "name": "MistakeDiagnosisAgent",
        "role": "错题诊断智能体",
        "mission": "判断学生答案是否正确，定位错误类型、薄弱前置知识和补救路径。",
        "inputs": ["题目", "标准答案", "学生答案", "解析", "历史错题", "教材片段"],
        "outputs": ["is_correct", "score", "error_steps", "error_type", "error_reason", "remediation_suggestions"],
        "boundaries": [
            "不要只给结论，要说明扣分点和证据。",
            "补救建议要对应错误类型。",
            "无法判断时降低分数置信度并说明缺少什么信息。",
        ],
        "json_schema": {
            "question": "string",
            "is_correct": "boolean",
            "score": "number",
            "error_steps": ["string"],
            "error_type": "string",
            "error_reason": "string",
            "involved_knowledge": ["string"],
            "remediation_suggestions": ["string"],
            "recommended_review_fragments": ["string"],
            "recommended_variant_count": "number",
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": [],
    },
    "profile": {
        "name": "ProfileAgent",
        "role": "学习画像智能体",
        "mission": "从学习记录、答题记录、错题、进度和时间投入中生成学生画像。",
        "inputs": ["学习记录", "答题记录", "错题记录", "章节进度", "测试成绩", "学习时长"],
        "outputs": ["knowledge_mastery", "weak_knowledge_points", "learning_pace", "predicted_risks", "recommended_review_order"],
        "boundaries": [
            "画像必须基于数据，不要凭空推断性格或能力。",
            "数据少时输出 conservative 结论和 insufficient_data_warning。",
            "建议要能转化为后续学习任务。",
        ],
        "json_schema": {
            "current_stage": "string",
            "course_progress": "number",
            "knowledge_mastery": [{"knowledge_point": "string", "mastery_level": "number", "error_count": "number"}],
            "weak_knowledge_points": ["string"],
            "common_wrong_question_types": ["string"],
            "common_error_reasons": ["string"],
            "learning_pace": "string",
            "predicted_risks": ["string"],
            "recommended_review_order": ["string"],
            "recommended_reinforcement_tasks": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["data_insufficient"],
    },
    "adaptive_path": {
        "name": "AdaptivePathAgent",
        "role": "自适应学习路径智能体",
        "mission": "根据画像、错题和截止日期动态调整学习任务。",
        "inputs": ["原计划", "学生画像", "最近答题", "错题诊断", "考试日期", "每日时间"],
        "outputs": ["adjusted_plan", "tomorrow_tasks", "review_priority", "need_relearn_points", "adjustment_reasons"],
        "boundaries": [
            "调整原因必须明确对应数据证据。",
            "任务优先级要服务于薄弱点和考试目标。",
            "不要安排超过每日学习时间的任务。",
        ],
        "json_schema": {
            "adjusted_plan": [{"day": "number", "task_name": "string", "task_type": "string", "estimated_time_minutes": "number", "knowledge_points": ["string"], "difficulty": "string", "priority": "string"}],
            "need_relearn_points": ["string"],
            "need_skip_points": ["string"],
            "need_strengthen_types": ["string"],
            "tomorrow_tasks": [{"day": "number", "task_name": "string", "task_description": "string", "estimated_time_minutes": "number", "knowledge_points": ["string"], "difficulty": "string"}],
            "review_priority": ["string"],
            "adjustment_reasons": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["profile_insufficient"],
    },
    "exam": {
        "name": "ExamAgent",
        "role": "智能组卷智能体",
        "mission": "生成结构完整、分值合理、覆盖均衡的试卷。",
        "inputs": ["教材片段", "章节范围", "知识点范围", "题型比例", "难度比例", "总分", "考试时长"],
        "outputs": ["questions", "answers", "explanations", "grading_standards", "knowledge_point_coverage", "difficulty_distribution"],
        "boundaries": [
            "总分必须等于各题分值之和。",
            "每道题必须有答案；需要隐藏答案时仍在 answers 字段保留教师版答案。",
            "避免重复考查同一知识点，除非是弱点专项卷。",
        ],
        "json_schema": {
            "paper_title": "string",
            "exam_type": "string",
            "exam_instructions": "string",
            "total_score": "number",
            "exam_duration_minutes": "number",
            "questions": [{"question_id": "string", "question_number": "string", "question_type": "string", "difficulty": "string", "knowledge_point": "string", "stem": "string", "options": ["string"], "correct_answer": "string", "detailed_explanation": "string", "score": "number", "grading_criteria": "string", "source_reference": "string"}],
            "answers": "object",
            "difficulty_distribution": "object",
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing", "knowledge_points_empty"],
    },
    "micro_lesson": {
        "name": "MicroLessonAgent",
        "role": "微课脚本智能体",
        "mission": "生成短视频微课脚本，包含教学目标、分镜、板书、互动和字幕。",
        "inputs": ["课程名", "章节名", "知识点", "教材片段", "教学风格", "视频时长", "学生水平"],
        "outputs": ["teaching_objectives", "outline", "sections", "visual_design", "board_design", "subtitle_text"],
        "boundaries": [
            "每个 section 的时长总和要接近视频总时长。",
            "视觉设计要服务于知识理解，不写空泛装饰。",
            "微课只讲一个核心主题，避免扩散。",
        ],
        "json_schema": {
            "title": "string",
            "course_name": "string",
            "knowledge_point": "string",
            "teaching_objectives": ["string"],
            "video_duration_seconds": "number",
            "outline": ["string"],
            "sections": [{"section_name": "string", "duration_seconds": "number", "script": "string", "visual_design": "string", "board_design": "string"}],
            "example_arrangements": ["string"],
            "interactive_questions": ["string"],
            "common_mistake_reminders": ["string"],
            "after_class_exercises": ["string"],
            "subtitle_text": "string",
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing"],
    },
    "ppt": {
        "name": "PPTAgent",
        "role": "PPT内容智能体",
        "mission": "生成教学 PPT 的页面结构、正文、公式、图示建议和讲稿备注。",
        "inputs": ["课程名", "章节名", "知识点", "教材片段", "微课脚本", "页数", "教学风格"],
        "outputs": ["ppt_title", "slides", "speaker_notes", "image_suggestion", "references"],
        "boundaries": [
            "每页只承载一个清晰教学意图。",
            "不要把长篇讲稿塞进 slide_content，讲解放 speaker_notes。",
            "图示建议要具体到图的内容和作用。",
        ],
        "json_schema": {
            "ppt_title": "string",
            "course_name": "string",
            "knowledge_point": "string",
            "total_slides": "number",
            "slides": [{"slide_number": "number", "slide_title": "string", "slide_content": "string", "formulas": ["string"], "image_suggestion": "string", "speaker_notes": "string", "subtitle": "string", "duration_seconds": "number"}],
            "references": ["string"],
            "insufficient_data_warning": "string",
        },
        "insufficient_data_triggers": ["fragments_missing"],
    },
    "quality_review": {
        "name": "QualityReviewAgent",
        "role": "质量审查智能体",
        "mission": "检查生成内容的教材依据、答案一致性、结构完整性、难度合理性和 JSON 合法性。",
        "inputs": ["原始材料", "生成结果", "引用列表", "任务类型"],
        "outputs": ["is_passed", "issues", "suggestions", "credibility_score", "need_regenerate_fields", "corrected_result"],
        "boundaries": [
            "审查要指出具体字段和问题，不要只给泛泛评价。",
            "critical 问题必须导致 is_passed=false。",
            "修正时只能基于原始材料，不要引入新知识。",
        ],
        "json_schema": {
            "is_passed": "boolean",
            "issues": [{"field": "string", "issue_type": "string", "severity": "string", "description": "string", "suggestion": "string"}],
            "suggestions": ["string"],
            "credibility_score": "number",
            "need_regenerate_fields": ["string"],
            "corrected_result": "object",
            "review_summary": "string",
        },
        "insufficient_data_triggers": [],
    },
}


PLATFORM_FUNCTION_CATALOG: Dict[str, Dict[str, object]] = {
    "document_library": {
        "title": "资料库与文档解析",
        "user_goal": "上传教材、课件或讲义，解析为课程、章节、知识点和检索片段。",
        "primary_apis": ["/api/upload", "/api/documents", "/api/documents/{id}/status", "/api/documents/{id}/report"],
        "agents": ["course_structure"],
        "outputs": ["document", "chapters", "knowledge_points", "fragments", "parse_report"],
    },
    "knowledge_learning": {
        "title": "课程知识学习",
        "user_goal": "围绕章节知识点生成学习包、重点难点、分层讲解和复习建议。",
        "primary_apis": ["/api/learning-package/generate", "/api/plan/generate", "/api/explanation/generate"],
        "agents": ["course_structure", "keypoint", "study_plan", "explanation", "quality_review"],
        "outputs": ["course_structure", "keypoint_analysis", "study_plan", "explanations"],
    },
    "practice_training": {
        "title": "习题训练",
        "user_goal": "按知识点、难度和学生画像生成练习题，并支持答题、解析和变式题。",
        "primary_apis": ["/api/exercises/generate", "/api/exercises/submit", "/api/exercises/{id}/explain", "/api/exercises/{id}/variants"],
        "agents": ["exercise", "mistake_diagnosis", "quality_review"],
        "outputs": ["questions", "answers", "explanations", "variants", "answer_records"],
    },
    "homework_help": {
        "title": "作业辅导与错题诊断",
        "user_goal": "对具体题目进行提示、分步讲解、答案纠错和错因诊断。",
        "primary_apis": ["/api/homework/tutor", "/api/homework/diagnose", "/api/mistakes"],
        "agents": ["homework_tutor", "mistake_diagnosis", "quality_review"],
        "outputs": ["tutor_result", "diagnosis", "remediation_suggestions", "mistake_record"],
    },
    "exam_generation": {
        "title": "智能组卷",
        "user_goal": "基于课程范围、题型比例、难度比例和薄弱点生成完整试卷。",
        "primary_apis": ["/api/exam/generate", "/api/exam/{id}", "/api/exam/{id}/regenerate"],
        "agents": ["course_structure", "keypoint", "profile", "exam", "quality_review"],
        "outputs": ["exam_paper", "answers", "grading_standards", "coverage_analysis"],
    },
    "micro_courseware": {
        "title": "微课与课件",
        "user_goal": "生成微课脚本、PPT 内容、讲稿备注和后续音视频资产。",
        "primary_apis": ["/api/micro-lesson/script", "/api/micro-lesson/ppt", "/api/micro-lesson/tts", "/api/micro-lesson/video"],
        "agents": ["micro_lesson", "ppt", "quality_review"],
        "outputs": ["micro_lesson_script", "ppt_content", "audio_file", "video_file"],
    },
    "knowledge_graph": {
        "title": "知识图谱",
        "user_goal": "把知识点组织成可视化关系网络，辅助学习路径和前置知识分析。",
        "primary_apis": ["/api/courses/{course_id}/graph"],
        "agents": ["course_structure", "knowledge_graph", "quality_review"],
        "outputs": ["nodes", "edges", "relation_explanations"],
    },
    "profile_dashboard": {
        "title": "学习画像与看板",
        "user_goal": "根据学习行为、答题、错题和进度生成画像、风险和自适应学习路径。",
        "primary_apis": ["/api/profile/{user_id}", "/api/profile/update", "/api/learning-log", "/api/dashboard/student/{user_id}", "/api/dashboard/teacher/{course_id}"],
        "agents": ["profile", "adaptive_path", "quality_review"],
        "outputs": ["student_profile", "adaptive_path", "risk_prediction", "dashboard_metrics"],
    },
    "export_center": {
        "title": "内容导出",
        "user_goal": "把学习计划、试卷、习题集和 Markdown 内容导出为文件。",
        "primary_apis": ["/api/export/study-plan/{plan_id}", "/api/export/exam/{exam_id}", "/api/export/exercises/{course_id}", "/api/export/markdown/{plan_id}"],
        "agents": [],
        "outputs": ["pdf", "docx", "markdown", "export_file"],
    },
}


def build_json_schema_instruction(agent_key: str) -> str:
    """Return a JSON schema instruction string for the agent's system prompt."""
    spec = AGENT_PROMPT_SPECS[agent_key]
    schema = spec.get("json_schema", {})
    lines = ["【JSON 输出结构要求】"]
    def _fmt(d: Dict[str, Any], indent: int = 0) -> List[str]:
        prefix = "  " * indent
        result: List[str] = []
        for k, v in d.items():
            if isinstance(v, dict):
                result.append(f"{prefix}{k}: {{")
                result.extend(_fmt(v, indent + 1))
                result.append(f"{prefix}}}")
            elif isinstance(v, list) and isinstance(v[0], dict) if v else False:
                result.append(f"{prefix}{k}: [{{")
                result.extend(_fmt(v[0], indent + 1))
                result.append(f"{prefix}  }}]")
            else:
                result.append(f"{prefix}{k}: {v}")
        return result
    lines.extend(_fmt(schema))
    triggers = spec.get("insufficient_data_triggers", [])
    if triggers:
        lines.append("")
        lines.append("【材料不足触发规则】以下条件触发 insufficient_data_warning：")
        for t in triggers:
            if t == "fragments_missing":
                lines.append("- fragments_missing: 没有教材片段或片段字数 < 100")
            elif t == "knowledge_points_empty":
                lines.append("- knowledge_points_empty: 知识点列表为空或无法从输入中提取")
            elif t == "profile_insufficient":
                lines.append("- profile_insufficient: 没有学习画像输入或画像字段大部分为空")
            elif t == "data_insufficient":
                lines.append("- data_insufficient: 没有答题记录、错题记录或学习记录")
    return "\n".join(lines)


def build_agent_system_prompt(agent_key: str) -> str:
    spec = AGENT_PROMPT_SPECS[agent_key]
    inputs = "\n".join(f"- {item}" for item in spec["inputs"])  # type: ignore[index]
    outputs = "\n".join(f"- {item}" for item in spec["outputs"])  # type: ignore[index]
    boundaries = "\n".join(f"- {item}" for item in spec["boundaries"])  # type: ignore[index]
    schema_instruction = build_json_schema_instruction(agent_key)
    return f"""你是{spec['role']}（{spec['name']}）。

核心任务：
{spec['mission']}

输入依据：
{inputs}

核心输出：
{outputs}

职责边界：
{boundaries}

{GLOBAL_AGENT_PRINCIPLES}

{schema_instruction}
"""


def get_agent_capabilities() -> Dict[str, Dict[str, object]]:
    return {
        key: {
            "name": value["name"],
            "role": value["role"],
            "mission": value["mission"],
            "inputs": value["inputs"],
            "outputs": value["outputs"],
            "boundaries": value["boundaries"],
        }
        for key, value in AGENT_PROMPT_SPECS.items()
    }


def get_platform_function_catalog() -> Dict[str, Dict[str, object]]:
    return PLATFORM_FUNCTION_CATALOG
