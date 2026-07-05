# -*- coding: utf-8 -*-
"""
数据库初始化与会话管理（SQLAlchemy + SQLite）
包含系统全部业务表
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    Boolean, Text, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool

from ..core.config import settings

# ─── 引擎 ────────────────────────────────────────────────────
_connect_args = {}
_poolclass = None
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    _poolclass = StaticPool

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    poolclass=_poolclass,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── 工具函数 ────────────────────────────────────────────────
def gen_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.utcnow()


# ════════════════════════════════════════════════════════════
#  数据库模型（共 17 张表）
# ════════════════════════════════════════════════════════════

class User(Base):
    """用户表"""
    __tablename__ = "users"
    id          = Column(String, primary_key=True, default=gen_id)
    username    = Column(String(64), unique=True, nullable=False)
    role        = Column(String(16), default="student")   # student / teacher
    created_at  = Column(DateTime, default=now)


class Course(Base):
    """课程表"""
    __tablename__ = "courses"
    id          = Column(String, primary_key=True, default=gen_id)
    name        = Column(String(128), nullable=False)
    description = Column(Text, default="")
    created_by  = Column(String, ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime, default=now)


class Document(Base):
    """文档表（用户上传的原始文件）"""
    __tablename__ = "documents"
    id              = Column(String, primary_key=True, default=gen_id)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    file_name       = Column(String(256), nullable=False)
    file_type       = Column(String(16), nullable=False)   # pdf/docx/pptx
    file_path       = Column(String(512), nullable=False)
    file_size       = Column(Integer, default=0)
    file_md5        = Column(String(32), default="")

    # 解析状态
    parse_status    = Column(String(32), default="uploaded")
    # uploaded / parsing / ocr_processing / chunking / embedding / indexed / failed / completed

    # 解析报告
    total_pages     = Column(Integer, default=0)
    parsed_pages    = Column(Integer, default=0)
    ocr_pages       = Column(Integer, default=0)
    failed_pages    = Column(Integer, default=0)
    total_chars     = Column(Integer, default=0)
    chapter_count   = Column(Integer, default=0)
    section_count   = Column(Integer, default=0)
    kp_count        = Column(Integer, default=0)
    formula_count   = Column(Integer, default=0)
    example_count   = Column(Integer, default=0)
    exercise_count  = Column(Integer, default=0)
    chunk_count     = Column(Integer, default=0)
    vector_count    = Column(Integer, default=0)
    parse_error     = Column(Text, default="")
    parse_seconds   = Column(Float, default=0.0)

    created_at      = Column(DateTime, default=now)
    updated_at      = Column(DateTime, default=now, onupdate=now)


class Chapter(Base):
    """章节表"""
    __tablename__ = "chapters"
    id              = Column(String, primary_key=True, default=gen_id)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=False)
    document_id     = Column(String, ForeignKey("documents.id"), nullable=True)
    chapter_number  = Column(String(32), default="")
    chapter_name    = Column(String(256), nullable=False)
    chapter_intro   = Column(Text, default="")
    chapter_summary = Column(Text, default="")
    order_index     = Column(Integer, default=0)
    created_at      = Column(DateTime, default=now)


class KnowledgePoint(Base):
    """知识点表"""
    __tablename__ = "knowledge_points"
    id              = Column(String, primary_key=True, default=gen_id)
    chapter_id      = Column(String, ForeignKey("chapters.id"), nullable=False)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=False)
    name            = Column(String(256), nullable=False)
    definition      = Column(Text, default="")
    kp_type         = Column(String(32), default="concept")   # concept/theorem/formula/method
    difficulty      = Column(String(16), default="medium")
    page_reference  = Column(String(64), default="")
    created_at      = Column(DateTime, default=now)


class Fragment(Base):
    """文本片段表（RAG chunk）"""
    __tablename__ = "fragments"
    id              = Column(String, primary_key=True, default=gen_id)
    document_id     = Column(String, ForeignKey("documents.id"), nullable=False)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    chapter_id      = Column(String, ForeignKey("chapters.id"), nullable=True)
    content_type    = Column(String(32), default="text")
    text            = Column(Text, nullable=False)
    page_start      = Column(Integer, default=0)
    page_end        = Column(Integer, default=0)
    has_formula     = Column(Boolean, default=False)
    has_example     = Column(Boolean, default=False)
    has_exercise    = Column(Boolean, default=False)
    from_ocr        = Column(Boolean, default=False)
    embedding_id    = Column(String(128), default="")
    created_at      = Column(DateTime, default=now)


class StudyPlan(Base):
    """学习计划表"""
    __tablename__ = "study_plans"
    id              = Column(String, primary_key=True, default=gen_id)
    user_id         = Column(String, ForeignKey("users.id"), nullable=True)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    chapter_id      = Column(String, ForeignKey("chapters.id"), nullable=True)
    title           = Column(String(256), nullable=False)
    content         = Column(JSON, default=dict)   # 完整 JSON 内容
    status          = Column(String(16), default="active")
    created_at      = Column(DateTime, default=now)


class Exercise(Base):
    """习题表"""
    __tablename__ = "exercises"
    id              = Column(String, primary_key=True, default=gen_id)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    chapter_id      = Column(String, ForeignKey("chapters.id"), nullable=True)
    kp_id           = Column(String, ForeignKey("knowledge_points.id"), nullable=True)
    question_type   = Column(String(32), default="choice")  # choice/fill/judge/calc/short/proof/code
    difficulty      = Column(String(16), default="medium")
    stem            = Column(Text, nullable=False)
    options         = Column(JSON, default=list)
    answer          = Column(Text, default="")
    explanation     = Column(Text, default="")
    score_criteria  = Column(Text, default="")
    mistake_tip     = Column(Text, default="")
    source_ref      = Column(String(256), default="")
    created_at      = Column(DateTime, default=now)


class AnswerRecord(Base):
    """答题记录表"""
    __tablename__ = "answer_records"
    id              = Column(String, primary_key=True, default=gen_id)
    user_id         = Column(String, ForeignKey("users.id"), nullable=True)
    exercise_id     = Column(String, ForeignKey("exercises.id"), nullable=False)
    student_answer  = Column(Text, default="")
    is_correct      = Column(Boolean, default=False)
    score           = Column(Float, default=0.0)
    diagnosis       = Column(JSON, default=dict)   # 错题诊断结果
    time_spent_sec  = Column(Integer, default=0)
    created_at      = Column(DateTime, default=now)


class Mistake(Base):
    """错题表"""
    __tablename__ = "mistakes"
    id              = Column(String, primary_key=True, default=gen_id)
    user_id         = Column(String, ForeignKey("users.id"), nullable=True)
    exercise_id     = Column(String, ForeignKey("exercises.id"), nullable=False)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    chapter_id      = Column(String, ForeignKey("chapters.id"), nullable=True)
    error_type      = Column(String(64), default="")
    error_reason    = Column(Text, default="")
    mastered        = Column(Boolean, default=False)
    review_count    = Column(Integer, default=0)
    last_reviewed   = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=now)


class ExamPaper(Base):
    """试卷表"""
    __tablename__ = "exam_papers"
    id              = Column(String, primary_key=True, default=gen_id)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    created_by      = Column(String, ForeignKey("users.id"), nullable=True)
    title           = Column(String(256), nullable=False)
    exam_type       = Column(String(32), default="unit")
    content         = Column(JSON, default=dict)
    total_score     = Column(Float, default=100.0)
    duration_min    = Column(Integer, default=90)
    with_answer     = Column(Boolean, default=True)
    with_analysis   = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=now)


class VideoLesson(Base):
    """微课表"""
    __tablename__ = "video_lessons"
    id              = Column(String, primary_key=True, default=gen_id)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    title           = Column(String(256), nullable=False)
    topic           = Column(String(256), default="")
    script          = Column(JSON, default=dict)   # 微课脚本 JSON
    ppt_content     = Column(JSON, default=dict)   # PPT 内容 JSON
    ppt_file_path   = Column(String(512), default="")
    audio_file_path = Column(String(512), default="")
    video_file_path = Column(String(512), default="")
    status          = Column(String(32), default="pending")
    duration_sec    = Column(Integer, default=0)
    created_at      = Column(DateTime, default=now)


class ExportFile(Base):
    """导出文件表"""
    __tablename__ = "export_files"
    id              = Column(String, primary_key=True, default=gen_id)
    user_id         = Column(String, ForeignKey("users.id"), nullable=True)
    source_type     = Column(String(32), default="")   # study_plan/exam/exercises
    source_id       = Column(String, default="")
    export_format   = Column(String(16), default="pdf")
    file_path       = Column(String(512), nullable=False)
    file_name       = Column(String(256), nullable=False)
    file_size       = Column(Integer, default=0)
    created_at      = Column(DateTime, default=now)


class LearningLog(Base):
    """学习行为记录表"""
    __tablename__ = "learning_logs"
    id              = Column(String, primary_key=True, default=gen_id)
    user_id         = Column(String, ForeignKey("users.id"), nullable=True)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    action          = Column(String(64), nullable=False)
    detail          = Column(JSON, default=dict)
    duration_sec    = Column(Integer, default=0)
    created_at      = Column(DateTime, default=now)


class ParseTask(Base):
    """文档解析异步任务表"""
    __tablename__ = "parse_tasks"
    id              = Column(String, primary_key=True, default=gen_id)
    document_id     = Column(String, ForeignKey("documents.id"), nullable=False)
    status          = Column(String(32), default="pending")
    progress        = Column(Integer, default=0)   # 0-100
    current_step    = Column(String(64), default="")
    error_msg       = Column(Text, default="")
    started_at      = Column(DateTime, nullable=True)
    finished_at     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=now)


class GenerateTask(Base):
    """AI生成异步任务表"""
    __tablename__ = "generate_tasks"
    id              = Column(String, primary_key=True, default=gen_id)
    task_type       = Column(String(64), nullable=False)   # study_plan/exam/micro_lesson...
    request_params  = Column(JSON, default=dict)
    result          = Column(JSON, default=dict)
    status          = Column(String(32), default="pending")
    error_msg       = Column(Text, default="")
    started_at      = Column(DateTime, nullable=True)
    finished_at     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=now)


class UserProfile(Base):
    """学生学习画像表"""
    __tablename__ = "user_profiles"
    id              = Column(String, primary_key=True, default=gen_id)
    user_id         = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    course_id       = Column(String, ForeignKey("courses.id"), nullable=True)
    profile_data    = Column(JSON, default=dict)   # 完整画像 JSON
    updated_at      = Column(DateTime, default=now, onupdate=now)


# ─── 初始化 ──────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
