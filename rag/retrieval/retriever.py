"""检索核心：元数据精确过滤优先，再语义检索，必要时 fuzzy fallback。"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional

from rapidfuzz import fuzz

from ..config import RetrieverConfig
from ..processing.splitter import normalize_section
from ..storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    text: str
    metadata: Dict
    distance: float

    @property
    def score(self) -> float:
        """余弦距离的粗略相关性分数，越大越相关。"""
        return 1.0 - float(self.distance)


class Retriever:
    """面向 RAG 的检索器。"""

    def __init__(
        self,
        vector_store: VectorStore,
        config: Optional[RetrieverConfig] = None,
        *,
        course_id: Optional[str] = None,
        db_path: Optional[str] = None,
        persist_dir: Optional[str] = None,
    ):
        warnings.warn(
            "rag.retriever.Retriever is deprecated; use rag.retrieve(...) as the stable API.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.store = vector_store
        self.config = config or RetrieverConfig()
        self.course_id = course_id
        self.db_path = db_path
        self.persist_dir = persist_dir or getattr(getattr(vector_store, "config", None), "persist_dir", None)

    def retrieve(
        self,
        query: str,
        chapter: Optional[str] = None,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None,
    ) -> List[RetrievalResult]:
        """
        检索文本片段。

        参数：
        - query: 用户问题或检索关键词；
        - chapter: 可选章节名，先按 section_norm 精确过滤，再 fuzzy；
        - filters: 额外元数据过滤，如 {"doc_name": "高等数学.pdf", "page_start": {"$gte": 120}}。
        """
        top_k = top_k or self.config.default_top_k
        if self.course_id:
            from .rag import retrieve as core_retrieve
            hits = core_retrieve(
                query,
                course_id=self.course_id,
                chapter=chapter,
                filters=filters,
                top_k=top_k,
                db_path=self.db_path,
                persist_dir=self.persist_dir,
            )
            return [RetrievalResult(text=h.get("text", ""), metadata=h, distance=1.0 - float(h.get("score", 0.0) or 0.0)) for h in hits]
        if self.store.count() == 0:
            logger.warning("向量库为空")
            return self._mock_results(query, top_k) if self.config.enable_mock_fallback else []

        base_filters = filters or {}
        strategies = self._build_filter_strategies(chapter, base_filters)
        seen = set()

        for name, where in strategies:
            logger.debug("检索策略: %s where=%s", name, where)
            results = self._query_to_results(query, top_k=max(top_k, self.config.prefilter_top_k), where=where)
            if not results:
                continue

            deduped: List[RetrievalResult] = []
            for r in results:
                key = (r.metadata.get("doc_md5"), r.metadata.get("chunk_index"), r.text[:50])
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(r)

            if deduped:
                if self.config.enable_rerank:
                    from .reranker import rerank
                    deduped = rerank(query, deduped, top_k)
                return deduped[:top_k]

        return self._mock_results(query, top_k) if self.config.enable_mock_fallback else []

    def _query_to_results(self, query: str, top_k: int, where: Optional[Dict]) -> List[RetrievalResult]:
        result = self.store.query(query, top_k=top_k, where=where)
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        return [
            RetrievalResult(text=docs[i], metadata=metas[i] or {}, distance=float(dists[i]))
            for i in range(len(docs))
            if docs[i]
        ]

    def _build_filter_strategies(self, chapter: Optional[str], base_filters: Dict) -> List:
        strategies = []
        base_where = self._metadata_where(base_filters)

        if self.config.use_chapter_filter and chapter:
            chapter_norm = normalize_section(chapter)
            exact_chapter_where = self._and_where(base_where, {"section_norm": chapter_norm})
            strategies.append(("exact_chapter", exact_chapter_where))

            if self.config.allow_fuzzy_chapter_fallback:
                fuzzy_where = self._build_fuzzy_chapter_filter(chapter, base_where)
                if fuzzy_where:
                    strategies.append(("fuzzy_chapter", fuzzy_where))

        if base_where:
            strategies.append(("base_filters", base_where))

        if self.config.allow_no_filter_fallback:
            strategies.append(("no_filter", None))

        if not strategies:
            strategies.append(("no_filter", None))

        return strategies

    @staticmethod
    def _metadata_where(filters: Optional[Dict]) -> Optional[Dict]:
        if not filters:
            return None
        conditions = []
        for k, v in filters.items():
            if isinstance(v, dict):
                conditions.append({k: v})
            else:
                conditions.append({k: v})
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    @staticmethod
    def _and_where(*clauses: Optional[Dict]) -> Optional[Dict]:
        valid = [c for c in clauses if c]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]
        return {"$and": valid}

    def _build_fuzzy_chapter_filter(self, chapter: str, base_where: Optional[Dict]) -> Optional[Dict]:
        all_sections = self.store.get_all_sections()
        if not all_sections:
            return None

        matched = [
            s for s in all_sections
            if fuzz.partial_ratio(normalize_section(s), normalize_section(chapter)) >= self.config.fuzzy_threshold
            or fuzz.token_set_ratio(s, chapter) >= self.config.fuzzy_threshold
        ]
        if not matched:
            return None

        return self._and_where(base_where, {"section": {"$in": matched}})

    @staticmethod
    def _mock_results(query: str, top_k: int) -> List[RetrievalResult]:
        samples = [
            "Mock：向量库为空或检索失败。请先运行 IndexManager.index_document(...) 建立索引。",
            f"Mock：当前查询为 {query!r}。",
        ]
        return [RetrievalResult(text=x, metadata={"source": "mock"}, distance=1.0) for x in samples[:top_k]]
