# -*- coding: utf-8 -*-
import sys
import os
import io
import time
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import (
    orchestrator,
    generate_study_plan,
    generate_exercises,
    generate_layered_explanation,
    generate_keypoint_analysis,
    generate_course_structure,
    generate_micro_lesson,
    generate_exam_paper,
    generate_homework_tutor,
    generate_mistake_diagnosis,
    review_content
)
from core.memory_manager import MemoryManager


def on_token(token: str):
    print(token, end='', flush=True)


def print_header():
    print("=" * 60)
    print("  智能教育系统")
    print("=" * 60)


def print_menu():
    print("\n" + "=" * 60)
    print("  主菜单")
    print("=" * 60)
    print("可用功能：")
    print("  学习包 - 生成章节学习包（学习计划+讲解+习题）")
    print("  试卷   - 智能组卷生成测试卷")
    print("  练习   - 出几道练习题练练手")
    print("  微课   - 生成微课脚本和PPT")
    print("  PPT    - 生成PPT课件")
    print("  作业辅导 - 题目讲解和答疑")
    print("  知识图谱 - 生成知识点关系图")
    print("  学生画像 - 学习情况分析报告")
    print("  智能体列表 - 查看所有可用智能体")
    print("  退出/再见 - 退出系统")
    print("=" * 60)


def print_agent_menu():
    print("\n" + "=" * 60)
    print("  可用智能体")
    print("=" * 60)
    agents = orchestrator.list_agents()
    for i, (name, desc) in enumerate(agents.items(), 1):
        print(f"{i}. {name} - {desc}")
    print("0. 返回")
    print("=" * 60)


def load_fragments(file_path: str) -> list:
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return [line.strip() for line in lines if line.strip()]


def save_fragments(file_path: str, fragments: list):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(fragments))


def format_study_plan(plan):
    if not plan:
        return ""
    
    lines = []
    lines.append("学习计划")
    lines.append("=" * 40)
    lines.append("标题：" + plan.get('title', 'N/A'))
    lines.append("课程：" + plan.get('course_name', ''))
    lines.append("章节：" + plan.get('chapter_name', ''))
    
    intro = plan.get('chapter_intro', '')
    if intro:
        lines.append("简介：" + intro)
    
    lines.append("建议总时长：" + str(plan.get('total_time_minutes', 0)) + " 分钟")
    lines.append("适合人群：" + plan.get('target_audience', ''))
    
    objectives = plan.get('learning_objectives', [])
    if objectives:
        lines.append("\n学习目标：")
        for obj in objectives:
            lines.append("  - " + obj)
    
    core = plan.get('core_knowledge_points', [])
    if core:
        lines.append("\n核心知识点：")
        for c in core:
            lines.append("  - " + c)
    
    tasks = plan.get('daily_tasks', [])
    if tasks:
        lines.append("\n每日学习任务：")
        for task in tasks:
            lines.append(f"\n  第{task.get('day', '?')}天：{task.get('task_name', 'N/A')}")
            lines.append(f"  {task.get('task_description', '')}")
            lines.append(f"  预计时间：{task.get('estimated_time_minutes', 0)} 分钟")
    
    lines.append("")
    return "\n".join(lines)


def format_exercises(exercises):
    if not exercises:
        return ""
    
    lines = []
    lines.append("配套习题")
    lines.append("=" * 40)
    
    mc = exercises.get('multiple_choice', [])
    for i, q in enumerate(mc, 1):
        lines.append(f"\n选择题 {i}：{q.get('question', 'N/A')}")
        for opt in q.get('options', []):
            lines.append(f"  {opt}")
        ans = q.get('correct_answer', 'N/A')
        if isinstance(ans, list):
            ans = "、".join(ans)
        lines.append(f"答案：{ans}")
        lines.append(f"解析：{q.get('explanation', 'N/A')}")
    
    fi = exercises.get('fill_in', [])
    for i, q in enumerate(fi, 1):
        lines.append(f"\n填空题 {i}：{q.get('question', 'N/A')}")
        lines.append(f"答案：{q.get('answer', 'N/A')}")
    
    sa = exercises.get('short_answer', [])
    for i, q in enumerate(sa, 1):
        lines.append(f"\n简答题 {i}：{q.get('question', 'N/A')}")
        lines.append(f"参考答案：{q.get('sample_answer', 'N/A')}")
    
    lines.append("")
    return "\n".join(lines)


def format_explanation(explanation):
    if not explanation:
        return ""
    
    lines = []
    lines.append("题目讲解")
    lines.append("=" * 40)
    lines.append("知识点：" + explanation.get('knowledge_point', 'N/A'))
    lines.append("模式：" + explanation.get('explanation_mode', 'N/A'))
    
    concept = explanation.get('concept_explanation', '')
    if concept:
        lines.append(f"\n概念解释：{concept}")
    
    steps = explanation.get('key_steps', [])
    if steps:
        lines.append("\n关键步骤：")
        for i, step in enumerate(steps, 1):
            lines.append(f"  {i}. {step}")
    
    mistakes = explanation.get('common_mistakes', [])
    if mistakes:
        lines.append("\n易错提醒：")
        for m in mistakes:
            lines.append(f"  - {m}")
    
    summary = explanation.get('summary_mnemonic', '')
    if summary:
        lines.append(f"\n总结口诀：{summary}")
    
    lines.append("")
    return "\n".join(lines)


def format_keypoint(keypoint):
    if not keypoint:
        return ""
    
    lines = []
    lines.append("重点难点分析")
    lines.append("=" * 40)
    
    core = keypoint.get('core_focus', [])
    if core:
        lines.append("\n核心重点：")
        for c in core:
            lines.append(f"  - {c}")
    
    difficulties = keypoint.get('learning_difficulties', [])
    if difficulties:
        lines.append("\n学习难点：")
        for d in difficulties:
            lines.append(f"  - {d}")
    
    exam_points = keypoint.get('exam_points', [])
    if exam_points:
        lines.append("\n常见考点：")
        for e in exam_points:
            lines.append(f"  - {e}")
    
    mistakes = keypoint.get('common_mistakes', [])
    if mistakes:
        lines.append("\n易错点：")
        for m in mistakes:
            lines.append(f"  - {m}")
    
    lines.append("")
    return "\n".join(lines)


def format_exam_paper(exam):
    if not exam:
        return ""
    
    lines = []
    lines.append("试卷")
    lines.append("=" * 40)
    lines.append(f"类型：{exam.get('exam_type', 'N/A')}")
    lines.append(f"总分：{exam.get('total_score', 0)} 分")
    lines.append(f"时长：{exam.get('exam_duration_minutes', 0)} 分钟")
    
    questions = exam.get('questions', [])
    if questions:
        lines.append(f"\n题目数量：{len(questions)}")
        for i, q in enumerate(questions, 1):
            lines.append(f"\n第{i}题 [{q.get('question_type', '')}] ({q.get('difficulty', '')})")
            lines.append(f"  {q.get('stem', '')}")
            if q.get('options'):
                for opt in q['options']:
                    lines.append(f"  {opt}")
            lines.append(f"  答案：{q.get('correct_answer', '')}")
    
    lines.append("")
    return "\n".join(lines)


def format_micro_lesson(lesson):
    if not lesson:
        return ""
    
    lines = []
    lines.append("微课脚本")
    lines.append("=" * 40)
    lines.append(f"标题：{lesson.get('title', 'N/A')}")
    lines.append(f"时长：{lesson.get('video_duration_seconds', 0)} 秒")
    
    objectives = lesson.get('teaching_objectives', [])
    if objectives:
        lines.append("\n教学目标：")
        for obj in objectives:
            lines.append(f"  - {obj}")
    
    outline = lesson.get('teaching_outline', [])
    if outline:
        lines.append("\n教学大纲：")
        for i, item in enumerate(outline, 1):
            lines.append(f"  {i}. {item}")
    
    script = lesson.get('script_segments', [])
    if script:
        lines.append("\n逐段脚本：")
        for seg in script:
            lines.append(f"  [{seg.get('segment_name', '')}] {seg.get('content', '')}")
    
    lines.append("")
    return "\n".join(lines)


def format_tutor_result(tutor):
    if not tutor:
        return ""
    
    lines = []
    lines.append("作业辅导")
    lines.append("=" * 40)
    lines.append(f"题目：{tutor.get('question', 'N/A')}")
    lines.append(f"模式：{tutor.get('tutor_mode', 'N/A')}")
    
    hint = tutor.get('hint', '')
    if hint:
        lines.append(f"\n提示：{hint}")
    
    steps = tutor.get('step_by_step', [])
    if steps:
        lines.append("\n分步讲解：")
        for i, step in enumerate(steps, 1):
            lines.append(f"  {i}. {step}")
    
    answer = tutor.get('answer', '')
    if answer:
        lines.append(f"\n答案：{answer}")
    
    lines.append("")
    return "\n".join(lines)


def run_learning_package_workflow(fragments, params=None):
    if params is None:
        params = {}
    
    print("\n" + "=" * 60)
    print("  生成本章学习包")
    print("=" * 60)
    
    user_profile = {
        "course_name": "",
        "knowledge_points": [],
        "student_level": "中等",
        "weak_points": [],
        "history_mistakes": []
    }
    
    study_days = params.get('study_days', 7)
    daily_time = params.get('daily_time', 60)
    exercise_count = params.get('exercise_count', 10)
    max_explanation_count = 5
    
    print("\n开始生成学习包...")
    print("-" * 60)
    print("  [提示] 系统将自动从资料中提取课程名、章节名、知识点等信息")
    
    result = orchestrator.run_learning_package_workflow(
        fragments=fragments,
        user_profile=user_profile,
        study_days=study_days,
        daily_time=daily_time,
        exercise_count=exercise_count,
        max_explanation_count=max_explanation_count,
        on_token=on_token
    )
    
    print("\n" + "=" * 60)
    print("  学习包生成完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    
    if package.get('course_structure'):
        print("\n课程结构：")
        print(json.dumps(package['course_structure'], ensure_ascii=False, indent=2)[:500])
    
    if package.get('keypoint_analysis'):
        print(format_keypoint(package['keypoint_analysis']))
    
    if package.get('study_plan'):
        print(format_study_plan(package['study_plan']))
    
    if package.get('explanations'):
        for exp in package['explanations'][:2]:
            print(format_explanation(exp))
    
    if package.get('exercises'):
        print(format_exercises(package['exercises']))
    
    if package.get('quality_review'):
        print("\n质量审查：")
        print(json.dumps(package['quality_review'], ensure_ascii=False, indent=2)[:300])
    
    return result


def run_exam_workflow(fragments, params=None):
    if params is None:
        params = {}
    
    print("\n" + "=" * 60)
    print("  生成试卷")
    print("=" * 60)
    
    exam_config = {
        "exam_type": "单元测试",
        "course_name": "",
        "total_questions": params.get('exercise_count', 20),
        "exam_duration_minutes": 90,
        "total_score": 100,
        "include_answers": True,
        "include_explanations": True,
        "mistake_records": [],
        "weak_points": []
    }
    
    print("\n开始生成试卷...")
    print("-" * 60)
    print("  [提示] 系统将自动从资料中提取章节范围和知识点")
    
    result = orchestrator.run_exam_workflow(
        chapters=[],
        exam_config=exam_config,
        fragments=fragments,
        on_token=on_token
    )
    
    print("\n" + "=" * 60)
    print("  试卷生成完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    if package.get('exam_paper'):
        print(format_exam_paper(package['exam_paper']))
    
    return result


def run_exercise_workflow(fragments, params=None):
    if params is None:
        params = {}
    
    print("\n" + "=" * 60)
    print("  生成练习题")
    print("=" * 60)
    
    exercise_count = params.get('exercise_count', 5)
    
    print(f"\n开始生成练习题...")
    print("-" * 60)
    print(f"  [提示] 系统将自动从资料中提取知识点，生成{exercise_count}道个性化练习题")
    
    result = orchestrator.run_exercise_workflow(
        fragments=fragments,
        exercise_count=exercise_count,
        on_token=on_token
    )
    
    print("\n" + "=" * 60)
    print("  练习题生成完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    if package.get('exercises'):
        print(format_exercises(package['exercises']))
    
    return result


def run_micro_lesson_workflow(fragments):
    print("\n" + "=" * 60)
    print("  生成微课")
    print("=" * 60)
    
    print("\n开始生成微课...")
    print("-" * 60)
    print("  [提示] 系统将自动从资料中提取核心知识点生成微课")
    
    result = orchestrator.run_micro_lesson_workflow(
        fragments=fragments,
        topic="",
        style="讲解式",
        duration=300,
        on_token=on_token
    )
    
    print("\n" + "=" * 60)
    print("  微课生成完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    if package.get('micro_lesson'):
        print(format_micro_lesson(package['micro_lesson']))
    
    return result


def run_homework_tutor_workflow(fragments):
    print("\n" + "=" * 60)
    print("  作业辅导")
    print("=" * 60)
    
    question = input("请输入题目: ").strip()
    if not question:
        print("题目不能为空")
        return None
    
    student_answer = input("学生答案（可选，直接回车跳过）: ").strip() or None
    
    print("\n开始辅导...")
    print("-" * 60)
    
    result = orchestrator.run_homework_tutor_workflow(
        question=question,
        student_answer=student_answer,
        fragments=fragments,
        tutor_mode="分步讲解",
        on_token=on_token
    )
    
    print("\n" + "=" * 60)
    print("  辅导完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    if package.get('tutor_result'):
        print(format_tutor_result(package['tutor_result']))
    
    if package.get('diagnosis_result'):
        print("\n错题诊断：")
        print(json.dumps(package['diagnosis_result'], ensure_ascii=False, indent=2)[:500])
    
    return result


def run_ppt_workflow(fragments):
    print("\n" + "=" * 60)
    print("  生成PPT课件")
    print("=" * 60)
    
    print("\n开始生成PPT...")
    print("-" * 60)
    print("  [提示] 系统将自动从资料中提取核心知识点生成PPT")
    
    result = orchestrator.run_ppt_workflow(
        fragments=fragments,
        topic="",
        teaching_style="生动活泼",
        total_slides=12,
        on_token=on_token
    )
    
    print("\n" + "=" * 60)
    print("  PPT生成完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    if package.get('ppt_content'):
        ppt = package['ppt_content']
        print(f"\nPPT标题：{ppt.get('ppt_title', 'N/A')}")
        print(f"总页数：{ppt.get('total_slides', 0)}")
        slides = ppt.get('slides', [])
        for slide in slides[:3]:
            print(f"\n第{slide.get('slide_number', '?')}页：{slide.get('slide_title', 'N/A')}")
            print(f"  内容：{slide.get('slide_content', '')[:200]}")
        if len(slides) > 3:
            print(f"\n  ... 共{len(slides)}页")
    
    return result


def run_knowledge_graph_workflow(fragments):
    print("\n" + "=" * 60)
    print("  生成知识图谱")
    print("=" * 60)
    
    print("\n开始生成知识图谱...")
    print("-" * 60)
    print("  [提示] 系统将自动从资料中提取知识点和关系")
    
    result = orchestrator.run_knowledge_graph_workflow(
        fragments=fragments,
        course_id="",
        chapter_name="",
        on_token=on_token
    )
    
    print("\n" + "=" * 60)
    print("  知识图谱生成完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    if package.get('knowledge_graph'):
        print("\n知识图谱：")
        print(json.dumps(package['knowledge_graph'], ensure_ascii=False, indent=2)[:800])
    
    return result


def run_student_profile_workflow():
    print("\n" + "=" * 60)
    print("  生成学生画像")
    print("=" * 60)
    
    print("\n注意：学生画像需要学习数据支持")
    print("当前暂无学习记录数据，将生成示例画像")
    print("-" * 60)
    
    result = orchestrator.run_student_profile_workflow()
    
    print("\n" + "=" * 60)
    print("  学生画像生成完成")
    print("=" * 60)
    
    package = result.get('final_package_structure', {})
    if package.get('student_profile'):
        print("\n学生画像：")
        print(json.dumps(package['student_profile'], ensure_ascii=False, indent=2)[:500])
    
    return result


def run_single_agent(fragments):
    print_agent_menu()
    
    choice = input("\n请选择智能体编号: ").strip()
    if choice == "0":
        return None
    
    agents = orchestrator.list_agents()
    agent_list = list(agents.keys())
    
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(agent_list):
            print("无效选项")
            return None
        agent_name = agent_list[idx]
    except ValueError:
        print("无效输入")
        return None
    
    print(f"\n已选择：{agent_name} - {agents[agent_name]}")
    
    action = input("操作（默认generate）: ").strip() or "generate"
    
    print("\n请输入参数（JSON格式，直接回车使用默认）: ")
    params_str = input().strip()
    
    params = {}
    if params_str:
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError:
            print("JSON格式错误")
            return None
    
    if 'fragments' not in params:
        params['fragments'] = fragments
    
    print(f"\n调用 {agent_name}.{action}...")
    print("-" * 60)
    
    try:
        result = orchestrator.call_agent(agent_name, action, **params)
        print("\n结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1000])
        return result
    except Exception as e:
        print(f"调用失败：{str(e)}")
        return None


def main():
    print_header()
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    fragments_path = os.path.join(project_root, "data", "fragments.txt")
    
    fragments = load_fragments(fragments_path)
    
    if not fragments:
        print("\n未找到教材资料（data/fragments.txt 为空）")
        print("请先在 data/fragments.txt 中添加教材内容，或直接输入内容继续")
        content = input("请输入教材内容（直接回车跳过）: ").strip()
        if content:
            fragments = [content]
            save_fragments(fragments_path, fragments)
            print("已保存到 fragments.txt")
        else:
            print("使用空内容继续")
    else:
        print(f"\n[资料加载] 已从 data/fragments.txt 加载 {len(fragments)} 条教材内容")
    
    memory = MemoryManager()
    session_id = "main_session"
    history = []
    
    print("\n" + "=" * 60)
    print("  欢迎使用智能教育系统！")
    print("  已加载教材资料，您可以直接告诉我您想做什么，例如：")
    print("    - 帮我根据资料生成一个学习包")
    print("    - 我想做一套试卷来检验学习成果")
    print("    - 给我讲解一下集合的概念")
    print("    - 生成知识图谱看看知识点之间的关系")
    print("=" * 60)
    
    while True:
        print_menu()
        try:
            user_input = input("\n请告诉我您想做什么: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        
        if not user_input:
            print("\n请输入您的想法")
            continue
        
        if any(word in user_input for word in ["退出", "再见", "bye", "quit", "exit"]):
            print("\n再见！")
            break
        
        if any(word in user_input for word in ["智能体列表", "查看所有", "有哪些智能体", "功能列表"]):
            agents = orchestrator.list_agents()
            print("\n" + "=" * 60)
            print("  可用智能体列表")
            print("=" * 60)
            for name, desc in agents.items():
                print(f"  {name}: {desc}")
            print("=" * 60)
            continue
        
        if any(word in user_input for word in ["历史", "记录", "查看历史"]):
            print("\n历史记录：")
            if history:
                for i, h in enumerate(history, 1):
                    print(f"  {i}. {h['type']}")
            else:
                print("  暂无历史记录")
            
            try:
                saved = memory.get_history(session_id)
                if saved:
                    print("\n保存的会话：")
                    for s in saved:
                        print(f"  - {s}")
            except Exception:
                pass
            continue
        
        task_type = orchestrator.recognize_task_by_llm(user_input)
        workflow_info = orchestrator._workflow_map.get(task_type)
        
        if not workflow_info:
            print("\n抱歉，我没有理解您的想法。请尝试以下功能：")
            print("  学习包、试卷、练习、微课、PPT、作业辅导、知识图谱、学生画像")
            continue
        
        print(f"\n识别到您的意图：{workflow_info['name']}")
        print("-" * 60)
        
        # 从用户输入中提取参数
        params = orchestrator.extract_params_from_input(user_input)
        print(f"  [自动提取参数] {params if params else '无'}")
        
        try:
            if task_type == "learning_package":
                result = run_learning_package_workflow(fragments, params)
            elif task_type == "exam":
                result = run_exam_workflow(fragments, params)
            elif task_type == "exercise":
                result = run_exercise_workflow(fragments, params)
            elif task_type == "micro_lesson":
                result = run_micro_lesson_workflow(fragments, params)
            elif task_type == "ppt":
                result = run_ppt_workflow(fragments, params)
            elif task_type == "homework_tutor":
                result = run_homework_tutor_workflow(fragments, params)
            elif task_type == "knowledge_graph":
                result = run_knowledge_graph_workflow(fragments, params)
            elif task_type == "student_profile":
                result = run_student_profile_workflow()
            else:
                result = None
            
            if result:
                history.append({"type": task_type, "result": result})
                try:
                    memory.save_session(session_id, fragments, result)
                except Exception:
                    pass
        except Exception as e:
            print(f"\n执行失败：{str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
