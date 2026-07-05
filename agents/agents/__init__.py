# -*- coding: utf-8 -*-
from .orchestrator_agent import orchestrator
from .course_structure_agent import generate_course_structure, refine_course_structure
from .knowledge_graph_agent import generate_knowledge_graph, extend_knowledge_graph
from .planner_agent import generate_study_plan, modify_study_plan
from .exercise_agent import generate_exercises, modify_exercises
from .explanation_agent import generate_layered_explanation, modify_explanation
from .keypoint_agent import generate_keypoint_analysis, modify_keypoint_analysis
from .homework_tutor_agent import generate_homework_tutor, modify_homework_tutor
from .mistake_diagnosis_agent import generate_mistake_diagnosis, modify_mistake_diagnosis
from .profile_agent import generate_student_profile, update_student_profile
from .adaptive_path_agent import generate_adaptive_path, update_adaptive_path
from .exam_agent import generate_exam_paper, check_exam_paper
from .micro_lesson_agent import generate_micro_lesson
from .ppt_agent import generate_ppt_content
from .quality_review_agent import review_content, review_and_fix


def run_learning_package_workflow(*args, **kwargs):
    return orchestrator.run_learning_package_workflow(*args, **kwargs)


def run_exam_workflow(*args, **kwargs):
    return orchestrator.run_exam_workflow(*args, **kwargs)


def run_micro_lesson_workflow(*args, **kwargs):
    return orchestrator.run_micro_lesson_workflow(*args, **kwargs)


def run_homework_tutor_workflow(*args, **kwargs):
    return orchestrator.run_homework_tutor_workflow(*args, **kwargs)


def run_knowledge_graph_workflow(*args, **kwargs):
    return orchestrator.run_knowledge_graph_workflow(*args, **kwargs)


def run_student_profile_workflow(*args, **kwargs):
    return orchestrator.run_student_profile_workflow(*args, **kwargs)


__all__ = [
    "orchestrator",
    "run_learning_package_workflow",
    "run_exam_workflow",
    "run_micro_lesson_workflow",
    "run_homework_tutor_workflow",
    "run_knowledge_graph_workflow",
    "run_student_profile_workflow",
    "generate_course_structure",
    "refine_course_structure",
    "generate_knowledge_graph",
    "extend_knowledge_graph",
    "generate_study_plan",
    "modify_study_plan",
    "generate_exercises",
    "modify_exercises",
    "generate_layered_explanation",
    "modify_explanation",
    "generate_keypoint_analysis",
    "modify_keypoint_analysis",
    "generate_homework_tutor",
    "modify_homework_tutor",
    "generate_mistake_diagnosis",
    "modify_mistake_diagnosis",
    "generate_student_profile",
    "update_student_profile",
    "generate_adaptive_path",
    "update_adaptive_path",
    "generate_exam_paper",
    "check_exam_paper",
    "generate_micro_lesson",
    "generate_ppt_content",
    "review_content",
    "review_and_fix"
]
