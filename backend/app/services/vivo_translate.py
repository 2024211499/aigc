# -*- coding: utf-8 -*-
"""vivo 同声传译服务（WebSocket，实时语音翻译）"""

import json
import logging
import os
import time
import uuid
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VivoSimultaneousInterpreter:
    """vivo 同声传译客户端。

    支持中→英、英→中、日→中、韩→中 实时语音翻译。
    与实时 ASR 类似，但开启翻译开关 (tc=1)。

    使用方式：
        interpreter = VivoSimultaneousInterpreter()
        interpreter.translate(audio_data, target_lang="en_cn",
            on_result=lambda text: print(text))
    """

    WS_URL = "ws://api-ai.vivo.com.cn/asr/v2"

    def __init__(
        self,
        app_key: Optional[str] = None,
        engineid: str = "longasrsubtitle",
        timeout: int = 60,
    ):
        self._app_key = app_key or os.getenv("VIVO_OCR_APP_KEY", "")
        self._engineid = engineid
        self._timeout = timeout
        if not self._app_key:
            raise ValueError("vivo 同声传译需要设置 VIVO_OCR_APP_KEY")

    def translate(
        self,
        audio_data: bytes,
        target_lang: str = "en_cn",
        source_lang: str = "cn",
        sample_rate: int = 16000,
        on_result: Optional[Callable[[str], None]] = None,
    ) -> str:
        """翻译一段音频。

        Args:
            audio_data: PCM 音频数据（16kHz, 16bit, 单声道）。
            target_lang: 目标翻译语言，如 en_cn（英译中）、ja_cn（日译中）。
            source_lang: 源语言，cn/en/ja/ko。
            sample_rate: 采样率，默认 16000。
            on_result: 中间结果回调。

        Returns:
            完整翻译文本。
        """
        from websocket import create_connection, ABNF

        request_id = str(uuid.uuid4()).replace("-", "")
        system_time = str(int(time.time() * 1000))
        user_id = "user_" + request_id[:16]

        params = {
            "user_id": user_id,
            "product": "unknown",
            "package": "unknown",
            "client_version": "1.0.0",
            "system_version": "unknown",
            "sdk_version": "1.0.0",
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
            raise RuntimeError(f"同声传译连接失败: {e}") from e

        try:
            # 1. 读握手
            code, data = ws.recv_data(True)
            handshake = json.loads(data) if code == ABNF.OPCODE_TEXT else {}
            if handshake.get("code") != 0:
                raise RuntimeError(f"同声传译握手失败: {handshake.get('desc', 'unknown')}")

            # 2. 发送 started 配置（开启翻译）
            start_msg = {
                "type": "started",
                "request_id": request_id,
                "asr_info": {
                    "audio_type": "pcm",
                    "lang": source_lang,
                    "target_lang": target_lang,
                    "punctuation": 1,
                    "eng_pgsnum": 40,
                    "end_vad_time": 1440,
                    "tc": 1,  # 开启同声传译
                },
                "tts_info": {
                    "selftts": 0,
                    "speed": 50,
                    "volume": 50,
                },
            }
            ws.send(json.dumps(start_msg))

            # 3. 发送音频数据
            frame_size = sample_rate * 2 * 40 // 1000  # 40ms
            for i in range(0, len(audio_data), frame_size):
                chunk = audio_data[i : i + frame_size]
                ws.send(chunk, ABNF.OPCODE_BINARY)

            # 4. 发送结束
            ws.send(b"--end--", ABNF.OPCODE_BINARY)

            # 5. 接收结果
            full_text = ""
            while True:
                code, data = ws.recv_data(True)
                if code == ABNF.OPCODE_CLOSE:
                    break
                elif code == ABNF.OPCODE_TEXT:
                    msg = json.loads(data)
                    if msg.get("action") == "result":
                        c = msg.get("code")
                        row = msg.get("data", {})
                        if c == 0:  # 完整结果
                            text = row.get("onebest", "")
                            if text:
                                full_text += text + "\n"
                                if on_result:
                                    on_result(text)
                        elif c == 8:  # 中间 var 结果
                            text = row.get("var", "")
                            if on_result:
                                on_result(f"[中间] {text}")
                        elif c == 9:  # 最后一句
                            text = row.get("onebest", "")
                            if text:
                                full_text += text
                                if on_result:
                                    on_result(text)
                            break
            return full_text.strip()
        except Exception as e:
            raise RuntimeError(f"同声传译失败: {e}") from e
        finally:
            ws.close()
