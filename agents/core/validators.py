from typing import Any, Dict, List, Tuple
from .models import StudyPlan, ExerciseSet, LayeredExplanation


def validate_study_plan(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    
    if "title" not in data:
        errors.append("缺少title字段")
    elif not isinstance(data["title"], str):
        errors.append("title必须是字符串")
    
    if "total_time_minutes" not in data:
        errors.append("缺少total_time_minutes字段")
    elif not isinstance(data["total_time_minutes"], int):
        errors.append("total_time_minutes必须是整数")
    
    if "daily_tasks" in data:
        if not isinstance(data["daily_tasks"], list):
            errors.append("daily_tasks必须是列表")
        else:
            for i, task in enumerate(data["daily_tasks"]):
                for field in ["day", "task_name", "task_description", "estimated_time_minutes"]:
                    if field not in task:
                        errors.append(f"daily_tasks[{i}]缺少{field}字段")
    
    return len(errors) == 0, errors


def validate_exercises(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    
    if "questions" not in data:
        errors.append("缺少questions字段")
    elif not isinstance(data["questions"], list):
        errors.append("questions必须是列表")
    else:
        for i, q in enumerate(data["questions"]):
            for field in ["question_id", "question_type", "difficulty", "stem", "correct_answer"]:
                if field not in q:
                    errors.append(f"questions[{i}]缺少{field}字段")
            if "difficulty" in q and q["difficulty"] not in ["easy", "medium", "hard"]:
                errors.append(f"questions[{i}].difficulty必须是easy/medium/hard")
            if "options" in q and not isinstance(q["options"], list):
                errors.append(f"questions[{i}].options必须是列表")
    
    return len(errors) == 0, errors


def validate_explanation(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    
    if "knowledge_point" not in data:
        errors.append("缺少knowledge_point字段")
    
    if "explanation_mode" not in data:
        errors.append("缺少explanation_mode字段")
    
    if "concept_explanation" not in data:
        errors.append("缺少concept_explanation字段")
    
    if "key_steps" in data and not isinstance(data["key_steps"], list):
        errors.append("key_steps必须是列表")
    
    return len(errors) == 0, errors


def safe_validate(model_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if model_type == "study_plan":
        is_valid, errors = validate_study_plan(data)
    elif model_type == "exercises":
        is_valid, errors = validate_exercises(data)
    elif model_type == "explanation":
        is_valid, errors = validate_explanation(data)
    else:
        return {"valid": False, "errors": [f"未知的模型类型: {model_type}"]}
    
    return {"valid": is_valid, "errors": errors}
