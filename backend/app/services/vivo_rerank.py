# -*- coding: utf-8 -*-
"""vivo Rerank 文本相似度服务（替换余弦相似度方案）"""

import json
import logging
import os
import uuid
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api-ai.vivo.com.cn/rerank"


class VivoReranker:
    """vivo Rerank 文本相似度客户端。

    使用 bge-reranker-large 模型计算 query 与候选项的语义相似度。
    """

    def __init__(self, app_key: Optional[str] = None):
        self._app_key = app_key or os.getenv("VIVO_OCR_APP_KEY", "")
        if not self._app_key:
            raise ValueError("vivo Rerank 需要设置 VIVO_OCR_APP_KEY")

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """计算两段文本的语义相似度（0~1）。

        内部通过 rerank 接口：用 text_a 作为 query 对 [text_b] 排序。
        """
        # 截断到 500 字以内
        query = text_a[:300]
        sentence = text_b[:300]

        result = self.rerank(query, [sentence])
        if result:
            return max(0.0, min(1.0, (result[0][1] + 10) / 20))  # 归一化到 0~1
        return 0.0

    def rerank(
        self,
        query: str,
        sentences: List[str],
    ) -> List[Tuple[str, float]]:
        """对候选项按与 query 的相关性排序。

        Args:
            query: 查询文本。
            sentences: 候选项列表。

        Returns:
            [(sentence, score), ...]，按分数降序排列。
        """
        # 截断
        query = query[:300]
        sentences = [s[:300] for s in sentences]

        body = {
            "model_name": "bge-reranker-large",
            "query": query,
            "sentences": sentences,
        }
        params = {"requestId": str(uuid.uuid4())}
        headers = {
            "Authorization": f"Bearer {self._app_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                API_URL,
                json=body,
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            scores = data.get("data", [])
            if not scores or len(scores) != len(sentences):
                return [(s, 0.0) for s in sentences]

            scored = list(zip(sentences, scores))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored
        except Exception as e:
            logger.error("Rerank 失败: %s", e)
            return [(s, 0.0) for s in sentences]
