"""图片 OCR 解析模块。"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Union

from PIL import Image

from ..processing.cleaners import clean_text
from ..config import ExtractionConfig
from ..exceptions import DocumentParseError
from .ocr_backends import create_ocr_backend


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def extract_image_text(
    image_path: str,
    config: Optional[Union[ExtractionConfig, Dict]] = None,
) -> str:
    """识别图片中的文字，用于图片题目、截图、PPT 内嵌图片 OCR。"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片不存在: {image_path}")

    cfg = ExtractionConfig.from_dict(config) if isinstance(config, dict) else (config or ExtractionConfig())
    if not cfg.enable_ocr:
        raise DocumentParseError("图片解析需要 OCR，请开启 ExtractionConfig.enable_ocr")

    backend = create_ocr_backend(cfg)
    if backend is None:
        return ""

    try:
        with Image.open(image_path) as image:
            return clean_text(backend.image_to_text(image.convert("RGB")))
    except Exception as exc:
        raise DocumentParseError(f"图片 OCR 失败: {image_path}: {exc}") from exc


def extract_pages_from_image(
    image_path: str,
    config: Optional[Union[ExtractionConfig, Dict]] = None,
) -> List[Dict]:
    """把单张图片包装成页级解析结果。"""
    text = extract_image_text(image_path, config)
    return [{
        "page_number": 1,
        "page": 1,
        "text": text,
        "extraction_method": "image_ocr",
        "method": "image_ocr",
        "char_count": len(text),
        "text_length": len(text),
        "is_ocr": True,
        "is_ocr_text": True,
        "ocr_backend": "",
        "ocr_confidence": None,
        "is_scanned_page": True,
        "failure_reason": "",
        "quality_stats": {},
    }] if text else [{
        "page_number": 1,
        "page": 1,
        "text": "",
        "extraction_method": "image_ocr",
        "method": "image_ocr",
        "char_count": 0,
        "text_length": 0,
        "is_ocr": True,
        "is_ocr_text": True,
        "ocr_backend": "",
        "ocr_confidence": None,
        "is_scanned_page": True,
        "failure_reason": "OCR 未识别到有效文本",
        "quality_stats": {},
        "error": "OCR 未识别到有效文本",
    }]
