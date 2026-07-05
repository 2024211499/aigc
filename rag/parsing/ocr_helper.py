"""兼容旧版 OCRHelper 的薄包装。

旧仓库里存在 `ocr_helper.py`，外部代码可能仍会导入
`from rag.ocr_helper import OCRHelper`。本文件不再维护独立 OCR 逻辑，
只把调用转发到新的 `ocr_backends`、`image_preprocess` 与 `pdf_parser`
能力，避免新旧两套 OCR 结果不一致。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from PIL import Image

from ..config import ExtractionConfig
from .image_preprocess import preprocess_for_ocr
from .ocr_backends import get_ocr_backend

logger = logging.getLogger(__name__)


def get_safe_resolution(page: Any, max_side: int = 2600, default_resolution: int = 220) -> int:
    """根据页面尺寸给出安全 DPI，避免大页 OCR 渲染爆内存。"""
    width = float(getattr(page, "width", 0) or getattr(page, "rect", object()).width if hasattr(getattr(page, "rect", None), "width") else 0)
    height = float(getattr(page, "height", 0) or getattr(page, "rect", object()).height if hasattr(getattr(page, "rect", None), "height") else 0)
    max_pt = max(width, height, 1.0)
    dpi = int(min(default_resolution, max(72, (max_side * 72) / max_pt)))
    return max(72, dpi)


class OCRHelper:
    """旧接口兼容包装，内部使用新 OCR 后端。"""

    _instances: Dict[Tuple[str, str, bool], Any] = {}

    @classmethod
    def get_ocr(cls, lang: str = "ch", **kwargs: Any) -> Any:
        """返回新 OCR backend 实例；保留旧方法名。"""
        backend = kwargs.get("backend", "auto")
        config = ExtractionConfig(
            enable_ocr=True,
            ocr_backend=backend,
            paddle_lang=lang if lang in {"ch", "en"} else "ch",
            ocr_lang=kwargs.get("ocr_lang", "chi_sim+eng"),
            enable_online_ocr=bool(kwargs.get("enable_online_ocr", False)),
        )
        key = (config.ocr_backend, config.paddle_lang, config.enable_online_ocr)
        if key not in cls._instances:
            cls._instances[key] = get_ocr_backend(config)
        return cls._instances[key]

    @classmethod
    def ocr_image_from_array(cls, img_array: Any, lang: str = "ch", **kwargs: Any) -> str:
        """识别 numpy/PIL 图像为文本。"""
        try:
            import numpy as np

            if isinstance(img_array, Image.Image):
                image = img_array
            else:
                image = Image.fromarray(np.asarray(img_array)).convert("RGB")
            config = ExtractionConfig(
                enable_ocr=True,
                ocr_backend=kwargs.get("backend", "auto"),
                paddle_lang=lang if lang in {"ch", "en"} else "ch",
                ocr_lang=kwargs.get("ocr_lang", "chi_sim+eng"),
                enable_online_ocr=bool(kwargs.get("enable_online_ocr", False)),
            )
            if config.preprocess_images:
                image = preprocess_for_ocr(image, config)
            result = get_ocr_backend(config).image_to_result(image)
            return result.text.strip()
        except Exception as exc:
            logger.warning("OCRHelper 识别失败: %s", exc)
            return ""

    @staticmethod
    def parse_ocr_result(result: Any) -> str:
        """兼容 PaddleOCR 结果解析。"""
        if not result:
            return ""
        lines = []
        for block in result if isinstance(result, list) else []:
            if not block:
                continue
            for item in block if isinstance(block, list) else []:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    value = item[1]
                    if isinstance(value, (list, tuple)) and value:
                        text = str(value[0]).strip()
                        if text:
                            lines.append(text)
        deduped = []
        last = None
        for line in lines:
            if line and line != last:
                deduped.append(line)
                last = line
        return "\n".join(deduped)

    @classmethod
    def ocr_page(cls, page: Any, config: ExtractionConfig) -> str:
        """兼容旧 pdfplumber 页级 OCR；新代码优先使用 PDFExtractor。"""
        try:
            image_obj = page.to_image(resolution=getattr(config, "ocr_dpi", 220))
            image = image_obj.original.convert("RGB")
            if config.preprocess_images:
                image = preprocess_for_ocr(image, config)
            result = get_ocr_backend(config).image_to_result(image)
            return result.text.strip()
        except Exception as exc:
            logger.warning("页面 OCR 失败: %s", exc)
            return ""
