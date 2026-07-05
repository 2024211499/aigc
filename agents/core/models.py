from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union


class KnowledgePoint(BaseModel):
    name: str = Field(..., description="知识点名称")
    definition: str = Field(default="", description="定义")
    type: str = Field(default="", description="类型（概念/定理/公式/方法）")
    source_fragment_id: str = Field(default="", description="来源片段ID")
    page_reference: str = Field(default="", description="页码引用")


class Section(BaseModel):
    section_number: str = Field(..., description="小节编号（如1.1）")
    section_name: str = Field(..., description="小节名称")
    section_summary: str = Field(default="", description="小节摘要")
    knowledge_points: List[KnowledgePoint] = Field(default_factory=list, description="知识点列表")
    examples: List[str] = Field(default_factory=list, description="例题")
    exercises: List[str] = Field(default_factory=list, description="习题")


class CourseStructure(BaseModel):
    course_name: str = Field(..., description="课程名")
    chapter_number: str = Field(default="", description="章节编号（如第一章）")
    chapter_name: str = Field(..., description="章节名")
    chapter_intro: str = Field(default="", description="章节简介")
    chapter_summary: str = Field(default="", description="章节摘要")
    sections: List[Section] = Field(default_factory=list, description="小节列表")
    all_knowledge_points: List[KnowledgePoint] = Field(default_factory=list, description="知识点列表")
    theorems: List[str] = Field(default_factory=list, description="定理列表")
    formulas: List[str] = Field(default_factory=list, description="公式列表")
    references: List[str] = Field(default_factory=list, description="引用来源")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


WORKFLOW_TYPES = [
    "learning_package",     # 学习包生成
    "exam",                 # 试卷生成
    "micro_lesson",         # 微课脚本生成
    "homework_tutor",       # 作业辅导
    "knowledge_graph",      # 知识图谱生成
    "custom",               # 自定义流程
]


class AgentCall(BaseModel):
    agent_name: str = Field(..., description="智能体名称")
    agent_function: str = Field(..., description="调用的函数名")
    input_params: dict = Field(default_factory=dict, description="输入参数")
    description: str = Field(default="", description="调用说明")


class WorkflowStep(BaseModel):
    step_number: int = Field(..., description="步骤序号")
    step_name: str = Field(..., description="步骤名称")
    agent_calls: List[AgentCall] = Field(default_factory=list, description="智能体调用列表")
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤序号")
    description: str = Field(default="", description="步骤说明")


class WorkflowResult(BaseModel):
    workflow_type: str = Field(..., description="流程类型")
    workflow_name: str = Field(..., description="流程名称")
    steps: List[WorkflowStep] = Field(default_factory=list, description="流程步骤")
    agent_sequence: List[str] = Field(default_factory=list, description="智能体调用顺序")
    final_package_structure: dict = Field(default_factory=dict, description="最终学习包结构")
    execution_log: List[str] = Field(default_factory=list, description="执行日志")
    status: str = Field(default="pending", description="状态（pending/running/completed/failed）")


class KnowledgeNode(BaseModel):
    node_id: str = Field(..., description="节点ID")
    name: str = Field(..., description="知识点名称")
    node_type: str = Field(default="", description="节点类型（概念/定理/公式/方法/题型/易错点）")
    chapter: str = Field(default="", description="所属章节")
    section: str = Field(default="", description="所属小节")
    definition: str = Field(default="", description="定义")


class KnowledgeEdge(BaseModel):
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    relation_type: str = Field(..., description="关系类型（prerequisite/subsequent/contains/parallel/confused/applies_to/error_related）")
    relation_label: str = Field(..., description="关系标签（中文描述）")
    explanation: str = Field(default="", description="解释理由")
    confidence: float = Field(default=0.0, description="置信度（0-1）")


class KnowledgeGraph(BaseModel):
    course_name: str = Field(..., description="课程名")
    chapter_name: str = Field(default="", description="章节名")
    nodes: List[KnowledgeNode] = Field(default_factory=list, description="节点列表")
    edges: List[KnowledgeEdge] = Field(default_factory=list, description="边列表")
    references: List[str] = Field(default_factory=list, description="引用来源")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


class DailyTask(BaseModel):
    day: int = Field(..., description="第几天")
    task_name: str = Field(..., description="任务名称")
    task_description: str = Field(..., description="任务描述")
    estimated_time_minutes: int = Field(..., description="预计学习时间（分钟）")
    key_points: List[str] = Field(default_factory=list, description="关键知识点")
    source_reference: str = Field(default="", description="对应教材来源")
    self_test_questions: List[str] = Field(default_factory=list, description="自测问题")


class StudyPlan(BaseModel):
    title: str = Field(..., description="学习计划标题")
    course_name: str = Field(default="", description="课程名")
    chapter_name: str = Field(default="", description="章节名")
    chapter_intro: str = Field(default="", description="章节简介")
    total_time_minutes: int = Field(..., description="建议总时长（分钟）")
    target_audience: str = Field(default="", description="适合人群")
    learning_objectives: List[str] = Field(default_factory=list, description="学习目标")
    prerequisite_knowledge: List[str] = Field(default_factory=list, description="前置知识")
    core_knowledge_points: List[str] = Field(default_factory=list, description="核心知识点列表")
    key_difficulties: str = Field(default="", description="重点难点分析")
    daily_tasks: List[DailyTask] = Field(default_factory=list, description="每日学习任务")
    review_suggestions: str = Field(default="", description="复习建议")
    common_mistakes: List[str] = Field(default_factory=list, description="易错点提醒")
    milestone_checkpoints: List[str] = Field(default_factory=list, description="阶段性检查标准")
    next_steps: str = Field(default="", description="下一步学习建议")
    references: List[str] = Field(default_factory=list, description="引用来源列表")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


QUALITY_REVIEW_TASK_TYPES = [
    "study_plan",         # 学习计划
    "keypoint",           # 重点难点
    "explanation",        # 分层讲解
    "exercise",           # 习题
    "homework_tutor",     # 作业辅导
    "mistake_diagnosis",  # 错题诊断
    "student_profile",    # 学生画像
    "adaptive_path",      # 自适应路径
    "exam_paper",         # 试卷
    "micro_lesson",       # 微课脚本
    "ppt_content",        # PPT内容
]


class QualityIssue(BaseModel):
    field: str = Field(..., description="问题所在字段")
    issue_type: str = Field(..., description="问题类型（hallucination/contradiction/incomplete/missing_reference/duplicate/wrong_difficulty/invalid_json）")
    severity: str = Field(..., description="严重程度（critical/major/minor）")
    description: str = Field(..., description="问题描述")
    suggestion: str = Field(..., description="修改建议")


class QualityReview(BaseModel):
    is_passed: bool = Field(default=False, description="是否通过")
    issues: List[QualityIssue] = Field(default_factory=list, description="问题列表")
    suggestions: List[str] = Field(default_factory=list, description="修改建议")
    credibility_score: float = Field(default=0.0, description="可信度评分（0-100）")
    need_regenerate_fields: List[str] = Field(default_factory=list, description="需要重新生成的字段")
    corrected_result: dict = Field(default_factory=dict, description="修正后的结果（可选）")
    review_summary: str = Field(default="", description="审查总结")


class PPTSlide(BaseModel):
    slide_number: int = Field(..., description="页码")
    slide_title: str = Field(..., description="每页标题")
    slide_content: str = Field(..., description="每页正文")
    formulas: List[str] = Field(default_factory=list, description="每页公式")
    image_suggestion: str = Field(default="", description="每页图示建议")
    speaker_notes: str = Field(default="", description="每页讲解备注")
    subtitle: str = Field(default="", description="每页对应字幕")
    duration_seconds: int = Field(default=30, description="每页停留时间（秒）")


class PPTContent(BaseModel):
    ppt_title: str = Field(..., description="PPT标题")
    course_name: str = Field(default="", description="课程名")
    chapter_name: str = Field(default="", description="章节名")
    knowledge_point: str = Field(default="", description="知识点")
    total_slides: int = Field(default=10, description="总页数")
    slides: List[PPTSlide] = Field(default_factory=list, description="每页内容")
    references: List[str] = Field(default_factory=list, description="引用来源")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


class MicroLessonSection(BaseModel):
    section_name: str = Field(..., description="段落名称（如开场导入、概念解释等）")
    duration_seconds: int = Field(default=30, description="时长（秒）")
    script: str = Field(..., description="逐字稿")
    visual_design: str = Field(default="", description="画面设计")
    board_design: str = Field(default="", description="板书设计")


class MicroLesson(BaseModel):
    title: str = Field(..., description="微课标题")
    course_name: str = Field(default="", description="课程名")
    chapter_name: str = Field(default="", description="章节名")
    knowledge_point: str = Field(default="", description="知识点")
    teaching_objectives: List[str] = Field(default_factory=list, description="教学目标")
    video_duration_seconds: int = Field(default=180, description="视频时长（秒）")
    outline: List[str] = Field(default_factory=list, description="讲解大纲")
    sections: List[MicroLessonSection] = Field(default_factory=list, description="逐段脚本")
    board_design: str = Field(default="", description="板书设计")
    example_arrangements: List[str] = Field(default_factory=list, description="例题安排")
    interactive_questions: List[str] = Field(default_factory=list, description="互动提问")
    common_mistake_reminders: List[str] = Field(default_factory=list, description="易错提醒")
    after_class_exercises: List[str] = Field(default_factory=list, description="课后练习")
    subtitle_text: str = Field(default="", description="字幕文本")
    references: List[str] = Field(default_factory=list, description="引用来源")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


EXAM_TYPES = [
    "chapter_quiz",       # 章节小测
    "unit_test",          # 单元测试
    "midterm_mock",       # 期中模拟卷
    "final_mock",         # 期末模拟卷
    "mistake_reinforce",  # 错题强化卷
    "weak_point_special", # 薄弱知识点专项卷
    "teacher_custom",     # 教师自定义组卷
]


class ExamQuestion(BaseModel):
    question_id: str = Field(..., description="题目ID")
    question_number: str = Field(..., description="题号（如一、1）")
    question_type: str = Field(..., description="题型")
    difficulty: str = Field(..., description="难度（easy/medium/hard）")
    knowledge_point: str = Field(default="", description="知识点")
    stem: str = Field(..., description="题干")
    options: List[str] = Field(default_factory=list, description="选项列表")
    correct_answer: str = Field(..., description="标准答案")
    detailed_explanation: str = Field(default="", description="详细解析")
    score: float = Field(default=0.0, description="每题分值")
    answer_area: str = Field(default="", description="答题区域说明")
    grading_criteria: str = Field(default="", description="评分标准")
    source_reference: str = Field(default="", description="来源依据")


class ExamPaper(BaseModel):
    paper_title: str = Field(..., description="试卷标题")
    exam_type: str = Field(default="", description="试卷类型")
    exam_instructions: str = Field(default="", description="考试说明")
    total_score: float = Field(default=100.0, description="总分")
    exam_duration_minutes: int = Field(default=120, description="考试时间（分钟）")
    questions: List[ExamQuestion] = Field(default_factory=list, description="题目列表")
    answers: dict = Field(default_factory=dict, description="答案")
    explanations: dict = Field(default_factory=dict, description="解析")
    grading_standards: str = Field(default="", description="评分标准")
    knowledge_point_coverage: dict = Field(default_factory=dict, description="知识点覆盖率")
    difficulty_distribution: dict = Field(default_factory=dict, description="难度分布")
    references: List[str] = Field(default_factory=list, description="引用来源")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


class KnowledgeMastery(BaseModel):
    knowledge_point: str = Field(..., description="知识点名称")
    mastery_level: float = Field(default=0.0, description="掌握度（0-100）")
    error_count: int = Field(default=0, description="错误次数")
    last_practice_time: str = Field(default="", description="最后练习时间")


class StudentProfile(BaseModel):
    current_stage: str = Field(default="", description="当前学习阶段")
    course_progress: float = Field(default=0.0, description="课程进度（0-100）")
    knowledge_mastery: List[KnowledgeMastery] = Field(default_factory=list, description="知识点掌握度")
    weak_knowledge_points: List[str] = Field(default_factory=list, description="薄弱知识点")
    common_wrong_question_types: List[str] = Field(default_factory=list, description="常错题型")
    common_error_reasons: List[str] = Field(default_factory=list, description="常见错误原因")
    learning_pace: str = Field(default="", description="学习节奏（快/中/慢）")
    learning_habits: List[str] = Field(default_factory=list, description="学习习惯")
    predicted_risks: List[str] = Field(default_factory=list, description="预测风险")
    recommended_review_order: List[str] = Field(default_factory=list, description="推荐复习顺序")
    recommended_reinforcement_tasks: List[str] = Field(default_factory=list, description="推荐补强任务")
    next_stage_suggestions: str = Field(default="", description="下一阶段学习建议")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


class AdaptiveTask(BaseModel):
    day: int = Field(..., description="第几天")
    task_name: str = Field(..., description="任务名称")
    task_description: str = Field(..., description="任务描述")
    task_type: str = Field(default="learn", description="任务类型（learn/review/practice/test）")
    estimated_time_minutes: int = Field(default=30, description="预计时间（分钟）")
    knowledge_points: List[str] = Field(default_factory=list, description="涉及知识点")
    difficulty: str = Field(default="medium", description="难度（easy/medium/hard）")
    priority: str = Field(default="normal", description="优先级（high/normal/low）")


class AdaptivePath(BaseModel):
    adjusted_plan: List[AdaptiveTask] = Field(default_factory=list, description="调整后的学习计划")
    need_relearn_points: List[str] = Field(default_factory=list, description="需要补学的知识点")
    need_skip_points: List[str] = Field(default_factory=list, description="需要跳过的内容")
    need_strengthen_types: List[str] = Field(default_factory=list, description="需要加强的题型")
    tomorrow_tasks: List[AdaptiveTask] = Field(default_factory=list, description="明日学习任务")
    review_priority: List[str] = Field(default_factory=list, description="复习优先级")
    estimated_completion_time: str = Field(default="", description="预计完成时间")
    adjustment_reasons: List[str] = Field(default_factory=list, description="调整原因")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


HOMEWORK_TUTOR_MODES = [
    "hint",          # 提示模式
    "step_by_step",  # 分步讲解模式
    "correction",    # 纠错模式
]


ERROR_TYPES = [
    "concept_misunderstanding",  # 概念理解错误
    "formula_memory_error",     # 公式记忆错误
    "method_selection_error",   # 方法选择错误
    "calculation_error",        # 计算错误
    "question_reading_error",   # 审题错误
    "condition_omission",       # 条件遗漏
    "step_skipping",            # 步骤跳跃
    "symbol_writing_error",     # 符号书写错误
    "logic_reasoning_error",    # 逻辑推理错误
    "programming_syntax_error", # 编程语法错误
    "code_logic_error",         # 代码逻辑错误
]


class ErrorAnalysis(BaseModel):
    error_location: str = Field(default="", description="学生错误位置")
    error_reason: str = Field(default="", description="错误原因")
    correct_fix: str = Field(default="", description="正确修改方式")
    related_knowledge: str = Field(default="", description="对应知识点")
    variant_practice: List[str] = Field(default_factory=list, description="变式练习")


class MistakeDiagnosis(BaseModel):
    question: str = Field(default="", description="题目")
    is_correct: bool = Field(default=False, description="是否正确")
    score: float = Field(default=0.0, description="得分（0-100）")
    error_steps: List[str] = Field(default_factory=list, description="错误步骤")
    error_type: str = Field(default="", description="错误类型")
    error_reason: str = Field(default="", description="错误原因")
    involved_knowledge: List[str] = Field(default_factory=list, description="涉及知识点")
    weak_prerequisite: str = Field(default="", description="前置薄弱知识")
    remediation_suggestions: List[str] = Field(default_factory=list, description="补救建议")
    recommended_review_fragments: List[str] = Field(default_factory=list, description="推荐复习片段")
    recommended_variant_count: int = Field(default=3, description="推荐变式题数量")
    references: List[str] = Field(default_factory=list, description="引用来源")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


class HomeworkTutorResponse(BaseModel):
    question_recognition: str = Field(default="", description="题目识别结果")
    knowledge_point: str = Field(default="", description="所属知识点")
    question_type: str = Field(default="", description="题型")
    difficulty: str = Field(default="", description="难度")
    solving_approach: str = Field(default="", description="解题思路")
    next_step_hint: str = Field(default="", description="下一步提示")
    complete_steps: List[str] = Field(default_factory=list, description="完整步骤")
    final_answer: str = Field(default="", description="最终答案")
    common_mistakes: List[str] = Field(default_factory=list, description="易错点")
    recommended_review: List[str] = Field(default_factory=list, description="推荐复习知识点")
    references: List[str] = Field(default_factory=list, description="引用来源")
    error_analysis: Optional[ErrorAnalysis] = Field(default=None, description="纠错模式下的错误分析")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


EXERCISE_TYPES = [
    "multiple_choice",  # 选择题
    "fill_in",          # 填空题
    "true_false",       # 判断题
    "calculation",      # 计算题
    "short_answer",     # 简答题
    "proof",            # 证明题
    "application",      # 应用题
    "programming",      # 编程题
    "code_reading",     # 代码阅读题
    "code_fill_in",     # 代码填空题
    "debugging",        # 调试题
]

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]


class ExerciseQuestion(BaseModel):
    question_id: str = Field(..., description="题目ID")
    question_type: str = Field(..., description="题型")
    difficulty: str = Field(..., description="难度：easy/medium/hard")
    knowledge_point: str = Field(default="", description="知识点")
    stem: str = Field(..., description="题干")
    options: List[str] = Field(default_factory=list, description="选项列表（选择题/判断题使用）")
    correct_answer: str = Field(..., description="标准答案")
    detailed_explanation: str = Field(default="", description="详细解析")
    grading_criteria: str = Field(default="", description="评分标准")
    common_mistakes: List[str] = Field(default_factory=list, description="易错提醒")
    source_reference: str = Field(default="", description="来源依据")
    variant_suggestions: List[str] = Field(default_factory=list, description="变式题建议")


class ExerciseSet(BaseModel):
    course_name: str = Field(default="", description="课程名")
    chapter_name: str = Field(default="", description="章节名")
    questions: List[ExerciseQuestion] = Field(default_factory=list, description="题目列表")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


class ExplanationStep(BaseModel):
    step_number: int = Field(..., description="步骤序号")
    content: str = Field(..., description="讲解内容")


class Explanation(BaseModel):
    question: str = Field(..., description="题目")
    difficulty: str = Field(default="Easy", description="难度等级：Easy/Medium/Hard")
    steps: List[ExplanationStep] = Field(..., description="分步讲解")
    summary: str = Field(..., description="总结")
    related_concepts: List[str] = Field(default_factory=list, description="相关概念")


class KeyPoint(BaseModel):
    core_focus: List[str] = Field(default_factory=list, description="核心重点")
    learning_difficulties: List[str] = Field(default_factory=list, description="学习难点")
    common_exam_points: List[str] = Field(default_factory=list, description="常见考点")
    common_mistakes: List[str] = Field(default_factory=list, description="易错点")
    confusing_concepts: List[str] = Field(default_factory=list, description="易混概念")
    breakthrough_methods: List[str] = Field(default_factory=list, description="建议突破方法")
    source_reference: str = Field(default="", description="对应教材来源")


class KeyPointAnalysis(BaseModel):
    chapter_name: str = Field(default="", description="章节名")
    key_points: List[KeyPoint] = Field(default_factory=list, description="重点难点分析列表")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")


EXPLANATION_MODES = [
    "zero_basic",       # 零基础讲解
    "textbook_sync",    # 教材同步讲解
    "exam_boost",       # 考试提分讲解
    "derivation",       # 推导理解讲解
    "analogy",          # 类比图解讲解
    "blackboard",       # 板书式讲解
    "lecture_script",   # 课堂讲稿式讲解
]


class LayeredExplanation(BaseModel):
    knowledge_point: str = Field(..., description="知识点名称")
    chapter_name: str = Field(default="", description="章节名")
    explanation_mode: str = Field(..., description="讲解模式")
    target_audience: str = Field(default="", description="适合人群")
    concept_explanation: str = Field(default="", description="概念解释")
    key_steps: List[str] = Field(default_factory=list, description="关键步骤")
    derivation_process: str = Field(default="", description="推导过程")
    example_problems: List[dict] = Field(default_factory=list, description="例题说明")
    common_mistakes: List[str] = Field(default_factory=list, description="易错提醒")
    summary_mnemonic: str = Field(default="", description="总结口诀")
    recommended_practice: List[str] = Field(default_factory=list, description="推荐练习")
    references: List[str] = Field(default_factory=list, description="引用来源")
    insufficient_data_warning: str = Field(default="", description="资料不足时的提示")
