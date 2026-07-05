# -*- coding: utf-8 -*-
"""vivo TTS 语音合成服务（WebSocket 流式）"""

import base64
import io
import json
import logging
import os
import time
import uuid
import wave
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VivoTTS:
    """vivo 语音合成客户端。

    使用方式：
        tts = VivoTTS(app_id="xxx", app_key="xxx")
        wav_bytes = tts.synthesize("你好呀", vcn="x2_F25")
    """

    WS_URL = "wss://api-ai.vivo.com.cn/tts"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_key: Optional[str] = None,
        engineid: str = "long_audio_synthesis_screen",
        timeout: int = 30,
    ):
        self._app_id = app_id or os.getenv("VIVO_OCR_APP_ID", "")
        self._app_key = app_key or os.getenv("VIVO_OCR_APP_KEY", "")
        self._engineid = engineid
        self._timeout = timeout

        if not self._app_id or not self._app_key:
            raise ValueError("vivo TTS 需要设置 APP_ID 和 APP_KEY")

    def synthesize(self, text: str, vcn: str = "x2_F25") -> bytes:
        """合成文本为音频，返回 WAV 格式的 PCM 数据。"""
        from websocket import create_connection, ABNF

        # ── 1. 构建 WebSocket URL ──
        system_time = str(int(time.time()))
        request_id = str(uuid.uuid4())
        params = {
            "engineid": self._engineid,
            "system_time": system_time,
            "user_id": "user_default",
            "model": "unknown",
            "product": "unknown",
            "package": "unknown",
            "client_version": "1.0.0",
            "system_version": "unknown",
            "sdk_version": "1.0.0",
            "android_version": "9",
            "requestId": request_id,
        }
        param_str = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        url = self.WS_URL + param_str

        headers = {
            "Authorization": f"Bearer {self._app_key}",
            "X-AI-GATEWAY-SIGNATURE": "developers-aigc",
            "vaid": "123456789",
        }

        # ── 2. 建立连接 ──
        try:
            ws = create_connection(url, header=headers, timeout=self._timeout)
        except Exception as e:
            raise RuntimeError(f"vivo TTS 连接失败: {e}") from e

        # 读取握手消息
        try:
            code, data = ws.recv_data(True)
            handshake = json.loads(data) if code == ABNF.OPCODE_TEXT else {}
            if handshake.get("error_code") != 0:
                ws.close()
                raise RuntimeError(f"vivo TTS 握手失败: {handshake.get('error_msg', 'unknown')}")
        except Exception as e:
            ws.close()
            raise RuntimeError(f"vivo TTS 握手异常: {e}") from e

        # ── 3. 发送合成请求 ──
        obj = {
            "speed": 50,
            "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            "auf": "audio/L16;rate=24000",
            "vcn": vcn,
            "volume": 50,
            "aue": 0,  # PCM
            "sfl": 1,
            "reqId": int(round(time.time() * 1000)),
        }
        ws.send(json.dumps(obj))

        # ── 4. 接收音频数据 ──
        audio_buff = bytearray()
        error_msg = None
        try:
            while True:
                code, data = ws.recv_data(True)
                if code == ABNF.OPCODE_CLOSE:
                    break
                elif code == ABNF.OPCODE_TEXT:
                    jre = json.loads(data)
                    if jre.get("error_code") != 0:
                        error_msg = jre.get("error_msg", "unknown")
                        logger.warning("vivo TTS 合成错误: %s", error_msg)
                        break
                    if "data" not in jre:
                        continue
                    audio_b64 = jre["data"].get("audio", "")
                    if audio_b64:
                        audio_buff.extend(base64.b64decode(audio_b64))
                    if jre["data"].get("status") == 2:  # 合成结束
                        break
                else:
                    break
        except Exception as e:
            error_msg = str(e)
        finally:
            ws.close()

        if error_msg:
            raise RuntimeError(f"vivo TTS 合成失败: {error_msg}")

        if not audio_buff:
            raise RuntimeError("vivo TTS 未生成音频数据")

        # ── 5. PCM → WAV ──
        return self._pcm_to_wav(bytes(audio_buff))

    def synthesize_to_file(self, text: str, output_path: str, vcn: str = "x2_F25") -> str:
        """合成文本并保存到文件。"""
        wav_data = self.synthesize(text, vcn=vcn)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(wav_data)
        logger.info("TTS 音频已保存: %s (%d bytes)", output_path, len(wav_data))
        return str(output_path)

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, channels: int = 1, bits: int = 16, sample_rate: int = 24000) -> bytes:
        if bits % 8 != 0:
            raise ValueError(f"bits % 8 must == 0: {bits}")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(bits // 8)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        buf.seek(0)
        return buf.read()
