# -*- coding: utf-8 -*-
"""文本相似度服务（基于现有 Embedding 做余弦相似度）"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算两个向量的余弦相似度。"""
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = sum(x * x for x in a[:n]) ** 0.5 or 1.0
    nb = sum(x * x for x in b[:n]) ** 0.5 or 1.0
    return dot / (na * nb)


def compute_similarity(text_a: str, text_b: str) -> float:
    """计算两段文本的语义相似度（0~1）。"""
    from rag.retrieval.embeddings import EmbeddingProvider
    try:
        emb = EmbeddingProvider(provider="siliconflow", model_name="BAAI/bge-m3")
        vectors = emb.embed_documents([text_a, text_b])
        return cosine_similarity(vectors[0], vectors[1])
    except Exception:
        # 回退：用 SiliconFlow embedding
        try:
            emb = EmbeddingProvider(provider="local", model_name="BAAI/bge-small-zh-v1.5")
            vectors = emb.embed_documents([text_a, text_b])
            return cosine_similarity(vectors[0], vectors[1])
        except Exception as e:
            logger.error("文本相似度计算失败: %s", e)
            return 0.0


def rank_similarities(query: str, candidates: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
    """对候选列表按与 query 的相似度排序。"""
    from rag.retrieval.embeddings import EmbeddingProvider
    try:
        emb = EmbeddingProvider(provider="siliconflow", model_name="BAAI/bge-m3")
        query_vec = emb.embed_query(query)
        candidate_vecs = emb.embed_documents(candidates)
        scored = [(candidates[i], cosine_similarity(query_vec, candidate_vecs[i])) for i in range(len(candidates))]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    except Exception as e:
        logger.error("排序失败: %s", e)
        return [(c, 0.0) for c in candidates[:top_k]]
