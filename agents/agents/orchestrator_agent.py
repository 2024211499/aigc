# -*- coding: utf-8 -*-
import sys
import os
import time
from typing import List, Callable, Optional, Dict, Any
from ..core.models import WorkflowResult, WorkflowStep, AgentCall
from ..core.llm_client import call_llm, extract_json_from_response
from ..core.prompt_contract import get_agent_capabilities, get_platform_function_catalog
from .course_structure_agent import generate_course_structure, refine_course_structure
from .knowledge_graph_agent import generate_knowledge_graph, extend_knowledge_graph
from .planner_agent import generate_study_plan, modify_study_plan
from .keypoint_agent import generate_keypoint_analysis, modify_keypoint_analysis
from .explanation_agent import generate_layered_explanation, modify_explanation
from .exercise_agent import generate_exercises, modify_exercises
from .homework_tutor_agent import generate_homework_tutor, modify_homework_tutor
from .mistake_diagnosis_agent import generate_mistake_diagnosis, modify_mistake_diagnosis
from .profile_agent import generate_student_profile, update_student_profile
from .adaptive_path_agent import generate_adaptive_path, update_adaptive_path
from .exam_agent import generate_exam_paper, check_exam_paper
from .micro_lesson_agent import generate_micro_lesson
from .ppt_agent import generate_ppt_content
from .quality_review_agent import review_content, review_and_fix


class AgentRegistry:
    def __init__(self):
        self._agents = {}
        self._register_all_agents()

    def _register_all_agents(self):
        self.register("course_structure", {
            "generate": generate_course_structure,
            "modify": refine_course_structure,
            "description": "课程结构分析智能体"
        })
        self.register("knowledge_graph", {
            "generate": generate_knowledge_graph,
            "modify": extend_knowledge_graph,
            "description": "知识图谱智能体"
        })
        self.register("study_plan", {
            "generate": generate_study_plan,
            "modify": modify_study_plan,
            "description": "学习计划智能体"
        })
        self.register("keypoint", {
            "generate": generate_keypoint_analysis,
            "modify": modify_keypoint_analysis,
            "description": "重点难点智能体"
        })
        self.register("explanation", {
            "generate": generate_layered_explanation,
            "modify": modify_explanation,
            "description": "分层讲解智能体"
        })
        self.register("exercise", {
            "generate": generate_exercises,
            "modify": modify_exercises,
            "description": "习题生成智能体"
        })
        self.register("homework_tutor", {
            "generate": generate_homework_tutor,
            "modify": modify_homework_tutor,
            "description": "作业辅导智能体"
        })
        self.register("mistake_diagnosis", {
            "generate": generate_mistake_diagnosis,
            "modify": modify_mistake_diagnosis,
            "description": "错题诊断智能体"
        })
        self.register("profile", {
            "generate": generate_student_profile,
            "modify": update_student_profile,
            "description": "学习画像智能体"
        })
        self.register("adaptive_path", {
            "generate": generate_adaptive_path,
            "modify": update_adaptive_path,
            "description": "自适应路径智能体"
        })
        self.register("exam", {
            "generate": generate_exam_paper,
            "check": check_exam_paper,
            "description": "智能组卷智能体"
        })
        self.register("micro_lesson", {
            "generate": generate_micro_lesson,
            "description": "微课脚本智能体"
        })
        self.register("ppt", {
            "generate": generate_ppt_content,
            "description": "PPT内容智能体"
        })
        self.register("quality_review", {
            "review": review_content,
            "review_and_fix": review_and_fix,
            "description": "质量审查智能体"
        })

    def register(self, name: str, agent: dict):
        self._agents[name] = agent

    def get(self, name: str) -> dict:
        return self._agents.get(name)

    def _build_generation_metadata(
        self,
        workflow_type: str,
        course_name: str = "",
        chapter_name: str = "",
        fragments: Optional[List[str]] = None,
        knowledge_points: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        fragments = fragments or []
        knowledge_points = knowledge_points or []
        metadata = {
            "workflow_type": workflow_type,
            "course_name": course_name,
            "chapter_name": chapter_name,
            "source_fragment_count": len(fragments),
            "source_char_count": sum(len(str(item)) for item in fragments),
            "knowledge_point_count": len(knowledge_points),
            "knowledge_points_preview": knowledge_points[:8],
            "has_source_material": bool(fragments),
            "quality_gate_enabled": True,
        }
        if extra:
            metadata.update(extra)
        return metadata

    def _safe_quality_review(
        self,
        original_materials: Dict[str, Any],
        generated_result: Dict[str, Any],
        references: Optional[List[str]],
        task_type: str,
        on_token: Callable = None,
    ) -> Dict[str, Any]:
        try:
            return review_and_fix(
                original_materials=original_materials,
                generated_result=generated_result,
                references=references or [],
                task_type=task_type,
                on_token=on_token,
            )
        except Exception as exc:
            return {
                "review": {
                    "is_passed": False,
                    "issues": [{
                        "field": "quality_review",
                        "issue_type": "review_failed",
                        "severity": "major",
                        "description": str(exc),
                        "suggestion": "Retry quality review or inspect the generated result manually.",
                    }],
                    "suggestions": ["Quality review failed; keep the original result with manual review required."],
                    "credibility_score": 0.0,
                    "need_regenerate_fields": [],
                    "review_summary": "Quality review did not complete.",
                },
                "final_result": generated_result,
                "was_fixed": False,
                "review_error": str(exc),
            }

    def _build_learning_actions(
        self,
        knowledge_points: Optional[List[str]] = None,
        weak_points: Optional[List[str]] = None,
        has_exercises: bool = False,
        has_diagnosis: bool = False,
    ) -> List[Dict[str, str]]:
        knowledge_points = knowledge_points or []
        weak_points = weak_points or []
        actions: List[Dict[str, str]] = []
        if weak_points:
            actions.append({
                "type": "review",
                "title": "Review weak points first",
                "description": "Start with: " + ", ".join(map(str, weak_points[:3])),
            })
        elif knowledge_points:
            actions.append({
                "type": "preview",
                "title": "Preview core concepts",
                "description": "Focus on: " + ", ".join(map(str, knowledge_points[:3])),
            })
        if has_exercises:
            actions.append({
                "type": "practice",
                "title": "Finish a mixed practice set",
                "description": "Do easy questions first, then retry medium and hard questions after checking explanations.",
            })
        if has_diagnosis:
            actions.append({
                "type": "remediate",
                "title": "Patch the diagnosed gap",
                "description": "Use the diagnosis to review prerequisite knowledge before doing variant questions.",
            })
        if not actions:
            actions.append({
                "type": "clarify",
                "title": "Add more source material",
                "description": "Provide textbook fragments, mistake records, or learning logs for richer personalization.",
            })
        return actions

    def list_agents(self) -> dict:
        return {name: info.get("description", "") for name, info in self._agents.items()}

    def call(self, name: str, action: str = "generate", **kwargs) -> Any:
        agent = self._agents.get(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found")
        func = agent.get(action)
        if not func:
            raise ValueError(f"Action '{action}' not found for agent '{name}'")
        return func(**kwargs)


class OrchestratorAgent:
    def __init__(self):
        self.registry = AgentRegistry()
        self._workflow_map = {
            "learning_package": {
                "name": "学习包生成流程",
                "keywords": ["学习包", "学习计划", "章节学习", "生成学习", "学习方案"],
                "function": self.run_learning_package_workflow
            },
            "exam": {
                "name": "试卷生成流程",
                "keywords": ["试卷", "考试", "组卷", "测试卷", "模拟卷"],
                "function": self.run_exam_workflow
            },
            "exercise": {
                "name": "习题生成流程",
                "keywords": ["练习题", "出几道题", "做题", "练习一下", "出点题", "习题", "做几道题", "练练手"],
                "function": self.run_exercise_workflow
            },
            "micro_lesson": {
                "name": "微课生成流程",
                "keywords": ["微课", "视频脚本", "教学视频", "微课脚本"],
                "function": self.run_micro_lesson_workflow
            },
            "ppt": {
                "name": "PPT课件生成流程",
                "keywords": ["ppt", "PPT", "课件", "幻灯片", "演示文稿"],
                "function": self.run_ppt_workflow
            },
            "homework_tutor": {
                "name": "作业辅导流程",
                "keywords": ["作业", "辅导", "题目讲解", "解题", "答疑"],
                "function": self.run_homework_tutor_workflow
            },
            "knowledge_graph": {
                "name": "知识图谱生成流程",
                "keywords": ["知识图谱", "知识关系", "知识点关联", "知识网络"],
                "function": self.run_knowledge_graph_workflow
            },
            "student_profile": {
                "name": "学生画像生成流程",
                "keywords": ["学生画像", "学习分析", "学习报告", "学习情况"],
                "function": self.run_student_profile_workflow
            }
        }

    def _build_generation_metadata(
        self,
        workflow_type: str,
        course_name: str = "",
        chapter_name: str = "",
        fragments: Optional[List[str]] = None,
        knowledge_points: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.registry._build_generation_metadata(
            workflow_type=workflow_type,
            course_name=course_name,
            chapter_name=chapter_name,
            fragments=fragments,
            knowledge_points=knowledge_points,
            extra=extra,
        )

    def _safe_quality_review(
        self,
        original_materials: Dict[str, Any],
        generated_result: Dict[str, Any],
        references: Optional[List[str]],
        task_type: str,
        on_token: Callable = None,
    ) -> Dict[str, Any]:
        return self.registry._safe_quality_review(
            original_materials=original_materials,
            generated_result=generated_result,
            references=references,
            task_type=task_type,
            on_token=on_token,
        )

    def _build_learning_actions(
        self,
        knowledge_points: Optional[List[str]] = None,
        weak_points: Optional[List[str]] = None,
        has_exercises: bool = False,
        has_diagnosis: bool = False,
    ) -> List[Dict[str, str]]:
        return self.registry._build_learning_actions(
            knowledge_points=knowledge_points,
            weak_points=weak_points,
            has_exercises=has_exercises,
            has_diagnosis=has_diagnosis,
        )

    def list_agents(self) -> dict:
        return self.registry.list_agents()

    def list_agent_capabilities(self) -> dict:
        return get_agent_capabilities()

    def list_platform_functions(self) -> dict:
        return get_platform_function_catalog()

    def list_workflows(self) -> dict:
        return {key: value["name"] for key, value in self._workflow_map.items()}

    def call_agent(self, agent_name: str, action: str = "generate", **kwargs) -> Any:
        return self.registry.call(agent_name, action, **kwargs)

    def recognize_task(self, user_input: str) -> str:
        input_lower = user_input.lower()
        
        scores = {}
        for workflow_key, workflow_info in self._workflow_map.items():
            score = 0
            for keyword in workflow_info["keywords"]:
                if keyword.lower() in input_lower:
                    score += len(keyword)
            if score > 0:
                scores[workflow_key] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return "learning_package"

    def recognize_task_by_llm(self, user_input: str) -> str:
        workflow_list = "\n".join([
            f"- {key}: {value['name']}（关键词：{', '.join(value['keywords'])}）" 
            for key, value in self._workflow_map.items()
        ])
        
        prompt = f"""你是一个意图识别专家，负责精准分析用户的需求并匹配到对应的功能。

【可用功能列表】
{workflow_list}

【用户输入】
{user_input}

【任务】
请分析用户的输入，精准判断用户想要使用哪个功能。

【核心识别逻辑】
第一步：提取用户输入中的关键动作词和对象词
第二步：根据关键动作词匹配功能
  - 动作词包含"PPT/课件/幻灯片" → ppt
  - 动作词包含"微课/视频/录课" → micro_lesson
  - 动作词包含"学习包/学习计划/系统学习" → learning_package
  - 动作词包含"出几道题/练习题/练习一下/做几道题/练练手/出点题/练练/出X道题" → exercise
  - 动作词包含"试卷/考试/组卷/测试卷/模拟卷/出套题/考考我" → exam
  - 动作词包含"作业/辅导/解答/讲解题目" → homework_tutor
  - 动作词包含"知识图谱/知识关系/知识网络" → knowledge_graph
  - 动作词包含"学生画像/学习分析/学习报告" → student_profile
第三步：如果同时匹配多个功能，选择最具体的那个

【严格区分规则】
- "PPT/课件/幻灯片" ≠ "微课/视频脚本"（前者是静态课件，后者是视频脚本）
- "学习包/学习计划" ≠ "试卷/测试"（前者是学习内容，后者是测试）
- "作业辅导" 是针对具体题目的讲解，不是系统性学习
- **exercise（习题生成）≠ exam（试卷生成）**：
  - exercise：用户说"出几道题"、"练习题"、"练习一下"、"做几道题"、"练练手"、"出X道题"（X是数字）、"练练"，只要几道练习题，不要完整试卷
  - exam：用户说"试卷"、"考试"、"组卷"、"测试卷"、"模拟卷"、"出套题"、"考考我"，需要完整试卷（含考试时间、总分、题型比例等）
  - 关键判断：如果用户提到具体题数（如"2-3道"、"5道"）或说"练练"、"练习"，一定是 exercise
  - 关键判断：如果用户说"试卷"、"考试"、"测试"，一定是 exam
- 用户说"学习一下/系统学习/全面学习" → learning_package
- 用户说"出几道题/练习题/练习一下/做几道题/练练手/出X道题/练练" → exercise
- 用户说"试卷/考试/组卷/测试卷/出套题/考考我" → exam
- 用户说"做PPT/生成课件/做课件" → ppt
- 用户说"做微课/录课/视频脚本" → micro_lesson

【输出格式】
请输出JSON格式：
{{
  "recognized_workflow": "功能key（必须从功能列表中选择一个）",
  "confidence": 0.95,
  "reason": "识别理由"
}}

【示例】
用户输入："帮我生成一个学习包"
输出：{{"recognized_workflow": "learning_package", "confidence": 0.95, "reason": "用户明确要求生成学习包"}}

用户输入："我想做一套测试卷来检验学习成果"
输出：{{"recognized_workflow": "exam", "confidence": 0.9, "reason": "用户提到测试卷，对应试卷生成功能"}}

用户输入："给我讲解一下这道题怎么做"
输出：{{"recognized_workflow": "homework_tutor", "confidence": 0.9, "reason": "用户要求题目讲解，对应作业辅导功能"}}

用户输入："生成ppt"
输出：{{"recognized_workflow": "ppt", "confidence": 0.95, "reason": "用户明确要求生成PPT课件"}}

用户输入："帮我做一个微课"
输出：{{"recognized_workflow": "micro_lesson", "confidence": 0.9, "reason": "用户明确要求生成微课"}}

用户输入："我想系统学习一下函数极限"
输出：{{"recognized_workflow": "learning_package", "confidence": 0.85, "reason": "用户说系统学习，对应学习包生成功能"}}

用户输入："帮我出套题考考我"
输出：{{"recognized_workflow": "exam", "confidence": 0.9, "reason": "用户说出套题考考我，对应试卷生成"}}

用户输入："给我出几道题目练习一下"
输出：{{"recognized_workflow": "exercise", "confidence": 0.95, "reason": "用户说出几道题练习，对应习题生成，不是完整试卷"}}

用户输入："做几道题练练手"
输出：{{"recognized_workflow": "exercise", "confidence": 0.9, "reason": "用户说做几道题练练手，对应习题生成"}}

用户输入："给我出2-3道题目练练"
输出：{{"recognized_workflow": "exercise", "confidence": 0.95, "reason": "用户提到具体题数2-3道和练练，对应习题生成，不是试卷"}}

用户输入："出5道题给我做"
输出：{{"recognized_workflow": "exercise", "confidence": 0.95, "reason": "用户说出5道题，对应习题生成"}}

用户输入："帮我出10道练习题"
输出：{{"recognized_workflow": "exercise", "confidence": 0.95, "reason": "用户说出10道练习题，对应习题生成"}}

用户输入："做个课件给我看看"
输出：{{"recognized_workflow": "ppt", "confidence": 0.9, "reason": "用户说做课件，对应PPT生成"}}

用户输入："这道题我不会做，帮我解答"
输出：{{"recognized_workflow": "homework_tutor", "confidence": 0.9, "reason": "用户要求解答题目，对应作业辅导"}}

用户输入："看看知识点之间的关系"
输出：{{"recognized_workflow": "knowledge_graph", "confidence": 0.85, "reason": "用户想看知识点关系，对应知识图谱"}}

请只输出JSON，不要其他内容。"""

        try:
            response = call_llm(prompt, system_prompt="你是一个专业的意图识别专家，能够精准理解用户的需求并匹配到对应的功能。严格区分相似功能，不混淆。", temperature=0.1)
            result = extract_json_from_response(response)
            
            if result and "recognized_workflow" in result:
                workflow_key = result["recognized_workflow"]
                if workflow_key in self._workflow_map:
                    return workflow_key
        except Exception as e:
            print(f"[LLM意图识别失败，回退到关键词匹配: {e}]")
        
        return self.recognize_task(user_input)

    def extract_params_from_input(self, user_input: str) -> dict:
        prompt = f"""你是一个参数提取助手，负责从用户输入中提取关键参数。

【用户输入】
{user_input}

【任务】
提取以下参数（如果存在）：
1. exercise_count: 题目数量（整数），如"出2道题"→2，"出5道"→5
2. study_days: 学习天数，如"帮我制定7天的学习计划"→7
3. daily_time: 每天学习时间（分钟），如"每天学1小时"→60
4. topic: 主题/知识点，如"关于函数极限的内容"→"函数极限"
5. style: 风格，如"生动一点"→"生动"
6. duration: 时长（秒），如"5分钟的微课"→300

【输出格式】
请输出JSON格式，只包含提取到的参数，没有则不输出该字段：
{{
  "exercise_count": 2,
  "study_days": 7,
  "daily_time": 60,
  "topic": "函数极限",
  "style": "生动",
  "duration": 300
}}

【示例】
用户输入："给我出2道题"
输出：{{"exercise_count": 2}}

用户输入："帮我制定一个7天的学习计划，每天学1小时"
输出：{{"study_days": 7, "daily_time": 60}}

用户输入："生成一个关于集合的微课，5分钟，生动一点"
输出：{{"topic": "集合", "duration": 300, "style": "生动"}}

用户输入："出3道关于极限的练习题"
输出：{{"exercise_count": 3, "topic": "极限"}}

请只输出JSON，不要其他内容。"""

        try:
            response = call_llm(prompt, system_prompt="你是一个专业的参数提取助手，能够准确从用户输入中提取数值和关键信息。", temperature=0.1)
            result = extract_json_from_response(response)
            if result:
                return result
        except Exception:
            pass
        
        return {}

    def dispatch(self, task_type: str, **kwargs) -> dict:
        workflow_info = self._workflow_map.get(task_type)
        if not workflow_info:
            raise ValueError(f"Unknown task type: {task_type}")
        return workflow_info["function"](**kwargs)

    def run_learning_package_workflow(
        self,
        course_id: str = "",
        chapter_name: str = "",
        user_profile: dict = None,
        fragments: List[str] = None,
        study_days: int = 7,
        daily_time: int = 60,
        exam_target: str = "",
        exercise_count: int = 10,
        max_explanation_count: int = 5,
        on_token: Callable = None
    ) -> dict:
        if user_profile is None:
            user_profile = {}
        if fragments is None:
            fragments = []
        
        workflow_result = WorkflowResult(
            workflow_type="learning_package",
            workflow_name="学习包生成流程",
            status="running"
        )

        chapter_text = "\n".join(fragments) if isinstance(fragments, list) else str(fragments)

        # Step 1: 先分析课程结构，自动提取课程名、章节名、知识点
        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="课程结构分析",
            agent_calls=[AgentCall(agent_name="course_structure", agent_function="generate_course_structure", description="分析章节内容，自动提取课程名、章节名、知识点结构")]
        ))
        course_structure = generate_course_structure(
            chapter_text=chapter_text,
            fragment_id=course_id,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("course_structure")
        
        # 从课程结构中自动提取信息
        auto_course_name = course_structure.get("course_name", "")
        auto_chapter_name = course_structure.get("chapter_name", chapter_name)
        auto_knowledge_points = [kp.get("name", "") for kp in course_structure.get("all_knowledge_points", [])]
        
        print(f"  [自动识别] 课程名: {auto_course_name}")
        print(f"  [自动识别] 章节名: {auto_chapter_name}")
        print(f"  [自动识别] 知识点数量: {len(auto_knowledge_points)}")

        # Step 2: 生成学生画像（作为后续所有生成的基础）
        workflow_result.steps.append(WorkflowStep(
            step_number=2,
            step_name="学生画像分析",
            agent_calls=[AgentCall(agent_name="profile", agent_function="generate_student_profile", description="分析学生特征，生成个性化画像")]
        ))
        _raw_mistakes = user_profile.get("history_mistakes", [])
        _mistake_records = [
            {"question": str(m), "error_type": "未知", "error_reason": "未知"}
            for m in (_raw_mistakes if isinstance(_raw_mistakes, list) else [])
        ]
        student_profile = generate_student_profile(
            learning_records=[],
            answer_records=[],
            mistake_records=_mistake_records,
            chapter_progress={},
            test_scores=[],
            study_time={},
            course_name=auto_course_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("profile")

        # 从画像中提取关键信息，用于后续个性化生成
        # StudentProfile 返回 learning_pace / weak_knowledge_points，不是 student_level / weak_points
        extracted_level = user_profile.get("student_level",
                            student_profile.get("learning_pace", "中等"))
        extracted_weak_points = (student_profile.get("weak_knowledge_points")
                                 or user_profile.get("weak_points", []))
        extracted_learning_style = user_profile.get("learning_style", "通用")
        history_mistakes = _raw_mistakes
        
        print(f"  [学生画像] 学习水平: {extracted_level}")
        print(f"  [学生画像] 学习风格: {extracted_learning_style}")
        print(f"  [学生画像] 薄弱知识点: {len(extracted_weak_points)}个")

        # Step 3: 重点难点分析（结合学生画像）
        workflow_result.steps.append(WorkflowStep(
            step_number=3,
            step_name="重点难点分析",
            agent_calls=[AgentCall(agent_name="keypoint", agent_function="generate_keypoint_analysis", description="提取重点、难点、考点、易错点")]
        ))
        keypoint_result = generate_keypoint_analysis(
            fragments=fragments,
            knowledge_points=auto_knowledge_points,
            wrong_questions=history_mistakes,
            exam_target=exam_target,
            chapter_name=auto_chapter_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("keypoint")

        # Step 4: 学习计划生成（基于学生画像个性化）
        workflow_result.steps.append(WorkflowStep(
            step_number=4,
            step_name="学习计划生成",
            agent_calls=[AgentCall(agent_name="study_plan", agent_function="generate_study_plan", description="根据学生画像生成个性化学习计划")]
        ))
        study_plan = generate_study_plan(
            course_name=auto_course_name,
            chapter_name=auto_chapter_name,
            fragments=fragments,
            knowledge_points=auto_knowledge_points,
            study_days=study_days,
            daily_study_time=daily_time,
            exam_target=exam_target,
            learning_foundation=extracted_level,
            weak_points=extracted_weak_points,
            learning_style=extracted_learning_style,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("study_plan")

        # Step 5: 分层讲解生成（根据学生水平调整难度）
        workflow_result.steps.append(WorkflowStep(
            step_number=5,
            step_name="知识点讲解",
            agent_calls=[AgentCall(agent_name="explanation", agent_function="generate_layered_explanation", description="根据学生水平生成个性化讲解")]
        ))
        explanations = []
        target_points = auto_knowledge_points[:max_explanation_count] if auto_knowledge_points else []
        for kp in target_points:
            exp = generate_layered_explanation(
                knowledge_point=kp,
                fragments=fragments,
                student_level=extracted_level,
                learning_style=extracted_learning_style,
                weak_points=extracted_weak_points,
                explanation_mode="textbook_sync",
                chapter_name=auto_chapter_name,
                on_token=on_token
            )
            explanations.append(exp)
        workflow_result.agent_sequence.append("explanation")

        # Step 6: 习题生成（根据学生画像调整难度和针对性）
        workflow_result.steps.append(WorkflowStep(
            step_number=6,
            step_name="习题生成",
            agent_calls=[AgentCall(agent_name="exercise", agent_function="generate_exercises", description="根据学生画像生成个性化习题")]
        ))
        exercises = generate_exercises(
            fragments=fragments,
            course_name=auto_course_name,
            chapter_name=auto_chapter_name,
            knowledge_points=auto_knowledge_points,
            question_count=exercise_count,
            student_profile={
                "student_level": extracted_level,
                "weak_points": extracted_weak_points,
                "learning_style": extracted_learning_style,
            },
            wrong_questions=[
                {"question": str(m)} for m in history_mistakes
            ] if history_mistakes else [],
            on_token=on_token
        )
        workflow_result.agent_sequence.append("exercise")

        # Step 7: 质量审查
        workflow_result.steps.append(WorkflowStep(
            step_number=7,
            step_name="质量审查",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="审查所有生成内容质量")]
        ))
        original_materials = {
            "course_structure": course_structure,
            "student_profile": student_profile,
            "keypoint": keypoint_result,
            "study_plan": study_plan,
            "explanations": explanations,
            "exercises": exercises
        }
        quality_review = review_and_fix(
            original_materials=original_materials,
            generated_result={
                "learning_package": {
                    "course_structure": course_structure,
                    "keypoint_analysis": keypoint_result,
                    "study_plan": study_plan,
                    "explanations": explanations,
                    "exercises": exercises
                }
            },
            references=fragments,
            task_type="learning_package",
            on_token=on_token
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "course_id": course_id,
            "course_name": auto_course_name,
            "chapter_name": auto_chapter_name,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="learning_package",
                course_name=auto_course_name,
                chapter_name=auto_chapter_name,
                fragments=fragments,
                knowledge_points=auto_knowledge_points,
                extra={
                    "study_days": study_days,
                    "daily_time": daily_time,
                    "exercise_count": exercise_count,
                    "has_student_profile": bool(user_profile),
                },
            ),
            "student_profile": student_profile,
            "course_structure": course_structure,
            "keypoint_analysis": keypoint_result,
            "study_plan": study_plan,
            "explanations": explanations,
            "exercises": exercises,
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                knowledge_points=auto_knowledge_points,
                weak_points=extracted_weak_points,
                has_exercises=True,
            ),
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("学习包生成流程完成")

        return workflow_result.model_dump()

    def run_exam_workflow(
        self,
        course_id: str = "",
        chapters: List[str] = None,
        exam_config: dict = None,
        fragments: List[str] = None,
        on_token: Callable = None
    ) -> dict:
        if exam_config is None:
            exam_config = {}
        if fragments is None:
            fragments = []
        if chapters is None:
            chapters = []
        
        workflow_result = WorkflowResult(
            workflow_type="exam",
            workflow_name="试卷生成流程",
            status="running"
        )

        exam_type = exam_config.get("exam_type", "单元测试")
        question_type_ratio = exam_config.get("question_type_ratio", {})
        difficulty_ratio = exam_config.get("difficulty_ratio", {"easy": 0.3, "medium": 0.5, "hard": 0.2})
        total_questions = exam_config.get("total_questions", 20)
        exam_duration = exam_config.get("exam_duration_minutes", 90)
        total_score = exam_config.get("total_score", 100)
        include_answers = exam_config.get("include_answers", True)
        include_explanations = exam_config.get("include_explanations", True)
        mistake_records = exam_config.get("mistake_records", [])
        weak_points = exam_config.get("weak_points", [])

        chapter_text = "\n".join(fragments) if fragments else ""

        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="课程结构分析",
            agent_calls=[AgentCall(agent_name="course_structure", agent_function="generate_course_structure", description="自动分析章节内容结构")]
        ))
        course_structure = generate_course_structure(
            chapter_text=chapter_text,
            fragment_id=course_id,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("course_structure")
        
        auto_course_name = course_structure.get("course_name", "")
        auto_chapter_name = course_structure.get("chapter_name", "")
        auto_knowledge_points = [kp.get("name", "") for kp in course_structure.get("all_knowledge_points", [])]
        
        print(f"  [自动识别] 课程名: {auto_course_name}")
        print(f"  [自动识别] 章节名: {auto_chapter_name}")

        # Step 2: 生成学生画像（用于个性化组卷）
        workflow_result.steps.append(WorkflowStep(
            step_number=2,
            step_name="学生画像分析",
            agent_calls=[AgentCall(agent_name="profile", agent_function="generate_student_profile", description="分析学生特征，用于个性化组卷")]
        ))
        _mistake_records_fmt = [
            {"question": str(m), "error_type": "未知", "error_reason": "未知"}
            for m in (mistake_records if isinstance(mistake_records, list) else [])
        ]
        student_profile = generate_student_profile(
            learning_records=[],
            answer_records=[],
            mistake_records=_mistake_records_fmt,
            chapter_progress={},
            test_scores=[],
            study_time={},
            course_name=auto_course_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("profile")

        # 从画像中提取关键信息
        extracted_level = exam_config.get("student_level",
                            student_profile.get("learning_pace", "中等"))
        extracted_weak_points = (student_profile.get("weak_knowledge_points") or weak_points)
        extracted_learning_style = exam_config.get("learning_style", "通用")
        extracted_mistakes = mistake_records
        
        print(f"  [学生画像] 学习水平: {extracted_level}")
        print(f"  [学生画像] 薄弱知识点: {len(extracted_weak_points)}个")

        # Step 3: 重点难点分析（结合学生画像）
        workflow_result.steps.append(WorkflowStep(
            step_number=3,
            step_name="重点难点分析",
            agent_calls=[AgentCall(agent_name="keypoint", agent_function="generate_keypoint_analysis", description="提取考点和易错点")]
        ))
        keypoint_result = generate_keypoint_analysis(
            fragments=fragments,
            knowledge_points=auto_knowledge_points,
            wrong_questions=extracted_mistakes,
            exam_target=exam_type,
            chapter_name=auto_chapter_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("keypoint")

        # Step 4: 智能组卷（根据学生画像调整难度和针对性）
        workflow_result.steps.append(WorkflowStep(
            step_number=4,
            step_name="智能组卷",
            agent_calls=[AgentCall(agent_name="exam", agent_function="generate_exam_paper", description="根据学生画像个性化生成试卷")]
        ))
        exam_paper = generate_exam_paper(
            course_name=auto_course_name,
            chapter_range=chapters if chapters else [auto_chapter_name],
            fragments=fragments,
            exam_type=exam_type,
            knowledge_point_range=auto_knowledge_points,
            question_type_ratio=question_type_ratio,
            difficulty_ratio=difficulty_ratio,
            total_questions=total_questions,
            exam_duration_minutes=exam_duration,
            total_score=total_score,
            include_answers=include_answers,
            include_explanations=include_explanations,
            mistake_records=extracted_mistakes,
            weak_points=extracted_weak_points,
            student_level=extracted_level,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("exam")

        # Step 5: 试卷质量审查
        workflow_result.steps.append(WorkflowStep(
            step_number=5,
            step_name="试卷质量审查",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="审查试卷质量和题目合理性")]
        ))
        quality_review = review_and_fix(
            original_materials={
                "course_structure": course_structure,
                "student_profile": student_profile,
                "keypoint": keypoint_result,
                "exam_config": exam_config
            },
            generated_result={"exam_paper": exam_paper},
            references=fragments or [],
            task_type="exam_paper",
            on_token=on_token
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "course_id": course_id,
            "chapters": chapters,
            "course_name": auto_course_name,
            "chapter_name": auto_chapter_name,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="exam",
                course_name=auto_course_name,
                chapter_name=auto_chapter_name,
                fragments=fragments,
                knowledge_points=auto_knowledge_points,
                extra={
                    "exam_type": exam_type,
                    "total_questions": total_questions,
                    "exam_duration": exam_duration,
                },
            ),
            "student_profile": student_profile,
            "exam_type": exam_type,
            "exam_paper": exam_paper,
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                knowledge_points=auto_knowledge_points,
                weak_points=extracted_weak_points,
            ),
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("试卷生成流程完成")

        return workflow_result.model_dump()

    def run_exercise_workflow(
        self,
        course_id: str = "",
        fragments: List[str] = None,
        exercise_count: int = 5,
        user_profile: dict = None,
        on_token: Callable = None
    ) -> dict:
        if user_profile is None:
            user_profile = {}
        if fragments is None:
            fragments = []
        
        workflow_result = WorkflowResult(
            workflow_type="exercise",
            workflow_name="习题生成流程",
            status="running"
        )

        chapter_text = "\n".join(fragments) if fragments else ""

        # Step 1: 课程结构分析
        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="课程结构分析",
            agent_calls=[AgentCall(agent_name="course_structure", agent_function="generate_course_structure", description="自动分析章节内容结构")]
        ))
        course_structure = generate_course_structure(
            chapter_text=chapter_text,
            fragment_id=course_id,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("course_structure")
        
        auto_course_name = course_structure.get("course_name", "")
        auto_chapter_name = course_structure.get("chapter_name", "")
        auto_knowledge_points = [kp.get("name", "") for kp in course_structure.get("all_knowledge_points", [])]
        
        print(f"  [自动识别] 课程名: {auto_course_name}")
        print(f"  [自动识别] 章节名: {auto_chapter_name}")
        print(f"  [自动识别] 知识点数量: {len(auto_knowledge_points)}")

        # Step 2: 学生画像分析
        workflow_result.steps.append(WorkflowStep(
            step_number=2,
            step_name="学生画像分析",
            agent_calls=[AgentCall(agent_name="profile", agent_function="generate_student_profile", description="分析学生特征，用于个性化出题")]
        ))
        student_profile = generate_student_profile(
            learning_records=[],
            answer_records=[],
            mistake_records=[],
            chapter_progress={},
            test_scores=[],
            study_time={},
            course_name=auto_course_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("profile")
        
        extracted_level = student_profile.get("learning_pace", "中等")
        extracted_weak_points = student_profile.get("weak_knowledge_points", [])
        extracted_learning_style = "通用"
        extracted_mistakes = []

        print(f"  [学生画像] 学习节奏: {extracted_level}")
        print(f"  [学生画像] 薄弱知识点: {len(extracted_weak_points)}个")

        # Step 3: 习题生成（根据学生画像个性化出题）
        workflow_result.steps.append(WorkflowStep(
            step_number=3,
            step_name="习题生成",
            agent_calls=[AgentCall(agent_name="exercise", agent_function="generate_exercises", description="根据学生画像生成个性化练习题")]
        ))
        exercises = generate_exercises(
            fragments=fragments,
            course_name=auto_course_name,
            chapter_name=auto_chapter_name,
            knowledge_points=auto_knowledge_points,
            question_count=exercise_count,
            student_profile={
                "student_level": extracted_level,
                "weak_points": extracted_weak_points,
                "learning_style": extracted_learning_style,
            },
            wrong_questions=[],
            on_token=on_token
        )
        workflow_result.agent_sequence.append("exercise")

        workflow_result.steps.append(WorkflowStep(
            step_number=4,
            step_name="Quality review",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="Review exercise quality, answer consistency, source grounding, and difficulty balance.")],
            depends_on=[3]
        ))
        quality_review = self._safe_quality_review(
            original_materials={
                "course_structure": course_structure,
                "student_profile": student_profile,
                "knowledge_points": auto_knowledge_points,
            },
            generated_result={"exercises": exercises},
            references=fragments,
            task_type="exercise",
            on_token=on_token,
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "course_id": course_id,
            "course_name": auto_course_name,
            "chapter_name": auto_chapter_name,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="exercise",
                course_name=auto_course_name,
                chapter_name=auto_chapter_name,
                fragments=fragments,
                knowledge_points=auto_knowledge_points,
                extra={"requested_question_count": exercise_count},
            ),
            "student_profile": student_profile,
            "exercises": quality_review.get("final_result", {}).get("exercises", exercises),
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                knowledge_points=auto_knowledge_points,
                weak_points=extracted_weak_points,
                has_exercises=True,
            )
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("习题生成流程完成")

        return workflow_result.model_dump()

    def run_micro_lesson_workflow(
        self,
        course_id: str = "",
        topic: str = "",
        style: str = "讲解式",
        duration: int = 300,
        fragments: List[str] = None,
        target_level: str = "中等",
        generate_ppt: bool = True,
        on_token: Callable = None
    ) -> dict:
        if fragments is None:
            fragments = []
        
        workflow_result = WorkflowResult(
            workflow_type="micro_lesson",
            workflow_name="微课生成流程",
            status="running"
        )

        chapter_text = "\n".join(fragments) if fragments else ""

        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="课程结构分析",
            agent_calls=[AgentCall(agent_name="course_structure", agent_function="generate_course_structure", description="分析章节内容结构，自动提取课程名、章节名、知识点")]
        ))
        course_structure = generate_course_structure(
            chapter_text=chapter_text,
            fragment_id=course_id,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("course_structure")
        
        auto_course_name = course_structure.get("course_name", "")
        auto_chapter_name = course_structure.get("chapter_name", "")
        auto_knowledge_points = [kp.get("name", "") for kp in course_structure.get("all_knowledge_points", [])]
        
        if not topic and auto_knowledge_points:
            topic = auto_knowledge_points[0]
            print(f"  [自动识别] 选择第一个知识点作为微课主题: {topic}")
        
        print(f"  [自动识别] 课程名: {auto_course_name}")
        print(f"  [自动识别] 章节名: {auto_chapter_name}")
        print(f"  [自动识别] 知识点数量: {len(auto_knowledge_points)}")

        workflow_result.steps.append(WorkflowStep(
            step_number=2,
            step_name="微课脚本生成",
            agent_calls=[AgentCall(agent_name="micro_lesson", agent_function="generate_micro_lesson", description="生成3-5分钟微课脚本")],
            depends_on=[1]
        ))
        micro_lesson = generate_micro_lesson(
            course_name=auto_course_name,
            chapter_name=auto_chapter_name,
            knowledge_point=topic,
            fragments=fragments,
            teaching_style=style,
            video_duration_seconds=duration,
            target_student_level=target_level,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("micro_lesson")

        ppt_content = None
        if generate_ppt:
            workflow_result.steps.append(WorkflowStep(
                step_number=3,
                step_name="PPT内容生成",
                agent_calls=[AgentCall(agent_name="ppt", agent_function="generate_ppt_content", description="根据微课脚本生成PPT结构")],
                depends_on=[2]
            ))
            ppt_content = generate_ppt_content(
                course_name=auto_course_name,
                chapter_name=auto_chapter_name,
                knowledge_point=topic,
                fragments=fragments,
                micro_lesson=micro_lesson,
                teaching_style=style,
                on_token=on_token
            )
            workflow_result.agent_sequence.append("ppt")

        workflow_result.steps.append(WorkflowStep(
            step_number=4 if generate_ppt else 3,
            step_name="质量审查",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="审查微课和PPT内容质量")],
            depends_on=[2, 3] if generate_ppt else [2]
        ))
        quality_review = review_and_fix(
            original_materials={
                "course_structure": course_structure,
                "micro_lesson": micro_lesson,
                "ppt_content": ppt_content
            },
            generated_result={
                "micro_lesson": micro_lesson,
                "ppt_content": ppt_content
            },
            references=fragments,
            task_type="micro_lesson",
            on_token=on_token
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "course_id": course_id,
            "course_name": auto_course_name,
            "chapter_name": auto_chapter_name,
            "topic": topic,
            "style": style,
            "duration": duration,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="micro_lesson",
                course_name=auto_course_name,
                chapter_name=auto_chapter_name,
                fragments=fragments,
                knowledge_points=auto_knowledge_points,
                extra={
                    "topic": topic,
                    "style": style,
                    "duration_seconds": duration,
                    "needs_ppt": generate_ppt,
                },
            ),
            "micro_lesson": micro_lesson,
            "ppt_content": ppt_content,
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                knowledge_points=auto_knowledge_points,
            ),
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("微课生成流程完成")

        return workflow_result.model_dump()

    def run_ppt_workflow(
        self,
        course_id: str = "",
        topic: str = "",
        fragments: List[str] = None,
        teaching_style: str = "生动活泼",
        total_slides: int = 12,
        on_token: Callable = None
    ) -> dict:
        if fragments is None:
            fragments = []
        
        workflow_result = WorkflowResult(
            workflow_type="ppt",
            workflow_name="PPT课件生成流程",
            status="running"
        )

        chapter_text = "\n".join(fragments) if fragments else ""

        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="课程结构分析",
            agent_calls=[AgentCall(agent_name="course_structure", agent_function="generate_course_structure", description="分析章节内容结构，自动提取课程名、章节名、知识点")]
        ))
        course_structure = generate_course_structure(
            chapter_text=chapter_text,
            fragment_id=course_id,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("course_structure")
        
        auto_course_name = course_structure.get("course_name", "")
        auto_chapter_name = course_structure.get("chapter_name", "")
        auto_knowledge_points = [kp.get("name", "") for kp in course_structure.get("all_knowledge_points", [])]
        
        if not topic and auto_knowledge_points:
            topic = auto_knowledge_points[0]
            print(f"  [自动识别] 选择第一个知识点作为PPT主题: {topic}")
        
        print(f"  [自动识别] 课程名: {auto_course_name}")
        print(f"  [自动识别] 章节名: {auto_chapter_name}")
        print(f"  [自动识别] 知识点数量: {len(auto_knowledge_points)}")

        workflow_result.steps.append(WorkflowStep(
            step_number=2,
            step_name="PPT内容生成",
            agent_calls=[AgentCall(agent_name="ppt", agent_function="generate_ppt_content", description="生成PPT页面结构和内容")]
        ))
        ppt_content = generate_ppt_content(
            course_name=auto_course_name,
            chapter_name=auto_chapter_name,
            knowledge_point=topic,
            fragments=fragments,
            teaching_style=teaching_style,
            total_slides=total_slides,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("ppt")

        workflow_result.steps.append(WorkflowStep(
            step_number=3,
            step_name="质量审查",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="审查PPT内容质量")]
        ))
        quality_review = review_and_fix(
            original_materials={
                "course_structure": course_structure,
                "ppt_content": ppt_content
            },
            generated_result={
                "ppt_content": ppt_content
            },
            references=fragments,
            task_type="ppt_content",
            on_token=on_token
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "course_id": course_id,
            "course_name": auto_course_name,
            "chapter_name": auto_chapter_name,
            "topic": topic,
            "teaching_style": teaching_style,
            "total_slides": total_slides,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="ppt",
                course_name=auto_course_name,
                chapter_name=auto_chapter_name,
                fragments=fragments,
                knowledge_points=auto_knowledge_points,
                extra={
                    "topic": topic,
                    "total_slides": total_slides,
                    "teaching_style": teaching_style,
                },
            ),
            "ppt_content": ppt_content,
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                knowledge_points=auto_knowledge_points,
            ),
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("PPT课件生成流程完成")

        return workflow_result.model_dump()

    def run_homework_tutor_workflow(
        self,
        question: str,
        student_answer: str = None,
        fragments: List[str] = None,
        tutor_mode: str = "分步讲解",
        chapter_name: str = "",
        knowledge_point: str = "",
        history_mistakes: List[dict] = None,
        on_token: Callable = None
    ) -> dict:
        workflow_result = WorkflowResult(
            workflow_type="homework_tutor",
            workflow_name="作业辅导流程",
            status="running"
        )

        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="作业辅导",
            agent_calls=[AgentCall(agent_name="homework_tutor", agent_function="generate_homework_tutor", description=f"使用{tutor_mode}模式进行辅导")]
        ))
        tutor_result = generate_homework_tutor(
            question_text=question,
            fragments=fragments or [],
            tutor_mode=tutor_mode,
            student_answer=student_answer or "",
            chapter_name=chapter_name,
            knowledge_point=knowledge_point,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("homework_tutor")

        diagnosis_result = None
        if student_answer:
            workflow_result.steps.append(WorkflowStep(
                step_number=2,
                step_name="错题诊断",
                agent_calls=[AgentCall(agent_name="mistake_diagnosis", agent_function="generate_mistake_diagnosis", description="分析学生答案错误原因")],
                depends_on=[1]
            ))
            diagnosis_result = generate_mistake_diagnosis(
                question=question,
                standard_answer=tutor_result.get("standard_answer", ""),
                student_answer=student_answer,
                fragments=fragments or [],
                explanation=tutor_result.get("explanation", ""),
                history_mistakes=history_mistakes or [],
                chapter_name=chapter_name,
                knowledge_point=knowledge_point,
                on_token=on_token
            )
            workflow_result.agent_sequence.append("mistake_diagnosis")

        workflow_result.steps.append(WorkflowStep(
            step_number=3 if student_answer else 2,
            step_name="Quality review",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="Review tutoring guidance, diagnosis consistency, and next-step usefulness.")],
            depends_on=[2] if student_answer else [1]
        ))
        quality_review = self._safe_quality_review(
            original_materials={
                "question": question,
                "student_answer": student_answer,
                "fragments": fragments or [],
                "chapter_name": chapter_name,
                "knowledge_point": knowledge_point,
                "history_mistakes": history_mistakes or [],
            },
            generated_result={
                "tutor_result": tutor_result,
                "diagnosis_result": diagnosis_result,
            },
            references=fragments or [],
            task_type="homework_tutor",
            on_token=on_token,
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "question": question,
            "student_answer": student_answer,
            "tutor_mode": tutor_mode,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="homework_tutor",
                chapter_name=chapter_name,
                fragments=fragments or [],
                knowledge_points=[knowledge_point] if knowledge_point else [],
                extra={"has_student_answer": bool(student_answer)},
            ),
            "tutor_result": quality_review.get("final_result", {}).get("tutor_result", tutor_result),
            "diagnosis_result": quality_review.get("final_result", {}).get("diagnosis_result", diagnosis_result),
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                knowledge_points=[knowledge_point] if knowledge_point else [],
                has_diagnosis=bool(diagnosis_result),
            )
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("作业辅导流程完成")

        return workflow_result.model_dump()

    def run_knowledge_graph_workflow(
        self,
        course_id: str = "",
        chapter_name: str = "",
        fragments: List[str] = None,
        course_name: str = "",
        on_token: Callable = None
    ) -> dict:
        if fragments is None:
            fragments = []
        
        workflow_result = WorkflowResult(
            workflow_type="knowledge_graph",
            workflow_name="知识图谱生成流程",
            status="running"
        )

        chapter_text = "\n".join(fragments) if isinstance(fragments, list) else str(fragments)

        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="课程结构分析",
            agent_calls=[AgentCall(agent_name="course_structure", agent_function="generate_course_structure", description="提取知识点和结构，自动识别课程名、章节名")]
        ))
        course_structure = generate_course_structure(
            chapter_text=chapter_text,
            fragment_id=course_id,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("course_structure")
        
        auto_course_name = course_structure.get("course_name", "")
        auto_chapter_name = course_structure.get("chapter_name", "")
        knowledge_points = course_structure.get("knowledge_points", [])
        
        if not course_name:
            course_name = auto_course_name
        if not chapter_name:
            chapter_name = auto_chapter_name
        
        print(f"  [自动识别] 课程名: {course_name}")
        print(f"  [自动识别] 章节名: {chapter_name}")
        print(f"  [自动识别] 知识点数量: {len(knowledge_points)}")

        workflow_result.steps.append(WorkflowStep(
            step_number=2,
            step_name="知识图谱生成",
            agent_calls=[AgentCall(agent_name="knowledge_graph", agent_function="generate_knowledge_graph", description="生成知识点关系图谱")],
            depends_on=[1]
        ))
        knowledge_graph = generate_knowledge_graph(
            course_structure=course_structure,
            knowledge_points=knowledge_points,
            fragments=fragments,
            chapter_name=chapter_name,
            course_name=course_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("knowledge_graph")

        workflow_result.steps.append(WorkflowStep(
            step_number=3,
            step_name="质量审查",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="审查知识图谱关系合理性")],
            depends_on=[2]
        ))
        quality_review = review_and_fix(
            original_materials={
                "course_structure": course_structure,
                "fragments": fragments
            },
            generated_result={"knowledge_graph": knowledge_graph},
            references=fragments,
            task_type="knowledge_graph",
            on_token=on_token
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "course_id": course_id,
            "course_name": course_name,
            "chapter_name": chapter_name,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="knowledge_graph",
                course_name=course_name,
                chapter_name=chapter_name,
                fragments=fragments,
                knowledge_points=[kp.get("name", "") if isinstance(kp, dict) else str(kp) for kp in (knowledge_points or [])],
            ),
            "course_structure": course_structure,
            "knowledge_graph": knowledge_graph,
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                knowledge_points=[kp.get("name", "") if isinstance(kp, dict) else str(kp) for kp in (knowledge_points or [])],
            ),
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("知识图谱生成流程完成")

        return workflow_result.model_dump()

    def run_student_profile_workflow(
        self,
        user_id: str = "demo_user",
        learning_records: List[dict] = None,
        answer_records: List[dict] = None,
        mistake_records: List[dict] = None,
        chapter_progress: dict = None,
        test_scores: List[dict] = None,
        study_time: dict = None,
        course_name: str = "",
        original_plan: dict = None,
        exam_date: str = "",
        daily_study_time: int = 60,
        on_token: Callable = None
    ) -> dict:
        if learning_records is None:
            learning_records = []
        if answer_records is None:
            answer_records = []
        if mistake_records is None:
            mistake_records = []
        if chapter_progress is None:
            chapter_progress = {}
        if test_scores is None:
            test_scores = []
        if study_time is None:
            study_time = {}
        
        workflow_result = WorkflowResult(
            workflow_type="student_profile",
            workflow_name="学生画像生成流程",
            status="running"
        )

        workflow_result.steps.append(WorkflowStep(
            step_number=1,
            step_name="学生画像生成",
            agent_calls=[AgentCall(agent_name="profile", agent_function="generate_student_profile", description="分析学习数据生成画像")]
        ))
        profile = generate_student_profile(
            learning_records=learning_records,
            answer_records=answer_records,
            mistake_records=mistake_records,
            chapter_progress=chapter_progress,
            test_scores=test_scores,
            study_time=study_time,
            course_name=course_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("profile")

        workflow_result.steps.append(WorkflowStep(
            step_number=2,
            step_name="自适应路径调整",
            agent_calls=[AgentCall(agent_name="adaptive_path", agent_function="generate_adaptive_path", description="根据画像调整学习路径")],
            depends_on=[1]
        ))
        adaptive_path_result = generate_adaptive_path(
            original_plan=original_plan or {},
            student_profile=profile,
            latest_answers=answer_records[-5:] if answer_records else [],
            mistake_diagnosis=mistake_records,
            fragments=[],
            exam_date=exam_date,
            daily_study_time=daily_study_time,
            chapter_name="",
            course_name=course_name,
            on_token=on_token
        )
        workflow_result.agent_sequence.append("adaptive_path")

        workflow_result.steps.append(WorkflowStep(
            step_number=3,
            step_name="Quality review",
            agent_calls=[AgentCall(agent_name="quality_review", agent_function="review_and_fix", description="Review profile conclusions, adaptive path priorities, and data-grounding.")],
            depends_on=[2]
        ))
        quality_review = self._safe_quality_review(
            original_materials={
                "learning_records": learning_records,
                "answer_records": answer_records,
                "mistake_records": mistake_records,
                "chapter_progress": chapter_progress,
                "test_scores": test_scores,
                "study_time": study_time,
                "original_plan": original_plan or {},
            },
            generated_result={
                "student_profile": profile,
                "adaptive_path": adaptive_path_result,
            },
            references=[],
            task_type="student_profile",
            on_token=on_token,
        )
        workflow_result.agent_sequence.append("quality_review")

        workflow_result.final_package_structure = {
            "user_id": user_id,
            "generation_metadata": self._build_generation_metadata(
                workflow_type="student_profile",
                course_name=course_name,
                extra={
                    "learning_record_count": len(learning_records),
                    "answer_record_count": len(answer_records),
                    "mistake_record_count": len(mistake_records),
                    "has_original_plan": bool(original_plan),
                },
            ),
            "student_profile": quality_review.get("final_result", {}).get("student_profile", profile),
            "adaptive_path": quality_review.get("final_result", {}).get("adaptive_path", adaptive_path_result),
            "quality_review": quality_review,
            "learning_actions": self._build_learning_actions(
                weak_points=profile.get("weak_knowledge_points", []) if isinstance(profile, dict) else [],
                has_diagnosis=bool(mistake_records),
            )
        }
        workflow_result.status = "completed"
        workflow_result.execution_log.append("学生画像生成流程完成")

        return workflow_result.model_dump()


orchestrator = OrchestratorAgent()
