# -*- coding: utf-8 -*-
"""多模态 LLM 封装（OpenAI 通用格式，支持 base64 图片）

支持的模型（只要兼容 OpenAI Vision API 且支持 data URI base64）：
- Qwen-VL (阿里)        — 推荐，中文好，便宜
- Step-1V (阶跃星辰)     — 免费额度大
- GPT-4o-mini (OpenAI)  — 最强但需境外支付
- GLM-4V-Flash (智谱)   — 不支持 base64，需要公网 URL，不推荐

使用方式：
    client = MultimodalClient()
    result = client.understand_image(image_bytes, "图中有什么？")
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# 默认走 Qwen-VL（阿里云百炼），如需切换改这里和 .env
DEFAULT_MODEL = "qwen-vl-plus"  # 或 qwen-vl-max
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class MultimodalClient:
    """多模态 LLM 客户端，支持 base64 图片输入。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("MULTIMODAL_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.base_url = base_url or os.getenv("MULTIMODAL_API_BASE", DEFAULT_BASE_URL)
        self.model = model or os.getenv("MULTIMODAL_MODEL", DEFAULT_MODEL)

        if not self.api_key:
            raise ValueError("多模态 API Key 未配置（设置 MULTIMODAL_API_KEY）")

        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _guess_mime(self, image_data: bytes) -> str:
        if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_data.startswith(b"\xff\xd8"):
            return "image/jpeg"
        if image_data.startswith(b"RIFF") and b"WEBP" in image_data[:16]:
            return "image/webp"
        return "image/jpeg"

    def understand_image(
        self,
        image_data: bytes,
        question: str = "请描述这张图片中的内容",
        system_prompt: str = "你是一个教学辅助 AI，擅长理解教材、笔记、试卷、习题图片中的内容。",
    ) -> str:
        """传入图片字节 + 问题，返回 LLM 的回答。"""
        encoded = base64.b64encode(image_data).decode("utf-8")
        data_uri = f"data:{self._guess_mime(image_data)};base64,{encoded}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": question},
                ],
            },
        ]

        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("多模态 LLM 调用失败: %s", e, exc_info=True)
            raise

    def analyze_homework_image(
        self,
        image_data: bytes,
        question: str = "",
        student_answer: str = "",
        mode: str = "step_by_step",
    ) -> str:
        """针对作业/习题图片的分析。"""
        prompt = f"""这是一道学习题目。请根据图片内容回答。

用户问题：{question or "请解答图片中的题目"}
学生答案：{student_answer or "未提供"}
辅导模式：{mode}

请根据图片中的题目内容进行辅导。如果图片包含图形（受力图、几何图、电路图等），请一并分析。
"""
        return self.understand_image(image_data, prompt)

    def extract_text_from_image(self, image_data: bytes) -> str:
        """提取图片中的文字内容（比纯 OCR 更强的理解）。"""
        return self.understand_image(
            image_data,
            "请提取这张图片中的所有文字内容，包括公式、标题、正文。保留原有的排版结构。",
        )
