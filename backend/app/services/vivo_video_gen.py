# -*- coding: utf-8 -*-
"""vivo 视频生成服务（Doubao Seedance，异步提交+轮询）"""

import logging
import os
import time
import uuid
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SUBMIT_URL = "https://api-ai.vivo.com.cn/api/v1/submit_task"
QUERY_URL = "https://api-ai.vivo.com.cn/api/v1/query_task"
POLL_INTERVAL = 10  # 轮询间隔（秒）
MAX_POLL_TIME = 600  # 最长等待 10 分钟


class VivoVideoGen:
    """vivo 视频生成客户端。

    支持文生视频、图生视频（首帧/首尾帧）。
    每日限制 10 次，总计 200 个视频。
    """

    def __init__(self, app_key: Optional[str] = None):
        self._app_key = app_key or os.getenv("VIVO_OCR_APP_KEY", "")
        if not self._app_key:
            raise ValueError("vivo 视频生成需要设置 VIVO_OCR_APP_KEY")

    def generate(
        self,
        prompt: str,
        model: str = "Doubao-Seedance-2.0-fast",
        image_url: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        ratio: str = "16:9",
        duration: int = 5,
        poll: bool = True,
    ) -> dict:
        """生成视频。

        Args:
            prompt: 文本描述（含动作、运镜等）。
            model: 模型名，默认 Doubao-Seedance-2.0-fast（最快）。
            image_url: 参考图片 URL（图生视频首帧）。
            last_frame_url: 尾帧图片 URL（首尾帧控制）。
            ratio: 画面比例，如 16:9, 9:16, adaptive。
            duration: 视频时长（秒），默认 5。
            poll: 是否等待完成，默认 True。

        Returns:
            {"task_id": "", "video_url": "", "status": ""}
        """
        # 构建 content
        content = []
        text_prompt = prompt.strip()
        if ratio:
            text_prompt += f"  --ratio {ratio}"
        if duration:
            text_prompt += f"  --dur {duration}"
        content.append({"type": "text", "text": text_prompt})

        if image_url:
            item = {"type": "image_url", "image_url": {"url": image_url}}
            if last_frame_url:
                item["role"] = "first_frame"
                content.append(item)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": last_frame_url},
                    "role": "last_frame",
                })
            else:
                content.append(item)

        # 提交任务
        params = {
            "request_id": str(uuid.uuid4()),
            "system_time": str(int(time.time())),
            "module": "aigc",
        }
        body = {"model": model, "content": content}
        headers = {
            "Authorization": f"Bearer {self._app_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(SUBMIT_URL, json=body, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"视频任务提交失败: {data.get('message', 'unknown')}")
            task_id = data["data"]["id"]
            logger.info("视频任务提交成功: %s", task_id)
        except Exception as e:
            raise RuntimeError(f"视频任务提交异常: {e}") from e

        if not poll:
            return {"task_id": task_id, "video_url": None, "status": "pending"}

        # 轮询
        start = time.time()
        while time.time() - start < MAX_POLL_TIME:
            time.sleep(POLL_INTERVAL)
            status = self.query_task(task_id)
            if status.get("status") == "succeeded":
                return status
            logger.info("视频生成中... status=%s", status.get("status"))

        return {"task_id": task_id, "video_url": None, "status": "timeout"}

    def query_task(self, task_id: str) -> dict:
        """查询视频生成任务状态。"""
        params = {
            "task_id": task_id,
            "request_id": str(uuid.uuid4()),
            "system_time": str(int(time.time())),
            "module": "aigc",
        }
        headers = {
            "Authorization": f"Bearer {self._app_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.get(QUERY_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"查询任务失败: {data.get('message', 'unknown')}")

            result = data.get("data", {})
            content = result.get("content", {}) or {}
            return {
                "task_id": result.get("id", task_id),
                "status": result.get("status", "unknown"),
                "video_url": content.get("video_url"),
                "last_frame_url": content.get("last_frame_url"),
                "duration": result.get("duration"),
                "resolution": result.get("resolution"),
                "seed": result.get("seed"),
            }
        except Exception as e:
            logger.error("查询视频任务失败: %s", e)
            return {"task_id": task_id, "status": "error", "error": str(e)}
