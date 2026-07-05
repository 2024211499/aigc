# -*- coding: utf-8 -*-
"""vivo 长语音转写服务（HTTP，录音文件转写，最长 5 小时 / 500MB）"""

import json
import logging
import math
import os
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE = 5 * 1024 * 1024  # 5MB
POLL_INTERVAL = 5  # seconds


class VivoLongASR:
    """vivo 长语音转写客户端。

    使用方式：
        asr = VivoLongASR()
        result = asr.transcribe_file("lecture.wav")
    """

    BASE_URL = "http://api-ai.vivo.com.cn"
    ENGINE_ID = "fileasrrecorder"

    def __init__(self, app_key: Optional[str] = None):
        self._app_key = app_key or os.getenv("VIVO_OCR_APP_KEY", "")
        if not self._app_key:
            raise ValueError("vivo 长语音转写需要设置 VIVO_OCR_APP_KEY")

    def transcribe_file(
        self,
        file_path: str,
        audio_type: str = "auto",
        poll_interval: int = POLL_INTERVAL,
    ) -> str:
        """转写一个录音文件。

        Args:
            file_path: 音频文件路径（wav/pcm/m4a/mp3/aac/ogg/ogg_opus）
            audio_type: 音频类型，pcm 传 pcm，其他格式传 auto
            poll_interval: 轮询间隔（秒）

        Returns:
            转写结果文本
        """
        import requests

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {file_path}")

        session_id = str(uuid.uuid4())
        user_id = "user_" + uuid.uuid4().hex[:16]
        file_size = file_path.stat().st_size
        slice_num = max(1, math.ceil(file_size / CHUNK_SIZE))

        common_params = {
            "client_version": "1.0.0",
            "package": "unknown",
            "user_id": user_id,
            "system_time": str(int(time.time() * 1000)),
            "engineid": self.ENGINE_ID,
            "requestId": str(uuid.uuid4()),
        }
        headers = {
            "Authorization": f"Bearer {self._app_key}",
        }

        def _mkurl(path: str) -> str:
            return self.BASE_URL + path + "?" + "&".join(f"{k}={v}" for k, v in common_params.items())

        # ── 1. 创建音频 ──
        logger.info("创建音频任务...")
        resp = requests.post(
            _mkurl("/lasr/create"),
            json={"audio_type": audio_type, "x-sessionId": session_id, "slice_num": slice_num},
            headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        body = resp.json()
        if body.get("code") != 0:
            raise RuntimeError(f"创建音频失败: {body.get('desc', 'unknown')}")
        audio_id = body["data"]["audio_id"]
        logger.info("音频创建成功: audio_id=%s", audio_id)

        # ── 2. 文件分片上传 ──
        logger.info("上传音频文件（共 %d 分片）...", slice_num)
        with open(file_path, "rb") as f:
            for idx in range(slice_num):
                chunk = f.read(CHUNK_SIZE)
                params = dict(common_params)
                params.update({
                    "audio_id": audio_id,
                    "x-sessionId": session_id,
                    "slice_index": str(idx),
                })
                upload_url = self.BASE_URL + "/lasr/upload?" + "&".join(f"{k}={v}" for k, v in params.items())
                resp2 = requests.post(
                    upload_url,
                    files={"file": (f"chunk_{idx}", chunk)},
                    headers=headers,
                    timeout=60,
                )
                body2 = resp2.json()
                if body2.get("code") != 0:
                    raise RuntimeError(f"分片 {idx} 上传失败: {body2.get('desc', 'unknown')}")
                logger.info("  分片 %d/%d 上传成功", idx + 1, slice_num)

        # ── 3. 创建转写任务 ──
        logger.info("创建转写任务...")
        resp3 = requests.post(
            _mkurl("/lasr/run"),
            json={"audio_id": audio_id, "x-sessionId": session_id},
            headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        body3 = resp3.json()
        if body3.get("code") != 0:
            raise RuntimeError(f"创建转写任务失败: {body3.get('desc', 'unknown')}")
        task_id = body3["data"]["task_id"]
        logger.info("转写任务创建成功: task_id=%s", task_id)

        # ── 4. 轮询进度 ──
        logger.info("等待转写完成...")
        while True:
            time.sleep(poll_interval)
            resp4 = requests.post(
                _mkurl("/lasr/progress"),
                json={"task_id": task_id, "x-sessionId": session_id},
                headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
                timeout=10,
            )
            body4 = resp4.json()
            if body4.get("code") != 0:
                raise RuntimeError(f"查询进度失败: {body4.get('desc', 'unknown')}")
            progress = body4["data"]["progress"]
            logger.info("  转写进度: %d%%", progress)
            if progress >= 100:
                break

        # ── 5. 获取结果 ──
        logger.info("获取转写结果...")
        resp5 = requests.post(
            _mkurl("/lasr/result"),
            json={"task_id": task_id, "x-sessionId": session_id},
            headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        body5 = resp5.json()
        if body5.get("code") != 0:
            raise RuntimeError(f"获取结果失败: {body5.get('desc', 'unknown')}")

        segments = body5.get("data", {}).get("result", [])
        texts = [s.get("onebest", "") for s in segments if isinstance(s, dict)]
        return "\n".join(texts)
