# -*- coding: utf-8 -*-
"""vivo 实时短语音识别服务（WebSocket，60s 内音频）"""

import base64
import json
import logging
import os
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class VivoShortASR:
    """vivo 实时短语音识别客户端。

    使用方式：
        asr = VivoShortASR()
        text = asr.transcribe(pcm_audio_data)  # PCM 16kHz 16bit mono
    """

    WS_URL = "ws://api-ai.vivo.com.cn/asr/v2"

    def __init__(
        self,
        app_key: Optional[str] = None,
        engineid: str = "shortasrinput",
        timeout: int = 30,
    ):
        self._app_key = app_key or os.getenv("VIVO_OCR_APP_KEY", "")
        self._engineid = engineid
        self._timeout = timeout
        if not self._app_key:
            raise ValueError("vivo ASR 需要设置 VIVO_OCR_APP_KEY")

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """识别一段 PCM 音频，返回识别文本。

        Args:
            audio_data: PCM 音频数据（16kHz, 16bit, 单声道）
            sample_rate: 采样率，默认 16000

        Returns:
            识别结果文本
        """
        from websocket import create_connection, ABNF

        request_id = str(uuid.uuid4()).replace("-", "")
        system_time = str(int(time.time() * 1000))
        user_id = "user_" + request_id[:16]

        params = {
            "model": "unknown",
            "system_version": "unknown",
            "client_version": "1.0.0",
            "package": "unknown",
            "sdk_version": "1.0.0",
            "user_id": user_id,
            "android_version": "unknown",
            "system_time": system_time,
            "net_type": "1",
            "engineid": self._engineid,
            "requestId": request_id,
        }
        param_str = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        url = self.WS_URL + param_str

        headers = {
            "Authorization": f"Bearer {self._app_key}",
            "X-AI-GATEWAY-SIGNATURE": "developers-aigc",
        }

        try:
            ws = create_connection(url, header=headers, timeout=self._timeout)
        except Exception as e:
            raise RuntimeError(f"vivo ASR 连接失败: {e}") from e

        try:
            # 1. 读握手
            code, data = ws.recv_data(True)
            handshake = json.loads(data) if code == ABNF.OPCODE_TEXT else {}
            if handshake.get("code") != 0:
                raise RuntimeError(f"vivo ASR 握手失败: {handshake.get('desc', 'unknown')}")

            # 2. 发送 started 配置
            start_msg = {
                "type": "started",
                "request_id": request_id,
                "asr_info": {
                    "end_vad_time": 1000,
                    "audio_type": "pcm",
                    "chinese2digital": 1,
                    "punctuation": 1,
                },
            }
            ws.send(json.dumps(start_msg))

            # 3. 发送音频数据（分帧，每帧 40ms = 640 bytes @ 16kHz 16bit）
            frame_size = sample_rate * 2 * 40 // 1000  # 40ms frames
            for i in range(0, len(audio_data), frame_size):
                chunk = audio_data[i : i + frame_size]
                ws.send(chunk, ABNF.OPCODE_BINARY)

            # 4. 发送结束标志
            ws.send(b"--end--", ABNF.OPCODE_BINARY)

            # 5. 接收结果
            result_text = ""
            while True:
                code, data = ws.recv_data(True)
                if code == ABNF.OPCODE_CLOSE:
                    break
                elif code == ABNF.OPCODE_TEXT:
                    msg = json.loads(data)
                    if msg.get("action") == "result" and msg.get("code") == 0:
                        result_text = msg.get("data", {}).get("text", "")
                    elif msg.get("action") == "error":
                        logger.warning("ASR 识别错误: %s", msg.get("desc"))
                        break
            return result_text.strip()
        except Exception as e:
            raise RuntimeError(f"vivo ASR 识别失败: {e}") from e
        finally:
            ws.close()
