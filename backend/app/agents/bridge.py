# -*- coding: utf-8 -*-
"""
智能体桥接层
将 2号队员的 OrchestratorAgent 封装为后端服务可调用的接口
兼容 2号代码未整合时的降级模式
"""

import sys
import os
import logging
from typing import List, Dict, Any, Optional

from ..core.config import settings

logger = logging.getLogger(__name__)

# ─── 尝试导入 2号模块 ────────────────────────────────────────
_agent_available = False
_orchestrator = None

def _try_import_agents():
    global _agent_available, _orchestrator
    # agent_dir = aigc-platform/agents，取其父目录作为包根
    # 这样 agents 成为顶层包（agents.agents.* / agents.core.*），
    # 相对导入 from ..core 可以正常解析，IDE 也能识别
    agent_dir = os.path.abspath(settings.AGENT_MODULE_DIR)
    project_root = os.path.dirname(agent_dir)   # aigc-platform/
    if os.path.isdir(agent_dir) and project_root not in sys.path:
        sys.path.insert(0, project_root)
        logger.info(f"✅ 已将项目根 {project_root} 加入 sys.path")
    try:
        from agents.agents.orchestrator_agent import OrchestratorAgent  # type: ignore
        _orchestrator = OrchestratorAgent()
        _agent_available = True
        logger.info("✅ 2号 Agent 模块加载成功")
    except ImportError as e:
        logger.warning(f"⚠️  2号 Agent 模块未找到，使用内置 LLM 直调: {e}")
        _agent_available = False
    except Exception as e:
        logger.warning(f"⚠️  Agent 初始化异常: {e}", exc_info=True)
        _agent_available = False

_try_import_agents()


# ════════════════════════════════════════════════════════════
#  智能体服务封装
# ════════════════════════════════════════════════════════════

class AgentService:
    """
    统一智能体调用服务
    有 2号模块 → 走 OrchestratorAgent
    无 2号模块 → 直接调用 LLM API（兜底）
    """

    # ── 学习包 ────────────────────────────────────────────
    def generate_learning_package(
        self,
        fragments: List[str],
        course_id: str = "",
        chapter_name: str = "",
        user_profile: Optional[Dict] = None,
        study_days: int = 7,
        daily_time: int = 60,
        exercise_count: int = 10,
    ) -> Dict[str, Any]:
        profile = user_profile or {}
        if _agent_available:
            try:
                return _orchestrator.run_learning_package_workflow(
                    course_id=course_id,
                    fragments=fragments,
                    user_profile=profile,
                    study_days=study_days,
                    daily_time=daily_time,
                    exercise_count=exercise_count,
                )
            except Exception as e:
                logger.error(f"Agent 学习包生成失败: {e}", exc_info=True)
        return self._llm_generate_learning_package(fragments, chapter_name, study_days, daily_time)

    # ── 重点难点 ──────────────────────────────────────────
    def generate_keypoints(
        self,
        fragments: List[str],
        course_id: str = "",
        chapter_name: str = "",
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                from agents.agents.keypoint_agent import generate_keypoint_analysis  # type: ignore
                return generate_keypoint_analysis(
                    fragments=fragments,
                    chapter_name=chapter_name,
                )
            except Exception as e:
                logger.error(f"Agent 重点难点生成失败: {e}", exc_info=True)
        return self._llm_generate_keypoints(fragments, chapter_name)

    # ── 讲解 ──────────────────────────────────────────────
    def generate_explanation(
        self,
        fragments: List[str],
        knowledge_point: str,
        style: str = "textbook",
        user_level: str = "中等",
        course_id: str = "",
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                from agents.agents.explanation_agent import generate_layered_explanation  # type: ignore
                return generate_layered_explanation(
                    knowledge_point=knowledge_point,
                    fragments=fragments,
                    explanation_mode=style,
                    student_level=user_level,
                )
            except Exception as e:
                logger.error(f"Agent 讲解生成失败: {e}", exc_info=True)
        return self._llm_generate_explanation(fragments, knowledge_point, style)

    # ── 习题 ──────────────────────────────────────────────
    def generate_exercises(
        self,
        fragments: List[str],
        course_id: str = "",
        chapter_name: str = "",
        knowledge_point: str = "",
        question_types: Optional[List[str]] = None,
        difficulty: str = "medium",
        count: int = 5,
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                return _orchestrator.run_exercise_workflow(
                    course_id=course_id,
                    fragments=fragments,
                    exercise_count=count,
                )
            except Exception as e:
                logger.error(f"Agent 习题生成失败: {e}", exc_info=True)
        return self._llm_generate_exercises(fragments, knowledge_point, count)

    # ── 错题诊断 ──────────────────────────────────────────
    def diagnose_mistake(
        self,
        question: str,
        standard_answer: str,
        student_answer: str,
        explanation: str = "",
        fragments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                from agents.agents.mistake_diagnosis_agent import generate_mistake_diagnosis  # type: ignore
                return generate_mistake_diagnosis(
                    question=question,
                    standard_answer=standard_answer,
                    student_answer=student_answer,
                    fragments=fragments or [],
                    explanation=explanation,
                )
            except Exception as e:
                logger.error(f"Agent 错题诊断失败: {e}", exc_info=True)
        return self._llm_diagnose_mistake(question, standard_answer, student_answer)

    # ── 组卷 ──────────────────────────────────────────────
    def generate_exam(
        self,
        fragments: List[str],
        course_id: str = "",
        chapters: Optional[List[str]] = None,
        exam_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        cfg = exam_config or {}
        if _agent_available:
            try:
                return _orchestrator.run_exam_workflow(
                    course_id=course_id,
                    chapters=chapters or [],
                    exam_config=cfg,
                    fragments=fragments,
                )
            except Exception as e:
                logger.error(f"Agent 组卷失败: {e}", exc_info=True)
        return self._llm_generate_exam(fragments, cfg)

    # ── 微课脚本 ──────────────────────────────────────────
    def generate_micro_lesson(
        self,
        fragments: List[str],
        topic: str,
        course_id: str = "",
        style: str = "讲解式",
        duration: int = 300,
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                return _orchestrator.run_micro_lesson_workflow(
                    course_id=course_id,
                    fragments=fragments,
                    topic=topic,
                    style=style,
                    duration=duration,
                )
            except Exception as e:
                logger.error(f"Agent 微课生成失败: {e}", exc_info=True)
        return self._llm_generate_micro_lesson(fragments, topic, duration)

    # ── PPT ───────────────────────────────────────────────
    def generate_ppt_content(
        self,
        fragments: List[str],
        topic: str,
        course_id: str = "",
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                return _orchestrator.run_ppt_workflow(
                    course_id=course_id,
                    fragments=fragments,
                    topic=topic,
                )
            except Exception as e:
                logger.error(f"Agent PPT 生成失败: {e}", exc_info=True)
        return self._llm_generate_ppt(fragments, topic)

    # ── 作业辅导 ──────────────────────────────────────────
    def homework_tutor(
        self,
        question: str,
        student_answer: str = "",
        mode: str = "step_by_step",
        fragments: Optional[List[str]] = None,
        image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 有图片时走多模态 LLM
        if image_base64:
            try:
                result = self._multimodal_homework_tutor(question, student_answer, mode, image_base64)
                return self._normalize_homework_result(result, question, image_based=True)
            except Exception as e:
                logger.error(f"多模态辅导失败，回退: {e}", exc_info=True)

        if image_base64:
            return self._insufficient_homework_result(
                question=question,
                reason="图片题多模态识别失败，不能只根据文字提示生成模板答案。",
                image_based=True,
            )

        frags = fragments or []
        if _agent_available:
            try:
                result = _orchestrator.run_homework_tutor_workflow(
                    question=question,
                    student_answer=student_answer if student_answer else None,
                    fragments=frags,
                )
                return self._normalize_homework_result(result, question)
            except Exception as e:
                logger.error(f"Agent 作业辅导失败: {e}", exc_info=True)
        return self._normalize_homework_result(self._llm_homework_tutor(question, student_answer, mode), question)

    # ── 知识图谱 ──────────────────────────────────────────
    def generate_knowledge_graph(
        self,
        fragments: List[str],
        course_id: str = "",
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                return _orchestrator.run_knowledge_graph_workflow(
                    course_id=course_id,
                    fragments=fragments,
                )
            except Exception as e:
                logger.error(f"Agent 知识图谱生成失败: {e}", exc_info=True)
        return self._llm_knowledge_graph(fragments)

    # ── 学习画像 ──────────────────────────────────────────
    def generate_profile(
        self,
        user_id: str,
        learning_records: Dict,
    ) -> Dict[str, Any]:
        if _agent_available:
            try:
                from agents.agents.profile_agent import generate_student_profile  # type: ignore

                # _collect_learning_records 返回的是聚合统计，需映射到 profile_agent 所需格式
                # recent_actions → learning_records
                recent = learning_records.get("recent_actions", [])
                lr_list = [
                    {"content": f"{a.get('action', '')} {a.get('detail', '')}"}
                    for a in recent
                ]

                # error_type_distribution → mistake_records（近似）
                error_dist = learning_records.get("error_type_distribution", {})
                mr_list = [
                    {"question": "", "error_type": et, "error_reason": f"共{cnt}次"}
                    for et, cnt in error_dist.items()
                ]

                # study_time：用答题正确率作为汇总参考
                study_time = {
                    "总答题数": learning_records.get("total_answers", 0),
                    "正确答题数": learning_records.get("correct_answers", 0),
                    "正确率": learning_records.get("accuracy_rate", 0),
                }

                return generate_student_profile(
                    learning_records=lr_list,
                    answer_records=[],          # 聚合层无法重建逐条答题流水
                    mistake_records=mr_list,
                    chapter_progress={},
                    test_scores=[],
                    study_time=study_time,
                    course_name="",
                )
            except Exception as e:
                logger.error(f"Agent 画像生成失败: {e}", exc_info=True)
        return self._llm_profile(learning_records)

    # ════════════════════════════════════════════════════════
    #  兜底：直接调用 LLM API
    # ════════════════════════════════════════════════════════

    def _call_llm(self, system: str, user: str, max_tokens: int = 1200) -> str:
        """调用 DeepSeek / OpenAI 兼容接口"""
        try:
            import openai
            # 确保 base_url 包含 /v1 路径
            base_url = settings.LLM_API_BASE
            if base_url and not base_url.rstrip("/").endswith("/v1"):
                base_url = base_url.rstrip("/") + "/v1"
            client = openai.OpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=base_url,
                timeout=50.0,  # 服务端 50s 超时，比测试客户端 60s 短，确保能返回错误
            )
            resp = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return ""

    def _parse_json_response(self, text: str) -> Dict:
        import json, re
        # 去除 markdown 代码块标记
        text = re.sub(r"```json\s*|```\s*", "", text).strip()

        # ① 直接解析
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
            if isinstance(result, list):
                return {"questions": result}
        except Exception:
            pass

        # ② 从文本中找最长合法 JSON 对象/数组
        for pattern in (r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
            candidates = re.findall(pattern, text)
            for candidate in sorted(candidates, key=len, reverse=True):
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                    if isinstance(result, list):
                        return {"questions": result}
                except Exception:
                    continue

        # ③ 兜底：将原文存入 raw，导出层会识别并尝试二次解析
        return {"raw": text}

    def _llm_generate_learning_package(self, fragments, chapter_name, study_days, daily_time):
        ctx = "\n---\n".join(fragments[:3])[:600]
        sys_p = "你是教育专家。只输出纯JSON，不含markdown，内容简洁。"
        day_show = min(study_days, 3)
        usr_p = (
            f"为《{chapter_name}》生成学习计划，{day_show}天，每天{daily_time}分钟。\n"
            f"教材摘要：\n{ctx}\n\n"
            f"输出JSON：{{\"title\":\"...\",\"chapter_name\":\"...\","
            f"\"learning_objectives\":[3条],\"core_knowledge_points\":[3条],"
            f"\"daily_tasks\":[{{\"day\":1,\"tasks\":[\"...\"]}},...共{day_show}天]}}"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p, max_tokens=900))

    def _llm_generate_keypoints(self, fragments, chapter_name):
        ctx = "\n---\n".join(fragments[:5])
        sys_p = "你是一位教育专家。只输出纯 JSON，不含 markdown 代码块。"
        usr_p = (
            f"从以下教材片段中提炼《{chapter_name}》的重点难点。\n\n"
            f"教材片段：\n{ctx}\n\n"
            "输出 JSON 包含：key_points(list), difficult_points(list), "
            "common_mistakes(list), exam_focuses(list)"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p))

    def _llm_generate_explanation(self, fragments, kp, style):
        ctx = "\n---\n".join(fragments[:3])[:500]
        sys_p = "你是教育专家。只输出纯JSON，不含markdown，内容简洁。"
        usr_p = (
            f"以「{style}」方式简要讲解：{kp}。\n教材参考：\n{ctx}\n\n"
            "输出JSON：{\"title\":\"...\",\"style\":\"...\",\"explanation\":\"200字以内\","
            "\"key_steps\":[3步],\"example\":\"一句话\",\"mistake_tips\":[2条],\"summary\":\"一句话\"}"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p, max_tokens=800))

    def _llm_generate_exercises(self, fragments, kp, count):
        ctx = "\n---\n".join(str(f)[:200] for f in fragments[:3])[:500]
        n = min(count, 3)
        sys_p = "你是出题专家。只输出纯JSON，不含markdown，题目简洁。"
        usr_p = (
            f"围绕「{kp or '核心知识'}」出{n}道简答/选择题。\n参考：{ctx}\n\n"
            f"输出JSON：{{\"exercises\":[{{\"question_type\":\"choice\",\"difficulty\":\"medium\","
            f"\"stem\":\"题干\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"answer\":\"A\","
            f"\"explanation\":\"一句解析\"}},...共{n}道]}}"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p, max_tokens=800))

    def _llm_diagnose_mistake(self, question, std_ans, stu_ans):
        sys_p = "你是一位教学诊断专家。只输出纯 JSON，不含 markdown 代码块。"
        usr_p = (
            f"题目：{question}\n标准答案：{std_ans}\n学生答案：{stu_ans}\n\n"
            "输出 JSON 包含：is_correct, error_type, error_reason, "
            "correct_steps(list), review_suggestion"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p))

    def _llm_generate_exam(self, fragments, cfg):
        ctx = "\n---\n".join(fragments[:5])
        count = cfg.get("total_questions", 20)
        sys_p = "你是一位命题专家。只输出纯 JSON，不含 markdown 代码块。"
        usr_p = (
            f"根据以下教材片段，生成包含 {count} 题的试卷。\n\n"
            f"教材片段：\n{ctx}\n\n"
            "输出 JSON：{title, instructions, questions: [{stem, options, answer, explanation, score}]}"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p))

    def _llm_generate_micro_lesson(self, fragments, topic, duration):
        ctx = "\n---\n".join(fragments[:3])[:500]
        min_dur = duration // 60
        sys_p = "你是微课制作专家。只输出纯JSON，不含markdown，内容简洁。"
        usr_p = (
            f"为「{topic}」生成{min_dur}分钟微课提纲。\n参考：{ctx}\n\n"
            "输出JSON：{\"title\":\"...\",\"objectives\":[2条],\"outline\":[3段],"
            "\"script_segments\":[{\"segment\":1,\"title\":\"...\",\"content\":\"50字\"},"
            "{\"segment\":2,\"title\":\"...\",\"content\":\"50字\"},"
            "{\"segment\":3,\"title\":\"...\",\"content\":\"50字\"}],"
            "\"blackboard_notes\":\"关键公式\",\"practice_questions\":[\"一道例题\"]}"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p, max_tokens=900))

    def _llm_generate_ppt(self, fragments, topic):
        ctx = "\n---\n".join(fragments[:3])[:500]
        sys_p = "你是课件制作专家。只输出纯JSON，不含markdown，内容简洁。"
        usr_p = (
            f"为「{topic}」生成PPT框架（5张幻灯片）。参考：{ctx}\n\n"
            "输出JSON：{\"title\":\"...\",\"slides\":["
            "{\"slide_title\":\"导入\",\"content\":[\"要点1\",\"要点2\"],\"speaker_notes\":\"一句话\"},"
            "{\"slide_title\":\"核心概念\",\"content\":[\"要点\"],\"formula\":\"\",\"speaker_notes\":\"\"},"
            "{\"slide_title\":\"例题\",\"content\":[\"例题描述\"],\"speaker_notes\":\"\"},"
            "{\"slide_title\":\"小结\",\"content\":[\"重点1\",\"重点2\"],\"speaker_notes\":\"\"},"
            "{\"slide_title\":\"练习\",\"content\":[\"练习题\"],\"speaker_notes\":\"\"}]}"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p, max_tokens=800))

    def _multimodal_homework_tutor(self, question, student_answer, mode, image_base64):
        """用多模态 LLM 处理包含图片的作业辅导。"""
        from ..services.multimodal import MultimodalClient

        client = MultimodalClient()
        import base64
        image_data = base64.b64decode(image_base64)

        prompt = f"""这是一道学习题目图片。请先识别图片中的完整题干、选项、公式和图形，再解答。

用户问题：{question or "请解答图片中的题目"}
学生答案：{student_answer or "未提供"}
辅导模式：{mode}

只输出纯 JSON，不要 markdown，不要解释 JSON 外的文字。
JSON 字段必须包含：
{{
  "answer_status": "ok 或 insufficient",
  "question_recognition": "识别出的完整题干/公式/选项",
  "knowledge_point": "知识点",
  "question_type": "题型",
  "solving_approach": "给学生看的简洁解题思路，不要写内部模板",
  "formulas": ["用到的公式，可为空"],
  "complete_steps": ["真正代入题目条件的步骤"],
  "final_answer": "最终答案，能算出时必须填写",
  "common_mistakes": ["易错点"],
  "next_step_hint": "下一步追问建议"
}}

要求：
1. 如果无法识别图片中的题干或关键公式，answer_status 写 insufficient，并说明缺少什么。
2. 禁止输出“识别知识点、整理条件、选择方法、检查答案”这类通用模板。
3. 数学题要保留公式；选择题要给选项答案并说明关键选项为什么对/错。
"""
        result_text = client.understand_image(
            image_data=image_data,
            question=prompt,
            system_prompt="你是严谨的图片题解答助手，擅长识别中文题目、数学公式和选项题。只输出纯 JSON。",
        )
        parsed = self._parse_json_response(result_text)
        if parsed and "raw" not in parsed:
            return parsed

        # 兜底：把多模态结果包装为 dict
        return {
            "solving_approach": result_text[:500],
            "complete_steps": [result_text],
            "final_answer": "",
            "common_mistakes": [],
            "note": "此为多模态模型直接输出，已包含图片理解结果",
        }

    def _llm_homework_tutor(self, question, student_answer, mode):
        sys_p = (
            "你是一位严谨的作业辅导老师。只输出纯 JSON，不含 markdown 代码块。"
            "必须真正代入题目求解，禁止输出通用模板。"
            "如果题干不完整或图片无法识别，answer_status 必须为 insufficient，并说明缺少什么。"
        )
        usr_p = (
            f"题目：{question}\n学生答案：{student_answer}\n辅导模式：{mode}\n\n"
            "输出 JSON 字段：answer_status(ok/insufficient), question_recognition, knowledge_point, question_type, "
            "solving_approach, complete_steps(list), formulas(list), final_answer, common_mistakes(list), next_step_hint。\n"
            "要求：complete_steps 必须引用题目中的具体表达式、数字或条件；final_answer 能算出时必须填写。"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p))

    def _normalize_homework_result(self, result: Dict[str, Any], question: str, image_based: bool = False) -> Dict[str, Any]:
        """Flatten workflow output and reject empty/template tutoring as a real answer."""
        data = result or {}
        if "final_package" in data and isinstance(data["final_package"], dict):
            data = data["final_package"]
        if "final_package_structure" in data and isinstance(data["final_package_structure"], dict):
            data = data["final_package_structure"]
        if "tutor_result" in data and isinstance(data["tutor_result"], dict):
            data = data["tutor_result"]
        if "tutoring" in data and isinstance(data["tutoring"], dict):
            data = data["tutoring"]

        if "steps" in data and "complete_steps" not in data:
            data["complete_steps"] = data.get("steps") or []
        if "hints" in data and "next_step_hint" not in data:
            hints = data.get("hints") or []
            data["next_step_hint"] = hints[0] if hints else ""
        if "mistake_tips" in data and "common_mistakes" not in data:
            tips = data.get("mistake_tips")
            data["common_mistakes"] = tips if isinstance(tips, list) else ([tips] if tips else [])

        steps = [str(item).strip() for item in data.get("complete_steps", []) if str(item).strip()]
        summary = str(data.get("solving_approach", "")).strip()
        final_answer = str(data.get("final_answer", "")).strip()
        recognition = str(data.get("question_recognition", "")).strip()

        if self._is_template_homework_answer(summary, steps, final_answer):
            return self._insufficient_homework_result(
                question=question,
                reason="当前模型没有把题目代入求解，只返回了通用辅导模板。",
                image_based=image_based,
            )

        if not final_answer and not steps and not summary:
            return self._insufficient_homework_result(
                question=question,
                reason="未获得有效解题内容。",
                image_based=image_based,
            )

        data["answer_status"] = data.get("answer_status") or "ok"
        data["question_recognition"] = recognition or question
        data["complete_steps"] = steps
        data.setdefault("common_mistakes", [])
        data.setdefault("formulas", [])
        data.setdefault("next_step_hint", "可以继续追问某一步为什么这样做，或让我生成同类题。")
        return data

    def _is_template_homework_answer(self, summary: str, steps: List[str], final_answer: str) -> bool:
        if final_answer:
            return False
        joined = f"{summary} {' '.join(steps)}"
        template_markers = [
            "识别题目",
            "整理条件",
            "选择方法",
            "完成推导",
            "检查答案",
            "列出已知条件",
            "先识别题目考查",
        ]
        hits = sum(1 for marker in template_markers if marker in joined)
        return hits >= 2

    def _insufficient_homework_result(self, question: str, reason: str, image_based: bool = False) -> Dict[str, Any]:
        missing = "图片题干/OCR识别结果" if image_based else "可用于计算或推导的有效模型输出"
        return {
            "answer_status": "insufficient",
            "question_recognition": question,
            "knowledge_point": "",
            "question_type": "",
            "solving_approach": reason,
            "complete_steps": [
                f"缺少：{missing}",
                "请补充完整题干，或检查模型/OCR服务是否正常返回。",
            ],
            "formulas": [],
            "final_answer": "",
            "common_mistakes": ["不要把通用解题模板当成真实答案。"],
            "next_step_hint": "把题目文字粘贴出来后，我再按题目逐步求解。",
            "insufficient_data_warning": reason,
        }

    def _llm_knowledge_graph(self, fragments):
        ctx = "\n---\n".join(fragments[:5])
        sys_p = "你是一位知识图谱专家。只输出纯 JSON，不含 markdown 代码块。"
        usr_p = (
            f"根据以下教材片段，生成知识图谱节点和边。\n\n"
            f"教材片段：\n{ctx}\n\n"
            "输出 JSON：{nodes: [{id, name, type, definition}], "
            "edges: [{source, target, relation_type, label}]}"
        )
        return self._parse_json_response(self._call_llm(sys_p, usr_p))

    def _llm_profile(self, records):
        sys_p = "你是一位学习分析专家。只输出纯 JSON，不含 markdown 代码块。"
        usr_p = (
            f"根据以下学习记录生成学生画像：\n{records}\n\n"
            "输出 JSON 包含：stage, progress, mastered_points(list), "
            "weak_points(list), error_patterns(list), recommendations(list)"
        )
        return self._parse_json_response(self._call_llm(sys_p, str(records)))


# ─── 单例 ────────────────────────────────────────────────────
agent_service = AgentService()
