# -*- coding: utf-8 -*-
"""
AIGC 智能学习资源生成平台 —— 后端主入口
3号队员：后端服务与系统工程
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings
from .core.logger import setup_logging
from .core.database import init_db
from .core.exceptions import AppException

from .api import (
    upload,
    courses,
    learning_package,
    explanation,
    exercises,
    mistakes,
    exam,
    export,
    micro_lesson,
    profile,
    dashboard,
    voice,
)

# ─── 日志初始化 ──────────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)


# ─── 生命周期 ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 服务启动中...")
    init_db()
    logger.info("✅ 数据库初始化完成")
    yield
    logger.info("🛑 服务关闭")


# ─── FastAPI 应用 ────────────────────────────────────────────
app = FastAPI(
    title="AIGC 智能学习资源生成平台",
    description=(
        "面向大学生学习与教师备课的 AIGC 智能平台。\n\n"
        "支持上传 PDF/Word/PPT，自动解析建库，生成学习包、讲解、习题、试卷、微课等。"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ───────────────────────────────────────────────────
import os as _os
_CORS_ORIGINS = _os.getenv("CORS_ORIGINS", "").split(",") if _os.getenv("CORS_ORIGINS") else []

app.add_middleware(
    CORSMiddleware,
    # 开发阶段允许所有来源，生产环境通过 CORS_ORIGINS 环境变量指定白名单
    # 注意：allow_origins=["*"] 与 allow_credentials=True 不兼容（浏览器会拒绝）
    # 若需携带 Cookie/Authorization，请在 .env 中设置 CORS_ORIGINS=http://your-frontend
    allow_origins=_CORS_ORIGINS if _CORS_ORIGINS else ["*"],
    allow_credentials=bool(_CORS_ORIGINS),  # 只有明确指定来源时才允许凭据
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── 全局异常处理 ────────────────────────────────────────────
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.message, "code": exc.code},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "服务器内部错误", "code": "INTERNAL_ERROR"},
    )


# ─── 请求计时中间件 ──────────────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 1)
    response.headers["X-Process-Time"] = f"{duration}ms"
    return response


# ─── 路由注册 ────────────────────────────────────────────────
PREFIX = "/api"

app.include_router(upload.router,           prefix=PREFIX, tags=["📁 文件上传与解析"])
app.include_router(courses.router,          prefix=PREFIX, tags=["📚 课程与章节"])
app.include_router(learning_package.router, prefix=PREFIX, tags=["🎓 学习包生成"])
app.include_router(explanation.router,      prefix=PREFIX, tags=["💡 智能讲解"])
app.include_router(exercises.router,        prefix=PREFIX, tags=["📝 习题与答题"])
app.include_router(mistakes.router,         prefix=PREFIX, tags=["❌ 错题本"])
app.include_router(exam.router,             prefix=PREFIX, tags=["📋 智能组卷"])
app.include_router(export.router,           prefix=PREFIX, tags=["📤 导出服务"])
app.include_router(micro_lesson.router,     prefix=PREFIX, tags=["🎬 微课生成"])
app.include_router(profile.router,          prefix=PREFIX, tags=["👤 学习画像"])
app.include_router(dashboard.router,        prefix=PREFIX, tags=["📊 数据看板"])
app.include_router(voice.router,            prefix=PREFIX, tags=["🎤 语音与文本"])


# ─── 根路由 ─────────────────────────────────────────────────
@app.get("/", tags=["系统"])
async def root():
    return {
        "name": "AIGC 智能学习资源生成平台",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "team": "后端服务与系统工程",
    }


@app.get("/api/health", tags=["系统"])
async def health():
    return {"status": "ok", "timestamp": time.time()}
