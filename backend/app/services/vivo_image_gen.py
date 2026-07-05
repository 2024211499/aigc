# -*- coding: utf-8 -*-
"""vivo 图片生成服务（Doubao Seedream）"""

import json
import logging
import os
import time
import uuid
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api-ai.vivo.com.cn/api/v1/image_generation"

MODELS = ["Doubao-Seedream-4.5", "Doubao-Seedream-5.0-lite"]


class VivoImageGen:
    """vivo 图片生成客户端。

    支持文生图、图生图，每日限制 50 次，总计 500 次。
    """

    def __init__(self, app_key: Optional[str] = None):
        self._app_key = app_key or os.getenv("VIVO_OCR_APP_KEY", "")
        if not self._app_key:
            raise ValueError("vivo 图片生成需要设置 VIVO_OCR_APP_KEY")

    def generate(
        self,
        prompt: str,
        model: str = "Doubao-Seedream-5.0-lite",
        image: Optional[str] = None,
        size: str = "1024x1024",
        num_images: int = 1,
    ) -> List[str]:
        """生成图片。

        Args:
            prompt: 文本描述。
            model: 模型名称，默认 Doubao-Seedream-5.0-lite。
            image: 参考图片 URL 或 base64（图生图时使用）。
            size: 分辨率，如 1024x1024, 2K。
            num_images: 生成图片数量（组图模式）。

        Returns:
            生成图片的 URL 列表。
        """
        if model not in MODELS:
            logger.warning("未知模型 %s，使用默认 Doubao-Seedream-5.0-lite", model)
            model = "Doubao-Seedream-5.0-lite"

        body = {
            "model": model,
            "prompt": prompt,
        }

        if image:
            body["image"] = image
            body["parameters"] = {
                "size": size,
                "watermark": False,
            }
        else:
            body["parameters"] = {
                "size": size,
                "prompt_extend": True,
            }

        # 组图模式
        if num_images > 1:
            body["parameters"]["sequential_image_generation"] = "auto"

        params = {
            "module": "aigc",
            "request_id": str(uuid.uuid4()),
            "system_time": str(int(time.time())),
        }
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
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"图片生成失败: {data.get('message', 'unknown')}")

            images = data.get("data", {}).get("images", [])
            urls = [img["url"] for img in images if isinstance(img, dict) and img.get("url")]
            return urls
        except Exception as e:
            logger.error("图片生成异常: %s", e, exc_info=True)
            raise
