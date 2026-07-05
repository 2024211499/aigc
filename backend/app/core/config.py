# -*- coding: utf-8 -*-
"""全局配置，从环境变量 / .env 文件读取"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env（项目根目录）
_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_root / ".env")


class Settings:
    # ── 项目基础 ──────────────────────────────
    PROJECT_NAME: str = "AIGC智能学习平台"
    VERSION: str = "1.0.0"
    BASE_DIR: Path = Path(__file__).parent.parent.parent

    # ── 数据库 ────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR}/data/aigc.db"
    )

    # ── 文件存储 ──────────────────────────────
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    EXPORT_DIR: Path = BASE_DIR / "data" / "exports"
    VECTOR_DIR: Path = BASE_DIR / "data" / "vectorstore"
    EMBED_CACHE_DIR: Path = BASE_DIR / "data" / "embed_cache"

    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024)))  # 100MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt"}

    # ── LLM（2号 DeepSeek）────────────────────
    LLM_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL_NAME", "deepseek-chat")

    # ── 多模态 LLM（带图提问）────────────────
    MULTIMODAL_API_KEY: str = os.getenv("MULTIMODAL_API_KEY", "")
    MULTIMODAL_API_BASE: str = os.getenv("MULTIMODAL_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    MULTIMODAL_MODEL: str = os.getenv("MULTIMODAL_MODEL", "qwen-vl-plus")

    # ── Embedding（1号 SiliconFlow）───────────
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_API_BASE: str = os.getenv("EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    # ── 向量库 ────────────────────────────────
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "data" / "vectorstore")

    # ── 1号模块路径 ───────────────────────────
    RAG_MODULE_DIR: str = os.getenv("RAG_MODULE_DIR", str(BASE_DIR.parent / "rag"))

    # ── 2号模块路径 ───────────────────────────
    AGENT_MODULE_DIR: str = os.getenv("AGENT_MODULE_DIR", str(BASE_DIR.parent / "agents"))

    def __init__(self):
        # 确保目录存在
        for d in [self.UPLOAD_DIR, self.EXPORT_DIR, self.VECTOR_DIR, self.EMBED_CACHE_DIR,
                  self.BASE_DIR / "data"]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
