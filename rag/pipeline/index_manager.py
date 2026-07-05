"""Deprecated compatibility wrapper for the unified indexing pipeline."""

from __future__ import annotations

import warnings
from typing import Optional

from ..config import ExtractionConfig, SplitterConfig
from ..retrieval.embeddings import EmbeddingProvider
from .pipeline import index_document as core_index_document
from ..storage.sqlite import CourseDB
from ..storage.vector_store import VectorStore


class IndexManager:
    """
    Deprecated wrapper around rag.index_document(...).

    The old IndexManager used a separate VectorStore-only path.  That created
    divergent behavior from the new CourseDB + FTS5 + Chroma pipeline.  The
    wrapper now keeps old code from breaking while routing indexing through the
    single core API.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: Optional[EmbeddingProvider] = None,
        splitter_config: Optional[SplitterConfig] = None,
        extraction_config: Optional[ExtractionConfig] = None,
        *,
        course_id: str = "legacy_course",
        course_name: Optional[str] = None,
        db_path: Optional[str] = None,
        persist_dir: Optional[str] = None,
        build_vector: bool = False,
    ):
        warnings.warn(
            "rag.index_manager.IndexManager is deprecated; use rag.index_document(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.store = vector_store
        self.embedding_provider = embedding_provider
        self.splitter_config = splitter_config or SplitterConfig()
        self.extraction_config = extraction_config or ExtractionConfig()
        self.course_id = course_id
        self.course_name = course_name or course_id
        self.db_path = db_path
        self.persist_dir = persist_dir or getattr(getattr(vector_store, "config", None), "persist_dir", None)
        self.build_vector = build_vector

    def is_indexed(self, doc_path: str) -> bool:
        from .pipeline import _document_id
        import os

        document_id = _document_id(self.course_id, os.path.abspath(doc_path))
        return CourseDB(self.db_path).get_document(document_id) is not None

    def index_document(self, doc_path: str, force: bool = False) -> int:
        result = core_index_document(
            doc_path,
            course_id=self.course_id,
            course_name=self.course_name,
            force=force,
            config=self.extraction_config,
            db_path=self.db_path,
            persist_dir=self.persist_dir,
            build_vector=self.build_vector,
        )
        return int((result.get("report") or {}).get("chunk_count", len(result.get("fragments") or [])))
