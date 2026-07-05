# -*- coding: utf-8 -*-
from .llm_client import call_llm, call_llm_stream, extract_json_from_response
from .memory_manager import MemoryManager
from .models import StudyPlan, ExerciseSet, LayeredExplanation
from .validators import safe_validate

try:
    from core.crew_config import EducationalCrew
    _has_crewai = True
except ImportError:
    EducationalCrew = None
    _has_crewai = False

_all_items = [
    "call_llm",
    "call_llm_stream",
    "extract_json_from_response",
    "MemoryManager",
    "StudyPlan",
    "ExerciseSet",
    "LayeredExplanation",
    "safe_validate",
]

if _has_crewai:
    _all_items.append("EducationalCrew")

__all__ = _all_items
