"""Embedding 与 Chroma 向量索引。"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from ..config import EmbeddingConfig
from ..exceptions import EmbeddingError, VectorStoreError
from .sqlite import CourseDB


DEFAULT_VECTOR_DIR = os.getenv("COURSE_KB_VECTOR_DIR", "./chroma_courses")
EMBED_DIM = 384
logger = logging.getLogger(__name__)


def _hash_embedding(text: str, dim: int = EMBED_DIM) -> List[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[一-鿿]|[A-Za-z0-9_]+", text.lower())
    if not tokens:
        tokens = [text[:64] or "empty"]
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8", errors="ignore")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _normalize_vectors(vectors: Sequence[Sequence[float]]) -> List[List[float]]:
    out: List[List[float]] = []
    for vector in vectors:
        vals = [float(x) for x in vector]
        norm = math.sqrt(sum(x * x for x in vals)) or 1.0
        out.append([x / norm for x in vals])
    return out


def get_embedding(
    texts: Union[str, Sequence[str]],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    config: Optional[EmbeddingConfig] = None,
) -> List[List[float]]:
    """
    调用 Embedding API。

    支持：
    - OpenAI 或 OpenAI 兼容接口：OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_EMBEDDING_MODEL；
    - 阿里云百炼兼容模式：DASHSCOPE_API_KEY；
    - 智谱兼容接口：ZHIPUAI_API_KEY；
    - 无密钥时使用 deterministic hash embedding，保证演示和测试不断链。
    """
    cfg = config or EmbeddingConfig(provider=provider or os.getenv("EMBEDDING_PROVIDER") or "local", model_name=model or os.getenv("LOCAL_EMBEDDING_MODEL") or (model or EmbeddingConfig.model_name))
    batch = [texts] if isinstance(texts, str) else [str(x or "") for x in texts]
    provider = (provider or cfg.provider).lower()

    if provider in {"openai", "aliyun", "gte", "zhipu", "auto"}:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        embed_model = model or os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small"

        if provider in {"auto", "aliyun", "gte"} and os.getenv("DASHSCOPE_API_KEY"):
            api_key = os.getenv("DASHSCOPE_API_KEY")
            base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            embed_model = model or os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3")

        if provider in {"auto", "zhipu"} and os.getenv("ZHIPUAI_API_KEY"):
            api_key = os.getenv("ZHIPUAI_API_KEY")
            base_url = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
            embed_model = model or os.getenv("ZHIPU_EMBEDDING_MODEL", "embedding-3")

        if api_key:
            return _embed_openai_compatible(batch, api_key, base_url, embed_model, cfg)
        if provider in {"openai", "aliyun", "gte", "zhipu"}:
            raise EmbeddingError("在线 Embedding 未配置 API Key")

    if provider in {"local", "auto"}:
        try:
            encoder = _get_sentence_transformer(model or cfg.model_name)
            vectors: List[List[float]] = []
            for i in range(0, len(batch), cfg.batch_size):
                chunk = [x[: cfg.max_input_chars] if cfg.max_input_chars else x for x in batch[i:i + cfg.batch_size]]
                logger.info("Embedding batch %s-%s/%s", i + 1, i + len(chunk), len(batch))
                vectors.extend(encoder.encode(chunk, normalize_embeddings=cfg.normalize_embeddings, show_progress_bar=False).tolist())
            return _normalize_vectors(vectors)
        except Exception as exc:
            if not cfg.debug_fallback:
                raise EmbeddingError(f"本地 Embedding 失败: {exc}") from exc
            logger.warning("本地 Embedding 失败，启用 debug hash fallback: %s", exc)

    if provider == "hash" or cfg.debug_fallback:
        return [_hash_embedding(text) for text in batch]
    raise EmbeddingError(f"未知或不可用 Embedding provider: {provider}")


@lru_cache(maxsize=4)
def _get_sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _embed_openai_compatible(batch: Sequence[str], api_key: str, base_url: Optional[str], model: str, cfg: EmbeddingConfig) -> List[List[float]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise EmbeddingError("缺少 openai：pip install openai") from exc
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    last_error: Optional[Exception] = None
    for attempt in range(cfg.retries + 1):
        try:
            response = client.embeddings.create(model=model, input=list(batch))
            return _normalize_vectors([item.embedding for item in response.data])
        except Exception as exc:
            last_error = exc
            if attempt < cfg.retries:
                time.sleep(cfg.retry_seconds)
    raise EmbeddingError(f"在线 Embedding 调用失败: {last_error}")


def _collection_name(course_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(course_id or "course")).strip("_")
    if len(safe) < 3:
        safe = f"course_{safe}"
    return safe[:60]


def create_or_load_collection(course_id: str, persist_dir: Optional[str] = None):
    """创建或加载 Chroma collection，按课程隔离。"""
    try:
        import chromadb
    except ImportError as exc:
        raise VectorStoreError("缺少 chromadb：pip install chromadb") from exc

    path = persist_dir or DEFAULT_VECTOR_DIR
    os.makedirs(path, exist_ok=True)
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection(
        name=_collection_name(course_id),
        metadata={"hnsw:space": "cosine", "course_id": str(course_id)},
    )


def load_collection(course_id: str, persist_dir: Optional[str] = None):
    """只加载已有 Chroma collection；不存在时抛错，不产生空集合副作用。"""
    try:
        import chromadb
    except ImportError as exc:
        raise VectorStoreError("缺少 chromadb：pip install chromadb") from exc

    path = persist_dir or DEFAULT_VECTOR_DIR
    client = chromadb.PersistentClient(path=path)
    return client.get_collection(name=_collection_name(course_id))


def _sanitize_metadata(fragment: Dict) -> Dict:
    allowed = (str, int, float, bool)
    meta: Dict = {}
    for key, value in fragment.items():
        if key in {"text", "embedding", "embedding_json"} or value is None:
            continue
        if isinstance(value, allowed):
            meta[key] = value
        elif isinstance(value, (list, tuple, dict)):
            meta[key] = json.dumps(value, ensure_ascii=False)
        else:
            meta[key] = str(value)
    return meta


def index_fragments(
    course_id: str,
    fragments: Sequence[Dict],
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
    provider: Optional[str] = None,
    embedding_config: Optional[EmbeddingConfig] = None,
) -> int:
    """将分块文本转为向量并入库。"""
    valid = [dict(f) for f in fragments if f.get("chunk_id") and f.get("text")]
    if not valid:
        return 0

    texts = [f["text"] for f in valid]
    embeddings = get_embedding(texts, provider=provider, config=embedding_config)
    embeddings_by_id = {f["chunk_id"]: embeddings[i] for i, f in enumerate(valid)}
    CourseDB(db_path).update_fragment_embeddings(embeddings_by_id)

    try:
        collection = create_or_load_collection(course_id, persist_dir)
        collection.upsert(
            ids=[f["chunk_id"] for f in valid],
            documents=texts,
            embeddings=embeddings,
            metadatas=[_sanitize_metadata(f) for f in valid],
        )
    except Exception as exc:
        # SQLite 中已经保存了 embedding，检索仍可用；Chroma 错误留给报告展示。
        raise VectorStoreError(f"Chroma 入库失败: {exc}") from exc
    return len(valid)


def save_fragments_to_vector_store(
    fragments: Sequence[Dict],
    *,
    course_id: Optional[str] = None,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
    provider: Optional[str] = None,
    embedding_config: Optional[EmbeddingConfig] = None,
) -> int:
    """保存向量到 Chroma。"""
    cid = course_id or (fragments[0].get("course_id") if fragments else None)
    if not cid:
        raise VectorStoreError("缺少 course_id，无法创建课程向量集合")
    return index_fragments(cid, fragments, db_path=db_path, persist_dir=persist_dir, provider=provider, embedding_config=embedding_config)


def delete_document_vectors(
    document_id: str,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
) -> None:
    """删除某个文档相关向量。"""
    db = CourseDB(db_path)
    doc = db.get_document(document_id)
    if not doc:
        return
    try:
        collection = load_collection(doc["course_id"], persist_dir)
        collection.delete(where={"document_id": document_id})
    except Exception as exc:
        logger.debug("删除 Chroma 文档向量失败或集合不存在: %s", exc)


def rebuild_course_index(
    course_id: str,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
    provider: Optional[str] = None,
    embedding_config: Optional[EmbeddingConfig] = None,
) -> int:
    """重新构建课程索引。"""
    db = CourseDB(db_path)
    fragments = db.get_fragments(course_id=course_id)
    if not fragments:
        return 0

    try:
        import chromadb

        path = persist_dir or DEFAULT_VECTOR_DIR
        client = chromadb.PersistentClient(path=path)
        try:
            client.delete_collection(_collection_name(course_id))
        except Exception as exc:
            logger.debug("删除旧 collection 失败或不存在: %s", exc)
    except Exception as exc:
        logger.debug("重建索引前清理 Chroma 失败: %s", exc)
    return index_fragments(course_id, fragments, db_path=db_path, persist_dir=persist_dir, provider=provider, embedding_config=embedding_config)


__all__ = [
    "get_embedding",
    "create_or_load_collection",
    "load_collection",
    "index_fragments",
    "save_fragments_to_vector_store",
    "delete_document_vectors",
    "rebuild_course_index",
    "DEFAULT_VECTOR_DIR",
]
