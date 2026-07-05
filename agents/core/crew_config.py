import os
import json
import uuid
import sys
import io
from typing import List, Optional
from crewai import Agent, Task, Crew, Process
from crewai.llm import LLM
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

os.environ["XDG_CONFIG_HOME"] = os.path.join(project_root, ".config")
os.environ["CREWAI_STORAGE_DIR"] = os.path.join(project_root, ".crewai_data")
os.makedirs(os.path.join(project_root, ".config", "crewai"), exist_ok=True)
os.makedirs(os.environ["CREWAI_STORAGE_DIR"], exist_ok=True)

from .llm_client import extract_json_from_response
from .models import StudyPlan, ExerciseSet, LayeredExplanation
from .memory_manager import MemoryManager

crewai_llm = LLM(
    model=os.getenv("LLM_MODEL_NAME", "deepseek-chat"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
)


class _SilentOutput:
    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        devnull = open(os.devnull, 'w', encoding='utf-8')
        sys.stdout = devnull
        sys.stderr = devnull
        return self

    def __exit__(self, *args):
        sys.stdout = self._stdout
        sys.stderr = self._stderr


class EducationalCrew:
    def __init__(self, fragments: List[str]):
        self.fragments = fragments
        self.context = "\n---\n".join(fragments)
        self.study_plan = None
        self.exercises = None
        self.explanation = None
        self.conversation_history = []
        self.session_id = str(uuid.uuid4())[:8]
        self.memory = MemoryManager()
        print("\nSession ID: " + self.session_id)
    
    def _add_to_history(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        self.memory.add_to_history(self.session_id, role, content)
    
    def _get_history_context(self) -> str:
        if not self.conversation_history:
            return ""
        history = "\n\n### 对话历史\n"
        for msg in self.conversation_history[-5:]:
            history += f"{msg['role']}: {msg['content']}\n"
        return history
    
    def run_initial(self) -> dict:
        print("\nGenerating initial content...\n")
        
        planner = create_planner_agent()
        exercise_maker = create_exercise_agent()
        explainer = create_explanation_agent()
        
        plan_task = Task(
            description=f"""## 任务：生成学习计划

请分析以下教材片段，生成一个结构化的学习计划：

{self.context}

## 输出要求
输出JSON格式，必须严格符合以下结构：
{{
  "title": "学习计划标题",
  "items": [
    {{
      "topic": "学习主题",
      "description": "学习描述",
      "estimated_time_minutes": 30,
      "key_points": ["知识点1", "知识点2"]
    }}
  ],
  "total_time_minutes": 总时间
}}""",
            expected_output="JSON格式的学习计划",
            agent=planner,
        )
        
        exercise_task = Task(
            description=f"""## 任务：生成配套习题集

请根据以下教材内容，生成一套完整的习题。

### 教材内容
{self.context}

### 要求
- 选择题：2-3道，每道4个选项
- 填空题：2道
- 简答题：1-2道
- 题目必须基于教材内容，不要超出范围
- 每道题必须有question_id（UUID格式）、question_type、difficulty、stem、correct_answer、detailed_explanation、grading_criteria、common_mistakes、source_reference、variant_suggestions

## 输出要求
输出JSON格式，必须严格符合以下结构：
{{
  "course_name": "课程名",
  "chapter_name": "章节名",
  "questions": [
    {{
      "question_id": "唯一ID",
      "question_type": "题型（multiple_choice/fill_in/short_answer）",
      "difficulty": "难度（easy/medium/hard）",
      "knowledge_point": "知识点",
      "stem": "题干",
      "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
      "correct_answer": "标准答案",
      "detailed_explanation": "详细解析",
      "grading_criteria": "评分标准",
      "common_mistakes": ["易错提醒1"],
      "source_reference": "来源依据",
      "variant_suggestions": ["变式题建议1"]
    }}
  ],
  "insufficient_data_warning": ""
}}""",
            expected_output="JSON格式的习题集",
            agent=exercise_maker,
            context=[plan_task],
        )
        
        explanation_task = Task(
            description=f"""## 任务：讲解知识点

请从前面生成的习题中选择**第一道选择题**，进行详细的分步骤讲解。

### 教材上下文
{self.context}

### 要求
- 先复述题目和选项
- 分步骤分析每个选项为什么对或错
- 给出最终答案和总结

## 输出要求
输出JSON格式，必须严格符合以下结构：
{{
  "knowledge_point": "知识点名称",
  "chapter_name": "章节名",
  "explanation_mode": "讲解模式",
  "target_audience": "适合人群",
  "concept_explanation": "概念解释",
  "key_steps": ["关键步骤1", "关键步骤2"],
  "derivation_process": "推导过程",
  "example_problems": [
    {{
      "problem": "例题题目",
      "solution": "解题过程",
      "key_point": "本题考查的核心点"
    }}
  ],
  "common_mistakes": ["易错提醒1"],
  "summary_mnemonic": "总结口诀",
  "recommended_practice": ["推荐练习1"],
  "references": ["引用来源1"],
  "insufficient_data_warning": ""
}}""",
            expected_output="JSON格式的讲解内容",
            agent=explainer,
            context=[exercise_task],
        )
        
        crew = Crew(
            agents=[planner, exercise_maker, explainer],
            tasks=[plan_task, exercise_task, explanation_task],
            process=Process.sequential,
            verbose=False,
            memory=False,
            output_log_file=os.path.join(project_root, ".crewai_data", "crew_output.log"),
        )
        
        print("\n" + "=" * 60)
        print("CrewAI 正在思考中...")
        print("=" * 60)
        
        with _SilentOutput():
            result = crew.kickoff()
        
        print("\n" + "=" * 60)
        print("思考完成")
        print("=" * 60 + "\n")
        
        plan_raw = str(plan_task.output.raw) if hasattr(plan_task.output, 'raw') else str(plan_task.output)
        exercise_raw = str(exercise_task.output.raw) if hasattr(exercise_task.output, 'raw') else str(exercise_task.output)
        explanation_raw = str(explanation_task.output.raw) if hasattr(explanation_task.output, 'raw') else str(explanation_task.output)
        
        plan_data = extract_json_from_response(plan_raw)
        if plan_data and "items" in plan_data:
            self.study_plan = StudyPlan(**plan_data).model_dump()
        
        exercise_data = extract_json_from_response(exercise_raw)
        if exercise_data and "questions" in exercise_data:
            self.exercises = ExerciseSet(**exercise_data).model_dump()
        
        explanation_data = extract_json_from_response(explanation_raw)
        if explanation_data and "knowledge_point" in explanation_data:
            self.explanation = LayeredExplanation(**explanation_data).model_dump()
        
        results = self.get_results()
        self.memory.save_session(self.session_id, self.fragments, results)
        
        self._add_to_history("系统", "初始生成完成")
        
        if self.study_plan:
            for item in self.study_plan.get("items", []):
                for kp in item.get("key_points", []):
                    try:
                        self.memory.save_knowledge_point(self.session_id, kp)
                    except Exception:
                        pass
        
        self.memory.save_learning_state(self.session_id, focus_level=0.8, fatigue_level=0.2, notes="初始学习")
        
        return results
    
    def modify_study_plan(self, request: str) -> dict:
        print(f"\nModifying study plan: {request}\n")
        
        self._add_to_history("用户", f"修改学习计划: {request}")
        
        planner = create_planner_agent()
        
        history_context = self._get_history_context()
        current_plan = json.dumps(self.study_plan, ensure_ascii=False, indent=2) if self.study_plan else "无"
        
        task = Task(
            description=f"""## 任务：修改学习计划

### 当前学习计划
{current_plan}

### 教材内容
{self.context}

{history_context}

### 用户修改要求
{request}

请根据用户的要求修改学习计划，输出JSON格式。""",
            expected_output="JSON格式的学习计划",
            agent=planner,
        )
        
        crew = Crew(
            agents=[planner],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
            memory=False,
        )
        
        with _SilentOutput():
            result = crew.kickoff()
        raw_output = str(result)
        
        plan_data = extract_json_from_response(raw_output)
        if plan_data and "items" in plan_data:
            self.study_plan = StudyPlan(**plan_data).model_dump()
            self._add_to_history("系统", "学习计划已修改")
            
            results = self.get_results()
            self.memory.save_session(self.session_id, self.fragments, results)
        
        return self.get_results()
    
    def modify_exercises(self, request: str) -> dict:
        print(f"\nModifying exercises: {request}\n")
        
        self._add_to_history("用户", f"修改习题: {request}")
        
        exercise_maker = create_exercise_agent()
        
        history_context = self._get_history_context()
        current_exercises = json.dumps(self.exercises, ensure_ascii=False, indent=2) if self.exercises else "无"
        current_plan = json.dumps(self.study_plan, ensure_ascii=False, indent=2) if self.study_plan else "无"
        
        task = Task(
            description=f"""## 任务：修改习题集

### 当前习题集
{current_exercises}

### 学习计划
{current_plan}

### 教材内容
{self.context}

{history_context}

### 用户修改要求
{request}

请根据用户的要求修改习题集，输出JSON格式。""",
            expected_output="JSON格式的习题集",
            agent=exercise_maker,
        )
        
        crew = Crew(
            agents=[exercise_maker],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
            memory=False,
        )
        
        with _SilentOutput():
            result = crew.kickoff()
        raw_output = str(result)
        
        exercise_data = extract_json_from_response(raw_output)
        if exercise_data and "questions" in exercise_data:
            self.exercises = ExerciseSet(**exercise_data).model_dump()
            self._add_to_history("系统", "习题集已修改")
            
            results = self.get_results()
            self.memory.save_session(self.session_id, self.fragments, results)
        
        return self.get_results()
    
    def modify_explanation(self, request: str) -> dict:
        print(f"\nModifying explanation: {request}\n")
        
        self._add_to_history("用户", f"修改讲解: {request}")
        
        explainer = create_explanation_agent()
        
        history_context = self._get_history_context()
        current_explanation = json.dumps(self.explanation, ensure_ascii=False, indent=2) if self.explanation else "无"
        
        task = Task(
            description=f"""## 任务：修改讲解

### 当前讲解
{current_explanation}

### 教材上下文
{self.context}

{history_context}

### 用户修改要求
{request}

请根据用户的要求修改讲解，输出JSON格式。""",
            expected_output="JSON格式的讲解内容",
            agent=explainer,
        )
        
        crew = Crew(
            agents=[explainer],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
            memory=False,
        )
        
        with _SilentOutput():
            result = crew.kickoff()
        raw_output = str(result)
        
        explanation_data = extract_json_from_response(raw_output)
        if explanation_data and "knowledge_point" in explanation_data:
            self.explanation = LayeredExplanation(**explanation_data).model_dump()
            self._add_to_history("系统", "讲解已修改")
            
            results = self.get_results()
            self.memory.save_session(self.session_id, self.fragments, results)
        
        return self.get_results()
    
    def get_results(self) -> dict:
        return {
            "study_plan": self.study_plan,
            "exercises": self.exercises,
            "explanation": self.explanation,
        }
    
    def get_conversation_history(self) -> List[dict]:
        return self.memory.get_history(self.session_id)
    
    def search_knowledge(self, query: str) -> List[str]:
        return self.memory.search_similar_concepts(self.session_id, query)
    
    def __del__(self):
        if hasattr(self, 'memory'):
            self.memory.close()


def create_planner_agent() -> Agent:
    return Agent(
        role="学习规划师",
        goal="根据教材片段生成结构化的学习计划",
        backstory="""你是一位经验丰富的教育规划专家，擅长分析教材内容并制定合理的学习计划。
你能准确把握知识点的难易程度，并安排循序渐进的学习路径。
你必须输出合法的JSON格式，不要包含其他多余内容。""",
        verbose=True,
        allow_delegation=False,
        llm=crewai_llm,
    )


def create_exercise_agent() -> Agent:
    return Agent(
        role="出题师",
        goal="根据教材片段和学习计划生成配套的习题集",
        backstory="""你是一位资深的命题专家，擅长根据教材内容和学习计划设计各种类型的习题。
你出的题目既考察基础知识，又能检验学生的理解深度。
你必须输出合法的JSON格式，不要包含其他多余内容。""",
        verbose=True,
        allow_delegation=False,
        llm=crewai_llm,
    )


def create_explanation_agent() -> Agent:
    return Agent(
        role="讲解师",
        goal="对习题中的选择题进行分步骤的详细讲解",
        backstory="""你是一位优秀的教师，擅长用清晰易懂的方式讲解题目。
你能把复杂的知识点分解成简单的步骤，帮助学生理解。
你必须输出合法的JSON格式，不要包含其他多余内容。""",
        verbose=True,
        allow_delegation=False,
        llm=crewai_llm,
    )


