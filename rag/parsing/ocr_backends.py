"""OCR 后端适配层：本地 OCR 优先，在线 OCR 可作为临时链路保障。"""

from __future__ import annotations

import base64
import io
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from ..config import ExtractionConfig
from ..exceptions import OCRConfigurationError, OCRDependencyError, OCRRuntimeError


@dataclass
class OCRResult:
    text: str
    confidence: Optional[float]
    backend: str


class OCRBackend(ABC):
    """OCR 后端抽象基类。"""

    name = "base"

    @abstractmethod
    def image_to_text(self, image: Image.Image) -> str:
        """将 PIL.Image 识别为文本。"""

    def image_to_result(self, image: Image.Image) -> OCRResult:
        return OCRResult(text=self.image_to_text(image), confidence=None, backend=self.name)


class TesseractOCRBackend(OCRBackend):
    """pytesseract 后端，适合本地轻量部署。"""

    name = "tesseract"

    def __init__(self, config: ExtractionConfig):
        self.config = config
        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:
            raise OCRDependencyError("缺少 pytesseract：pip install pytesseract，并安装系统 tesseract-ocr") from exc

    def image_to_text(self, image: Image.Image) -> str:
        import pytesseract

        try:
            return pytesseract.image_to_string(image, lang=self.config.ocr_lang) or ""
        except Exception as exc:
            raise OCRRuntimeError(f"Tesseract OCR 失败: {exc}") from exc

    def image_to_result(self, image: Image.Image) -> OCRResult:
        import pytesseract

        try:
            data = pytesseract.image_to_data(image, lang=self.config.ocr_lang, output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for word, conf in zip(data.get("text", []), data.get("conf", [])):
                if str(word).strip():
                    words.append(str(word))
                    try:
                        value = float(conf)
                        if value >= 0:
                            confs.append(value / 100.0)
                    except Exception:
                        pass
            text = " ".join(words) if words else self.image_to_text(image)
            confidence = sum(confs) / len(confs) if confs else None
            return OCRResult(text=text, confidence=confidence, backend=self.name)
        except Exception as exc:
            raise OCRRuntimeError(f"Tesseract OCR 失败: {exc}") from exc


class PaddleOCRBackend(OCRBackend):
    """PaddleOCR 后端，中文教材扫描件效果通常优于 Tesseract。"""

    name = "paddle"

    def __init__(self, config: ExtractionConfig):
        self.config = config
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OCRDependencyError("缺少 PaddleOCR：pip install paddlepaddle paddleocr") from exc

        self._ocr = PaddleOCR(
            lang=config.paddle_lang,
            use_angle_cls=True,
            show_log=False,
        )

    def image_to_text(self, image: Image.Image) -> str:
        import numpy as np

        arr = np.array(image.convert("RGB"))
        try:
            result = self._ocr.ocr(arr, cls=True)
        except Exception as exc:
            raise OCRRuntimeError(f"PaddleOCR 失败: {exc}") from exc
        text, confidence = _parse_paddle_result(result)
        return text

    def image_to_result(self, image: Image.Image) -> OCRResult:
        import numpy as np

        arr = np.array(image.convert("RGB"))
        try:
            result = self._ocr.ocr(arr, cls=True)
        except Exception as exc:
            raise OCRRuntimeError(f"PaddleOCR 失败: {exc}") from exc
        text, confidence = _parse_paddle_result(result)
        return OCRResult(text=text, confidence=confidence, backend=self.name)


class BaiduOCRBackend(OCRBackend):
    """
    百度 OCR 后端。
    适用于本地 OCR 暂时部署困难时打通链路。
    需要环境变量：
    - BAIDU_OCR_API_KEY
    - BAIDU_OCR_SECRET_KEY
    """

    name = "baidu"

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"

    def __init__(self, config: ExtractionConfig):
        self.config = config
        if not config.enable_online_ocr:
            raise OCRConfigurationError("百度 OCR 默认关闭，请设置 enable_online_ocr=True 后再启用")
        try:
            import requests  # noqa: F401
        except ImportError as exc:
            raise OCRDependencyError("缺少 requests：pip install requests") from exc

        self.api_key = os.getenv(config.baidu_api_key_env)
        self.secret_key = os.getenv(config.baidu_secret_key_env)
        if not self.api_key or not self.secret_key:
            raise OCRDependencyError(
                f"缺少百度 OCR 凭证环境变量: {config.baidu_api_key_env}, {config.baidu_secret_key_env}"
            )
        self._token: Optional[str] = None
        self._token_expire_at = 0.0

    def _get_token(self) -> str:
        import requests

        if self._token and time.time() < self._token_expire_at:
            return self._token

        resp = requests.post(
            self.TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise OCRRuntimeError(f"百度 OCR token 获取失败: {data}")
        self._token = token
        self._token_expire_at = time.time() + int(data.get("expires_in", 2592000)) - 300
        return token

    def image_to_text(self, image: Image.Image) -> str:
        import requests

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        resp = requests.post(
            self.OCR_URL,
            params={"access_token": self._get_token()},
            data={"image": encoded},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error_code" in data:
            raise OCRRuntimeError(f"百度 OCR 失败: {data}")
        return "\n".join(item.get("words", "") for item in data.get("words_result", []))


class TencentOCRBackend(OCRBackend):
    """
    腾讯 OCR 后端。
    需要安装 tencentcloud-sdk-python 并设置：
    - TENCENT_SECRET_ID
    - TENCENT_SECRET_KEY
    """

    name = "tencent"

    def __init__(self, config: ExtractionConfig):
        self.config = config
        if not config.enable_online_ocr:
            raise OCRConfigurationError("腾讯 OCR 默认关闭，请设置 enable_online_ocr=True 后再启用")
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.ocr.v20181119 import ocr_client
        except ImportError as exc:
            raise OCRDependencyError("缺少腾讯云 SDK：pip install tencentcloud-sdk-python") from exc

        sid = os.getenv(config.tencent_secret_id_env)
        skey = os.getenv(config.tencent_secret_key_env)
        if not sid or not skey:
            raise OCRDependencyError(
                f"缺少腾讯 OCR 凭证环境变量: {config.tencent_secret_id_env}, {config.tencent_secret_key_env}"
            )

        cred = credential.Credential(sid, skey)
        http_profile = HttpProfile()
        http_profile.endpoint = "ocr.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._client = ocr_client.OcrClient(cred, config.tencent_region, client_profile)

    def image_to_text(self, image: Image.Image) -> str:
        from tencentcloud.ocr.v20181119 import models

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        req = models.GeneralBasicOCRRequest()
        req.ImageBase64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        try:
            resp = self._client.GeneralBasicOCR(req)
        except Exception as exc:
            raise OCRRuntimeError(f"腾讯 OCR 失败: {exc}") from exc
        return "\n".join(item.DetectedText for item in resp.TextDetections or [])


class VivoOCRBackend(OCRBackend):
    """vivo 通用 OCR 后端。

    需要环境变量：
    - VIVO_OCR_APP_ID
    - VIVO_OCR_APP_KEY
    """

    name = "vivo"

    OCR_URL = "http://api-ai.vivo.com.cn/ocr/general_recognition"

    def __init__(self, config: ExtractionConfig):
        self.config = config
        if not config.enable_online_ocr:
            raise OCRConfigurationError("vivo OCR 默认关闭，请设置 enable_online_ocr=True 后再启用")
        try:
            import requests  # noqa: F401
        except ImportError as exc:
            raise OCRDependencyError("缺少 requests：pip install requests") from exc

        self.app_id = os.getenv(config.vivo_app_id_env)
        self.app_key = os.getenv(config.vivo_app_key_env)
        if not self.app_id or not self.app_key:
            raise OCRDependencyError(
                f"缺少 vivo OCR 凭证环境变量: {config.vivo_app_id_env}, {config.vivo_app_key_env}"
            )

    def image_to_text(self, image: Image.Image) -> str:
        import requests
        import uuid

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")

        business_id = "aigc" + self.app_id
        params = {"requestId": str(uuid.uuid4())}
        data = {"image": encoded, "pos": "0", "businessid": business_id}
        headers = {
            "Authorization": f"Bearer {self.app_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        resp = requests.post(
            self.OCR_URL,
            data=data,
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()

        if body.get("error_code") != 0:
            raise OCRRuntimeError(f"vivo OCR 失败: {body.get('error_msg', 'unknown')}")

        result = body.get("result", {})
        words = result.get("words", [])
        return "\n".join(w.get("words", "") for w in words if isinstance(w, dict))


class QwenVLOcrBackend(OCRBackend):
    """Qwen-VL-Plus 多模态 OCR 后端。

    用多模态大模型直接理解图片中的文字和图形。
    比传统 OCR 更强：识别手写体、公式、表格、图形中的文字。
    也看得懂受力图/几何图/电路图。

    需要环境变量：
    - MULTIMODAL_API_KEY（或 OPENAI_API_KEY）
    - MULTIMODAL_API_BASE
    """

    name = "qwen_vl"

    def __init__(self, config: ExtractionConfig):
        self.config = config
        if not config.enable_online_ocr:
            raise OCRConfigurationError("Qwen-VL OCR 默认关闭，请设置 enable_online_ocr=True 后再启用")
        try:
            import requests
        except ImportError as exc:
            raise OCRDependencyError("缺少 requests：pip install requests") from exc

        self.api_key = os.getenv("MULTIMODAL_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.api_base = os.getenv("MULTIMODAL_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = os.getenv("MULTIMODAL_MODEL", "qwen-vl-plus")
        if not self.api_key:
            raise OCRDependencyError("Qwen-VL OCR 需要设置 MULTIMODAL_API_KEY 或 OPENAI_API_KEY")

    def image_to_text(self, image: Image.Image) -> str:
        import requests
        import base64 as b64

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=92)
        encoded = b64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{encoded}"

        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": "请完整提取这张图片中的所有文字内容，包括公式、标题、正文、表格中的文字。保留原有的排版和段落结构。如果包含图形（如受力图、几何图、电路图），请描述图形中的关键信息。"},
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{self.api_base}/chat/completions",
            json=body,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise OCRRuntimeError("Qwen-VL OCR 返回为空")
        return choices[0].get("message", {}).get("content", "").strip()


class AutoOCRBackend(OCRBackend):
    """自动后端：按本地优先、在线兜底顺序尝试。"""

    name = "auto"

    def __init__(self, config: ExtractionConfig):
        self.config = config
        self.backends: Dict[str, OCRBackend] = {}
        self.errors: List[str] = []
        self.backend_order = ["paddle", "tesseract"]
        if config.enable_online_ocr:
            self.backend_order.extend(["qwen_vl", "baidu", "tencent", "vivo"])

    def _get_backend(self, name: str) -> OCRBackend:
        if name in self.backends:
            return self.backends[name]
        cls_map = {
            "paddle": PaddleOCRBackend,
            "tesseract": TesseractOCRBackend,
            "qwen_vl": QwenVLOcrBackend,
            "baidu": BaiduOCRBackend,
            "tencent": TencentOCRBackend,
            "vivo": VivoOCRBackend,
        }
        try:
            backend = cls_map[name](self.config)
        except Exception as exc:
            self.errors.append(f"{name}: {exc}")
            raise
        self.backends[name] = backend
        return backend

    def image_to_text(self, image: Image.Image) -> str:
        return self.image_to_result(image).text

    def image_to_result(self, image: Image.Image) -> OCRResult:
        last_error: Optional[Exception] = None
        for name in self.backend_order:
            try:
                backend = self._get_backend(name)
                result = backend.image_to_result(image)
                if result.text.strip():
                    return result
            except Exception as exc:
                last_error = exc
        detail = " | ".join(self.errors[-6:])
        raise OCRRuntimeError(f"所有 OCR 后端均失败，最后错误: {last_error}; 尝试记录: {detail}")


def _parse_paddle_result(result: Any) -> Tuple[str, Optional[float]]:
    """兼容 PaddleOCR 常见 v2/v3 返回结构。"""
    lines: List[str] = []
    scores: List[float] = []
    if not result:
        return "", None

    # v2 常见结构：[[[box, (text, score)], ...]]
    for page_or_line in result:
        if isinstance(page_or_line, dict):
            # v3 部分场景会返回 dict
            rec_texts = page_or_line.get("rec_texts") or page_or_line.get("texts")
            if rec_texts:
                lines.extend(str(x) for x in rec_texts if x)
            rec_scores = page_or_line.get("rec_scores") or page_or_line.get("scores")
            if rec_scores:
                scores.extend(float(x) for x in rec_scores if x is not None)
            continue

        if not isinstance(page_or_line, list):
            continue

        for item in page_or_line:
            if isinstance(item, list) and len(item) >= 2:
                payload = item[1]
                if isinstance(payload, (list, tuple)) and payload:
                    lines.append(str(payload[0]))
                    if len(payload) > 1:
                        try:
                            scores.append(float(payload[1]))
                        except Exception:
                            pass
                elif isinstance(payload, str):
                    lines.append(payload)
            elif isinstance(item, tuple) and item:
                lines.append(str(item[0]))

    text = "\n".join(x.strip() for x in lines if str(x).strip())
    confidence = sum(scores) / len(scores) if scores else None
    return text, confidence


def create_ocr_backend(config: ExtractionConfig) -> Optional[OCRBackend]:
    """根据配置创建 OCR 后端。"""
    backend = config.ocr_backend.lower()
    if backend == "none" or not config.enable_ocr:
        return None
    if backend == "auto":
        return AutoOCRBackend(config)
    if backend == "tesseract":
        return TesseractOCRBackend(config)
    if backend == "paddle":
        return PaddleOCRBackend(config)
    if backend == "baidu":
        return BaiduOCRBackend(config)
    if backend == "tencent":
        return TencentOCRBackend(config)
    if backend == "vivo":
        return VivoOCRBackend(config)
    if backend == "qwen_vl":
        return QwenVLOcrBackend(config)
    raise OCRDependencyError(f"未知 OCR 后端: {config.ocr_backend}")


_BACKEND_POOL: Dict[Tuple[str, str, str, bool], OCRBackend] = {}


def get_ocr_backend(config: ExtractionConfig) -> Optional[OCRBackend]:
    """Lazily create and cache OCR backends per config signature."""
    key = (config.ocr_backend.lower(), config.ocr_lang, config.paddle_lang, config.enable_online_ocr)
    if key not in _BACKEND_POOL:
        _BACKEND_POOL[key] = create_ocr_backend(config)
    return _BACKEND_POOL[key]
