# -*- coding: utf-8 -*-
"""
RAG 检索桥接层
将 1号队员的解析/检索模块封装为后端服务可调用的接口
兼容 1号代码未整合时的降级模式
"""

import os
import sys
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..core.config import settings

logger = logging.getLogger(__name__)

# ─── 尝试导入 1号模块 ────────────────────────────────────────
_rag_available = False
_pdf_extractor = None
_embedding_provider = None

def _try_import_rag():
    global _rag_available
    rag_dir = settings.RAG_MODULE_DIR
    # 将 rag/ 的上级目录（项目根）加入 sys.path，以包的形式导入
    rag_parent = str(Path(rag_dir).parent)
    if os.path.isdir(rag_dir) and rag_parent not in sys.path:
        sys.path.insert(0, rag_parent)
    try:
        # 以包形式导入 1号的核心模块（rag 目录需有 __init__.py）
        from rag.retrieval.embeddings import EmbeddingProvider  # type: ignore
        from rag.pipeline.index_manager import IndexManager     # type: ignore
        _rag_available = True
        logger.info("✅ 1号 RAG 模块加载成功")
    except ImportError as e:
        logger.warning(f"⚠️  1号 RAG 模块未找到，使用内置简化检索: {e}")
        _rag_available = False

_try_import_rag()


# ════════════════════════════════════════════════════════════
#  文档解析服务
# ════════════════════════════════════════════════════════════

class DocumentParseService:
    """
    文档解析服务
    优先调用 1号模块；若不可用则使用内置简化版
    """

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        解析文档，返回结构化结果

        Returns:
            {
                text: str,
                pages: int,
                chapters: list,
                knowledge_points: list,
                formulas: list,
                examples: list,
                exercises: list,
                from_ocr: bool,
                error: str
            }
        """
        ext = Path(file_path).suffix.lower()
        start = time.time()

        try:
            if _rag_available:
                return self._parse_via_rag(file_path, ext)
            else:
                return self._parse_builtin(file_path, ext)
        except Exception as e:
            logger.error(f"文档解析失败: {e}", exc_info=True)
            return self._empty_result(error=str(e))
        finally:
            elapsed = round(time.time() - start, 2)
            logger.info(f"解析耗时: {elapsed}s  文件: {Path(file_path).name}")

    def _parse_via_rag(self, file_path: str, ext: str) -> Dict[str, Any]:
        """调用 1号模块解析"""
        from rag.parsing.document_parser import parse_document  # type: ignore
        text = parse_document(file_path)
        return self._analyze_text(text, from_ocr=False)

    def _parse_builtin(self, file_path: str, ext: str) -> Dict[str, Any]:
        """内置简化解析（兜底）"""
        text = ""
        from_ocr = False

        if ext == ".pdf":
            text = self._extract_pdf(file_path)
        elif ext in (".docx", ".doc"):
            text = self._extract_docx(file_path)
        elif ext in (".pptx", ".ppt"):
            text = self._extract_pptx(file_path)
        elif ext == ".txt":
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()

        return self._analyze_text(text, from_ocr=from_ocr)

    def _extract_pdf(self, path: str) -> str:
        try:
            import PyMuPDF
            doc = PyMuPDF.open(path)
            pages = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(pages)
        except ImportError:
            pass
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as e:
            logger.warning(f"PDF 提取失败: {e}")
            return ""

    def _extract_docx(self, path: str) -> str:
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            logger.warning(f"DOCX 提取失败: {e}")
            return ""

    def _extract_pptx(self, path: str) -> str:
        try:
            from pptx import Presentation
            prs = Presentation(path)
            texts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        texts.append(shape.text)
            return "\n".join(texts)
        except Exception as e:
            logger.warning(f"PPTX 提取失败: {e}")
            return ""

    def _analyze_text(self, text: str, from_ocr: bool = False) -> Dict[str, Any]:
        """从文本中分析章节/知识点等结构"""
        import re

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        total_chars = len(text)

        # 章节识别（简化规则）
        chapter_patterns = [
            r'^第[一二三四五六七八九十百\d]+章',
            r'^Chapter\s+\d+',
            r'^\d+\.\s+[^\d]',
        ]
        chapters = []
        for line in lines:
            for pat in chapter_patterns:
                if re.match(pat, line):
                    chapters.append(line[:80])
                    break

        # 公式识别（含数学符号）
        formula_keywords = ['=', '∫', '∑', '∏', 'lim', 'sin', 'cos', 'tan', 'log', '→', '∞']
        formulas = [l for l in lines if any(k in l for k in formula_keywords) and len(l) < 200]

        # 例题识别
        examples = [l for l in lines if re.match(r'^例\d*[：:]|^Example\s+\d+', l)]

        # 习题识别
        exercises = [l for l in lines if re.match(r'^(习题|练习|作业|Exercise)\s*\d*[：:]?', l)]

        # 知识点（定义/定理/性质）
        kp_lines = [l for l in lines if re.match(r'^(定义|定理|性质|引理|推论|命题)\s*\d*[：:]', l)]

        return {
            "text": text,
            "total_chars": total_chars,
            "pages": max(1, total_chars // 2000),   # 估算页数
            "chapters": chapters,
            "knowledge_points": kp_lines[:50],
            "formulas": formulas[:100],
            "examples": examples[:50],
            "exercises": exercises[:50],
            "from_ocr": from_ocr,
            "error": "",
        }

    @staticmethod
    def _empty_result(error: str = "") -> Dict[str, Any]:
        return {
            "text": "", "total_chars": 0, "pages": 0,
            "chapters": [], "knowledge_points": [],
            "formulas": [], "examples": [], "exercises": [],
            "from_ocr": False, "error": error,
        }


# ════════════════════════════════════════════════════════════
#  向量检索服务
# ════════════════════════════════════════════════════════════

class RAGRetrieveService:
    """
    RAG 检索服务
    对 1号 IndexManager / VectorStore 的封装
    支持按 course_id 检索相关文本片段
    """

    def __init__(self):
        self._index_managers: Dict[str, Any] = {}

    def _get_manager(self, course_id: str):
        """懒加载每门课程的索引管理器"""
        if course_id in self._index_managers:
            return self._index_managers[course_id]

        if not _rag_available:
            return None

        try:
            from rag.retrieval.embeddings import EmbeddingProvider  # type: ignore
            from rag.storage.vector_store import VectorStore        # type: ignore
            from rag.pipeline.index_manager import IndexManager     # type: ignore

            emb = EmbeddingProvider(
                provider="local",
                model_name="paraphrase-multilingual-MiniLM-L12-v2",
                cache_dir=str(settings.EMBED_CACHE_DIR),
            )

            from rag.config import VectorStoreConfig  # type: ignore  (config 仍在根目录)
            store = VectorStore(config=VectorStoreConfig(
                collection_name=f"course_{course_id}",
                persist_dir=settings.CHROMA_PERSIST_DIR,
            ))
            manager = IndexManager(store, emb, course_id=course_id)
            self._index_managers[course_id] = manager
            return manager
        except Exception as e:
            logger.warning(f"IndexManager 初始化失败: {e}")
            return None

    def index_document(self, course_id: str, file_path: str, force: bool = False) -> int:
        """将文档索引到向量库，返回 chunk 数量"""
        manager = self._get_manager(course_id)
        if manager:
            try:
                return manager.index_document(file_path, force=force)
            except Exception as e:
                logger.error(f"向量索引失败: {e}")
        return 0

    def retrieve(
        self,
        course_id: str,
        query: str,
        top_k: int = 5,
        chapter: Optional[str] = None,
    ) -> List[str]:
        """
        检索相关片段，返回文本列表

        优先用 1号模块；降级返回空列表（由调用方从 DB 里取 fragments）
        """
        manager = self._get_manager(course_id)
        if manager:
            try:
                # 1号的 VectorStore 检索接口
                store = manager.store
                results = store.query(query_text=query, top_k=top_k)
                return [doc for doc in results.get("documents", [[]])[0]]
            except Exception as e:
                logger.warning(f"向量检索失败: {e}")

        # 降级：从数据库 fragments 表做关键词匹配
        return self._keyword_fallback(course_id, query, top_k)

    def _keyword_fallback(self, course_id: str, query: str, top_k: int) -> List[str]:
        """关键词降级检索（从 SQLite）"""
        try:
            from ..core.database import SessionLocal, Fragment
            db = SessionLocal()
            frags = (
                db.query(Fragment)
                .filter(Fragment.course_id == course_id)
                .limit(top_k * 5)
                .all()
            )
            db.close()

            keywords = query.lower().split()
            scored = []
            for f in frags:
                score = sum(1 for kw in keywords if kw in f.text.lower())
                if score > 0:
                    scored.append((score, f.text))
            scored.sort(reverse=True)
            return [t for _, t in scored[:top_k]]
        except Exception as e:
            logger.warning(f"关键词降级检索失败: {e}")
            return []


# ─── 单例 ────────────────────────────────────────────────────
parse_service = DocumentParseService()
rag_service = RAGRetrieveService()
