# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator_agent import OrchestratorAgent

app = FastAPI(
    title="AIGC教育智能体API",
    description="提供教育智能体的REST API接口",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = OrchestratorAgent()


class ExerciseRequest(BaseModel):
    user_input: str
    fragments: Optional[List[str]] = []
    course_id: Optional[str] = ""


class LearningPackageRequest(BaseModel):
    user_input: str
    fragments: Optional[List[str]] = []
    course_id: Optional[str] = ""


class ExamRequest(BaseModel):
    user_input: str
    fragments: Optional[List[str]] = []
    course_id: Optional[str] = ""


class MicroLessonRequest(BaseModel):
    user_input: str
    fragments: Optional[List[str]] = []
    course_id: Optional[str] = ""


class PPTRequest(BaseModel):
    user_input: str
    fragments: Optional[List[str]] = []
    course_id: Optional[str] = ""


class HomeworkTutorRequest(BaseModel):
    user_input: str
    fragments: Optional[List[str]] = []
    question: Optional[str] = ""


class KnowledgeGraphRequest(BaseModel):
    user_input: str
    fragments: Optional[List[str]] = []
    course_id: Optional[str] = ""


class IntentRequest(BaseModel):
    user_input: str


class ParamExtractRequest(BaseModel):
    user_input: str


@app.get("/")
async def root():
    return {
        "message": "AIGC教育智能体API",
        "version": "1.0.0",
        "endpoints": [
            "/api/intent/recognize",
            "/api/intent/extract-params",
            "/api/exercise",
            "/api/learning-package",
            "/api/exam",
            "/api/micro-lesson",
            "/api/ppt",
            "/api/homework-tutor",
            "/api/knowledge-graph"
        ]
    }


@app.post("/api/intent/recognize")
async def recognize_intent(request: IntentRequest):
    task_type = orchestrator.recognize_task_by_llm(request.user_input)
    workflow_info = orchestrator._workflow_map.get(task_type)
    
    return {
        "task_type": task_type,
        "workflow_name": workflow_info["name"] if workflow_info else None,
        "confidence": 0.9
    }


@app.post("/api/intent/extract-params")
async def extract_params(request: ParamExtractRequest):
    params = orchestrator.extract_params_from_input(request.user_input)
    return {"params": params}


@app.post("/api/exercise")
async def generate_exercise(request: ExerciseRequest):
    try:
        params = orchestrator.extract_params_from_input(request.user_input)
        exercise_count = params.get('exercise_count', 5)
        
        result = orchestrator.run_exercise_workflow(
            course_id=request.course_id,
            fragments=request.fragments,
            exercise_count=exercise_count
        )
        
        return {
            "success": True,
            "data": result,
            "exercise_count": exercise_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/learning-package")
async def generate_learning_package(request: LearningPackageRequest):
    try:
        params = orchestrator.extract_params_from_input(request.user_input)
        
        user_profile = {
            "course_name": "",
            "knowledge_points": [],
            "student_level": "中等",
            "weak_points": [],
            "history_mistakes": []
        }
        
        result = orchestrator.run_learning_package_workflow(
            course_id=request.course_id,
            fragments=request.fragments,
            user_profile=user_profile,
            study_days=params.get('study_days', 7),
            daily_time=params.get('daily_time', 60),
            exercise_count=params.get('exercise_count', 10)
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/exam")
async def generate_exam(request: ExamRequest):
    try:
        params = orchestrator.extract_params_from_input(request.user_input)
        
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
        
        result = orchestrator.run_exam_workflow(
            course_id=request.course_id,
            chapters=[],
            exam_config=exam_config,
            fragments=request.fragments
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/micro-lesson")
async def generate_micro_lesson(request: MicroLessonRequest):
    try:
        params = orchestrator.extract_params_from_input(request.user_input)
        
        result = orchestrator.run_micro_lesson_workflow(
            course_id=request.course_id,
            fragments=request.fragments,
            topic=params.get('topic', ''),
            style=params.get('style', '讲解式'),
            duration=params.get('duration', 300)
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ppt")
async def generate_ppt(request: PPTRequest):
    try:
        params = orchestrator.extract_params_from_input(request.user_input)
        
        result = orchestrator.run_ppt_workflow(
            course_id=request.course_id,
            fragments=request.fragments,
            topic=params.get('topic', '')
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/homework-tutor")
async def homework_tutor(request: HomeworkTutorRequest):
    try:
        params = orchestrator.extract_params_from_input(request.user_input)
        
        result = orchestrator.run_homework_tutor_workflow(
            question=params.get('topic', request.question),
            fragments=request.fragments
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge-graph")
async def generate_knowledge_graph(request: KnowledgeGraphRequest):
    try:
        result = orchestrator.run_knowledge_graph_workflow(
            course_id=request.course_id,
            fragments=request.fragments
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
