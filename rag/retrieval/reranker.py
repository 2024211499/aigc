"""Optional reranker adapters."""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)

_reranker = None
_cross_encoder = None


def rerank(query: str, results, top_k: int):
    if not results:
        return []

    global _reranker, _cross_encoder
    try:
        if _cross_encoder is None:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("BAAI/bge-reranker-base")
        scores = _cross_encoder.predict([[query, r.text if hasattr(r, "text") else r.get("text", "")] for r in results])
        for r, s in zip(results, scores):
            target = r.metadata if hasattr(r, "metadata") else r
            target["rerank_score"] = float(s)
        return [r for _, r in sorted(zip(scores, results), key=lambda x: x[0], reverse=True)][:top_k]
    except Exception:
        logger.debug("CrossEncoder reranker 不可用，尝试 FlagEmbedding", exc_info=True)

    if _reranker is None:
        try:
            from FlagEmbedding import FlagReranker
            _reranker = FlagReranker("BAAI/bge-reranker-base", use_fp16=True)
        except ImportError:
            logger.info("未安装可选 reranker，使用轻量规则排序")
            return results[:top_k]

    pairs = [[query, r.text if hasattr(r, "text") else r.get("text", "")] for r in results]
    scores = _reranker.compute_score(pairs)
    for r, s in zip(results, scores):
        try:
            target = r.metadata if hasattr(r, "metadata") else r
            target["rerank_score"] = float(s)
        except Exception:
            logger.debug("写入 rerank_score 失败", exc_info=True)
    return [r for _, r in sorted(zip(scores, results), key=lambda x: x[0], reverse=True)][:top_k]
