# -*- coding: utf-8 -*-
"""课程与章节接口"""

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from ..core.database import get_db, Course, Chapter, KnowledgePoint, Fragment, gen_id, now
from ..core.exceptions import NotFoundError
from ..agents.bridge import agent_service
from ..rag.bridge import rag_service

router = APIRouter()


@router.get("/courses", summary="获取课程列表")
def list_courses(db: Session = Depends(get_db)):
    courses = db.query(Course).order_by(Course.created_at.desc()).limit(100).all()
    items = []
    for c in courses:
        chapters = db.query(Chapter).filter(Chapter.course_id == c.id).all()
        ch_ids = [ch.id for ch in chapters]
        kp_count = 0
        if ch_ids:
            kp_count = db.query(KnowledgePoint).filter(KnowledgePoint.chapter_id.in_(ch_ids)).count()
        doc_count = db.query(Fragment.document_id).filter(Fragment.course_id == c.id).distinct().count()
        items.append(
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "chapter_count": len(chapters),
                "kp_count": kp_count,
                "document_count": doc_count,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
        )
    return {
        "success": True,
        "total": len(courses),
        "courses": items,
    }


@router.post("/courses", summary="创建课程")
def create_course(
    name: str = Body(..., embed=True),
    description: str = Body(default="", embed=True),
    db: Session = Depends(get_db),
):
    course = Course(id=gen_id(), name=name, description=description)
    db.add(course)
    db.commit()
    return {"success": True, "course_id": course.id, "name": name}


@router.get("/courses/{course_id}", summary="获取课程详情")
def get_course(course_id: str, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise NotFoundError("课程")
    chapters = db.query(Chapter).filter(Chapter.course_id == course_id)\
        .order_by(Chapter.order_index).all()
    return {
        "success": True,
        "course": {
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "chapter_count": len(chapters),
        },
        "chapters": [
            {"id": c.id, "chapter_number": c.chapter_number,
             "chapter_name": c.chapter_name, "order_index": c.order_index}
            for c in chapters
        ],
    }


@router.get("/courses/{course_id}/chapters", summary="获取章节目录")
def get_chapters(course_id: str, db: Session = Depends(get_db)):
    chapters = db.query(Chapter).filter(Chapter.course_id == course_id)\
        .order_by(Chapter.order_index).all()
    return {
        "success": True,
        "chapters": [
            {"id": c.id, "chapter_number": c.chapter_number,
             "chapter_name": c.chapter_name, "intro": c.chapter_intro}
            for c in chapters
        ],
    }


@router.get("/chapters/{chapter_id}", summary="获取章节详情")
def get_chapter(chapter_id: str, db: Session = Depends(get_db)):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        raise NotFoundError("章节")
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.chapter_id == chapter_id).all()
    return {
        "success": True,
        "chapter": {
            "id": ch.id,
            "chapter_name": ch.chapter_name,
            "chapter_number": ch.chapter_number,
            "chapter_intro": ch.chapter_intro,
            "chapter_summary": ch.chapter_summary,
            "kp_count": len(kps),
        },
        "knowledge_points": [
            {"id": k.id, "name": k.name, "type": k.kp_type, "difficulty": k.difficulty}
            for k in kps
        ],
    }


@router.get("/chapters/{chapter_id}/knowledge-points", summary="获取知识点列表")
def get_kps(chapter_id: str, db: Session = Depends(get_db)):
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.chapter_id == chapter_id).all()
    return {
        "success": True,
        "knowledge_points": [
            {"id": k.id, "name": k.name, "definition": k.definition,
             "type": k.kp_type, "difficulty": k.difficulty}
            for k in kps
        ],
    }


@router.get("/courses/{course_id}/knowledge-points", summary="获取课程下所有知识点")
def get_course_kps(
    course_id: str,
    chapter_id: str = "",
    kp_type: str = "",
    db: Session = Depends(get_db),
):
    """按课程（或章节）查询知识点列表"""
    query = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id)
    if chapter_id:
        query = query.filter(KnowledgePoint.chapter_id == chapter_id)
    if kp_type:
        query = query.filter(KnowledgePoint.kp_type == kp_type)
    kps = query.order_by(KnowledgePoint.created_at).all()
    return {
        "success": True,
        "total": len(kps),
        "knowledge_points": [
            {
                "id": k.id,
                "name": k.name,
                "definition": k.definition,
                "type": k.kp_type,
                "difficulty": k.difficulty,
                "chapter_id": k.chapter_id,
            }
            for k in kps
        ],
    }


@router.get("/courses/{course_id}/graph", summary="获取知识图谱")
def get_knowledge_graph(course_id: str, db: Session = Depends(get_db)):
    """调用 2号 KnowledgeGraphAgent 生成图谱数据"""
    frags = db.query(Fragment).filter(Fragment.course_id == course_id).limit(10).all()
    fragment_texts = [f.text for f in frags]

    graph = agent_service.generate_knowledge_graph(
        fragments=fragment_texts,
        course_id=course_id,
    )
    return {"success": True, "graph": graph}
