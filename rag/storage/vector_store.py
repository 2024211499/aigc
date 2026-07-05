"""Chroma 向量存储封装：线程安全、元数据过滤、原子 upsert。"""

from __future__ import annotations

import logging
import threading
import warnings
from typing import Dict, List, Optional

from ..config import VectorStoreConfig
from ..exceptions import VectorStoreError

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB 持久化向量库封装。"""

    def __init__(self, config: Optional[VectorStoreConfig] = None, embedding_fn=None):
        warnings.warn(
            "rag.vector_store.VectorStore is deprecated; use rag.index_document/retrieve with CourseDB + Chroma.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.config = config or VectorStoreConfig()
        self.embedding_fn = embedding_fn
        self._client = None
        self._collection = None
        self._write_lock = threading.Lock()
        self._read_lock = threading.RLock()

    @property
    def client(self):
        if self._client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise VectorStoreError("缺少 chromadb：pip install chromadb") from exc
            self._client = chromadb.PersistentClient(path=self.config.persist_dir)
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            with self._write_lock:
                if self._collection is None:
                    self._collection = self.client.get_or_create_collection(
                        name=self.config.collection_name,
                        embedding_function=self.embedding_fn,
                        metadata={"hnsw:space": "cosine"},
                    )
        return self._collection

    @staticmethod
    def _sanitize_metadata(meta: Dict) -> Dict:
        allowed = (str, int, float, bool)
        out = {}
        for k, v in (meta or {}).items():
            if v is None:
                continue
            if isinstance(v, allowed):
                out[str(k)] = v
            else:
                out[str(k)] = str(v)
        return out

    def add_chunks(self, chunks: List[Dict], source_info: Optional[Dict] = None) -> int:
        """追加分块。返回实际写入数量。"""
        source_info = source_info or {}
        documents, metadatas, ids = [], [], []

        for i, chunk in enumerate(chunks):
            text = (chunk.get("text") or "").strip()
            if not text:
                continue

            meta = {k: v for k, v in chunk.items() if k != "text"}
            meta.update(source_info)
            meta["text_chars"] = len(text)
            metadatas.append(self._sanitize_metadata(meta))
            documents.append(text)

            doc_key = source_info.get("doc_md5") or source_info.get("doc_name") or "doc"
            chunk_idx = meta.get("chunk_index", i)
            page = meta.get("page_start", "na")
            ids.append(f"{doc_key}_{page}_{chunk_idx}")

        if not documents:
            return 0

        with self._write_lock:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        logger.info("向量库新增 %s 个片段", len(documents))
        return len(documents)

    def upsert_chunks(self, chunks: List[Dict], source_info: Optional[Dict] = None) -> int:
        """按 doc_md5 或 doc_path 删除旧片段后重新插入。"""
        source_info = source_info or {}
        where = None
        if source_info.get("doc_md5"):
            where = {"doc_md5": source_info["doc_md5"]}
        elif source_info.get("doc_path"):
            where = {"doc_path": source_info["doc_path"]}

        with self._write_lock:
            if where:
                try:
                    self.collection.delete(where=where)
                except Exception:
                    # Chroma 在不存在匹配项时可能直接无操作；这里不阻断。
                    logger.debug("删除旧分块时无匹配或已为空: %s", where)
        return self.add_chunks(chunks, source_info)

    def query(self, query_text: str, top_k: int = 5, where: Optional[Dict] = None) -> Dict:
        """语义检索。"""
        with self._read_lock:
            return self.collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

    def get(self, where: Optional[Dict] = None, limit: Optional[int] = None) -> Dict:
        with self._read_lock:
            kwargs = {"include": ["metadatas", "documents"]}
            if where:
                kwargs["where"] = where
            if limit is not None:
                kwargs["limit"] = limit
            return self.collection.get(**kwargs)

    def get_all_sections(self) -> List[str]:
        """获取所有章节名，用于 fuzzy chapter filter。"""
        results = self.collection.get(include=["metadatas"])
        sections = set()
        for meta in results.get("metadatas", []) or []:
            s = meta.get("section") if meta else None
            if s:
                sections.add(str(s))
        return sorted(sections)

    def count(self) -> int:
        with self._read_lock:
            return int(self.collection.count())

    def delete_by_filter(self, where: Dict) -> None:
        with self._write_lock:
            self.collection.delete(where=where)

    def clear(self) -> None:
        with self._write_lock:
            try:
                self.client.delete_collection(self.config.collection_name)
            finally:
                self._collection = None
