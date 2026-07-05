"""Embedding 提供者：支持本地 sentence-transformers / OpenAI / ModelScope GTE。"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from ..config import EmbeddingConfig
from ..exceptions import ConfigurationError, EmbeddingError

logger = logging.getLogger(__name__)


def file_md5(path: str) -> str:
    """计算文件 MD5，用于增量索引。"""
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_cache_name(*parts: str) -> str:
    raw = "_".join(parts)
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)[:180] + ".pkl"


class EmbeddingProvider:
    """统一 Embedding 提供者。"""

    def __init__(
        self,
        provider: str = "local",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        cache_dir: str = "./embedding_cache",
        config: Optional[EmbeddingConfig] = None,
    ):
        cfg = config or EmbeddingConfig(provider=provider, model_name=model_name or EmbeddingConfig.model_name, cache_dir=cache_dir)
        self.config = cfg
        self.provider = (provider or cfg.provider).lower()
        self.model_name = model_name or cfg.model_name
        # Embedding key: 优先用 EMBEDDING_API_KEY，再回退 api_key_env
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv(cfg.api_key_env)
        # Embedding API base: 优先用 EMBEDDING_API_BASE，没有则用 openai 兼容的默认值
        self.api_base = os.getenv(cfg.api_base_env, "")
        self.cache_dir = Path(cfg.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._func = self._build_func()

    def _build_func(self) -> Callable[[Sequence[str]], List[List[float]]]:
        if self.provider == "local":
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingError("缺少 sentence-transformers：pip install sentence-transformers") from exc

            model = _cached_sentence_transformer(self.model_name)
            return lambda texts: model.encode(
                list(texts),
                normalize_embeddings=self.config.normalize_embeddings,
                show_progress_bar=False,
            ).tolist()

        if self.provider in ("openai", "siliconflow"):
            if not self.api_key:
                raise ConfigurationError(f"Embedding 需要 API key：{self.config.api_key_env} 或 EMBEDDING_API_KEY")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise EmbeddingError("缺少 openai：pip install openai") from exc

            client_kwargs = {"api_key": self.api_key}
            if self.api_base:
                client_kwargs["base_url"] = self.api_base

            client = OpenAI(**client_kwargs)

            def embed_openai(texts: Sequence[str]) -> List[List[float]]:
                resp = client.embeddings.create(model=self.model_name, input=list(texts))
                return [item.embedding for item in resp.data]

            return embed_openai

        if self.provider == "gte":
            try:
                from modelscope.pipelines import pipeline
            except ImportError as exc:
                raise EmbeddingError("缺少 modelscope：pip install modelscope") from exc

            nlp = pipeline("feature-extraction", model=self.model_name or "damo/nlp_gte_base_zh")
            return lambda texts: [list(map(float, v)) for v in nlp(list(texts))]

        raise ConfigurationError(f"未知 Embedding provider: {self.provider}")

    def _max_input_chars(self) -> int:
        if self.config.max_input_chars:
            return self.config.max_input_chars
        if self.provider in ("openai", "siliconflow"):
            return 8000
        if self.provider == "gte":
            return 512
        return 512

    def embed_documents(
        self,
        texts: Sequence[str],
        doc_identifier: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> List[List[float]]:
        texts = [str(t or "") for t in texts]
        if not texts:
            return []

        max_len = self._max_input_chars()
        truncated = [t[:max_len] for t in texts]
        batch_size = batch_size or self.config.batch_size

        cache_file = None
        if doc_identifier:
            cache_file = self.cache_dir / _safe_cache_name(doc_identifier, self.provider, self.model_name)
            if cache_file.exists():
                try:
                    with cache_file.open("rb") as f:
                        cached = pickle.load(f)
                    if len(cached) == len(texts):
                        logger.info("加载 Embedding 缓存: %s", cache_file)
                        return cached
                except Exception:
                    logger.warning("Embedding 缓存损坏，将重新生成: %s", cache_file)

        vectors: List[List[float]] = []
        for i in range(0, len(truncated), batch_size):
            batch = truncated[i:i + batch_size]
            last_error = None
            for attempt in range(self.config.retries + 1):
                try:
                    vectors.extend(self._func(batch))
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < self.config.retries:
                        time.sleep(self.config.retry_seconds)
            if last_error is not None:
                raise EmbeddingError(f"Embedding 失败: {last_error}") from last_error

        if cache_file:
            with cache_file.open("wb") as f:
                pickle.dump(vectors, f)

        return vectors

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


class ChromaEmbeddingAdapter:
    """适配 ChromaDB embedding_function 协议。"""

    def __init__(self, provider: EmbeddingProvider):
        self.provider = provider

    def __call__(self, input):  # Chroma 形参名要求为 input
        return self.provider.embed_documents(list(input))


@lru_cache(maxsize=4)
def _cached_sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)
