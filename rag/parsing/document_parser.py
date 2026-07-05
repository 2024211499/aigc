"""统一文档解析入口：PDF / Word / PPT / 图片 / 文本自动路由。"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from ..processing.cleaners import clean_text, normalize_math_text
from ..config import ExtractionConfig
from .docx_parser import extract_pages_from_docx, extract_text_from_docx
from ..exceptions import DocumentParseError
from .image_parser import IMAGE_EXTENSIONS, extract_image_text, extract_pages_from_image
from .pdf_parser import PDFExtractor
from .pptx_parser import extract_pages_from_pptx, extract_pptx_text


@dataclass
class ParseResult:
    text: str
    pages: List[Dict]
    metadata: Dict


def detect_file_type(file_path: str) -> str:
    """
    判断文件类型。

    返回值：pdf / word / ppt / image / text / other。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".docx", ".doc"}:
        return "word"
    if ext in {".pptx", ".ppt"}:
        return "ppt"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in {".txt", ".md", ".markdown", ".csv"}:
        return "text"

    # 对被改名的 docx/pptx 做一次轻量 ZIP 内容识别。
    try:
        with zipfile.ZipFile(file_path) as zf:
            names = set(zf.namelist())
            if "word/document.xml" in names:
                return "word"
            if "ppt/presentation.xml" in names:
                return "ppt"
    except Exception:
        pass
    return "other"


def extract_pdf_text(file_path: str, config: Optional[Union[ExtractionConfig, Dict]] = None) -> str:
    """处理文字型 PDF，禁用 OCR，仅做直接文本提取。"""
    cfg = ExtractionConfig.from_dict(config) if isinstance(config, dict) else (config or ExtractionConfig())
    cfg = ExtractionConfig(**{**cfg.__dict__, "enable_ocr": False})
    with PDFExtractor(file_path) as extractor:
        return extractor.extract_text(cfg)


def detect_scanned_pdf(file_path: str, config: Optional[Union[ExtractionConfig, Dict]] = None) -> bool:
    """判断 PDF 是否疑似扫描版。"""
    cfg = ExtractionConfig.from_dict(config) if isinstance(config, dict) else (config or ExtractionConfig())
    with PDFExtractor(file_path) as extractor:
        profile = extractor.detect_scan_profile(cfg)
    return bool(profile.get("likely_scanned"))


def extract_scanned_pdf_ocr(file_path: str, config: Optional[Union[ExtractionConfig, Dict]] = None) -> str:
    """处理扫描版 PDF，强制低文本页走 OCR。"""
    cfg = ExtractionConfig.from_dict(config) if isinstance(config, dict) else (config or ExtractionConfig())
    cfg = ExtractionConfig(**{
        **cfg.__dict__,
        "enable_ocr": True,
        "force_ocr_for_low_text_pages": True,
        "scan_avg_text_threshold": max(cfg.scan_avg_text_threshold, 1000000),
    })
    with PDFExtractor(file_path) as extractor:
        return extractor.extract_text(cfg)


def extract_docx_text(file_path: str) -> str:
    """处理 Word 文档。"""
    return extract_text_from_docx(file_path)


def parse_document_result(
    file_path: str,
    config: Optional[Union[ExtractionConfig, Dict]] = None,
    course_id: Optional[str] = None,
) -> ParseResult:
    """解析文档，返回全文、逐页文本与文档元数据。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[-1].lower()
    file_type = detect_file_type(file_path)
    cfg = ExtractionConfig.from_dict(config) if isinstance(config, dict) else (config or ExtractionConfig())
    failed_pages: List[Dict] = []

    if file_type == "pdf":
        with PDFExtractor(file_path) as extractor:
            pages = extractor.extract_pages(cfg)
            failed_pages = list(getattr(extractor, "failed_pages", []))
    elif file_type == "word" and ext == ".docx":
        pages = extract_pages_from_docx(file_path)
    elif file_type == "word" and ext == ".doc":
        converted = _convert_with_libreoffice(file_path, "docx")
        if converted:
            try:
                pages = extract_pages_from_docx(converted)
            finally:
                shutil.rmtree(os.path.dirname(converted), ignore_errors=True)
        else:
            pages = _extract_pages_from_legacy_doc(file_path)
    elif file_type == "ppt" and ext == ".pptx":
        pages = extract_pages_from_pptx(file_path, cfg)
    elif file_type == "ppt" and ext == ".ppt":
        converted = _convert_with_libreoffice(file_path, "pptx")
        if not converted:
            raise DocumentParseError(".ppt 二进制格式解析失败：请安装 LibreOffice，或用 Office/WPS 另存为 .pptx 后上传")
        try:
            pages = extract_pages_from_pptx(converted, cfg)
        finally:
            shutil.rmtree(os.path.dirname(converted), ignore_errors=True)
    elif file_type == "image":
        pages = extract_pages_from_image(file_path, cfg)
    elif file_type == "text":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = clean_text(f.read())
        pages = [{"page": 1, "text": text, "method": "text", "char_count": len(text), "is_ocr": False}]
    else:
        raise DocumentParseError(f"不支持的文件类型: {ext}")

    normalized_pages: List[Dict] = []
    for page in pages:
        page = dict(page)
        if "page_number" not in page:
            page["page_number"] = page.get("page")
        if "extraction_method" not in page:
            page["extraction_method"] = page.get("method", "")
        raw_text = page.get("raw_text", page.get("text", "")) or ""
        cleaned_text = page.get("cleaned_text", page.get("text", "")) or ""
        cleaned_text = normalize_math_text(cleaned_text)
        page["raw_text"] = raw_text
        page["cleaned_text"] = cleaned_text
        page["text"] = cleaned_text
        page["char_count"] = len(cleaned_text)
        page["text_length"] = page["char_count"]
        page["is_ocr"] = bool(page.get("is_ocr") or "ocr" in str(page.get("extraction_method", page.get("method", ""))).lower())
        page["is_ocr_text"] = page["is_ocr"]
        page.setdefault("ocr_backend", "")
        page.setdefault("ocr_confidence", None)
        page.setdefault("is_scanned_page", False)
        page.setdefault("failure_reason", page.get("error", ""))
        page.setdefault("quality_stats", {})
        normalized_pages.append(page)

    text = "\n\n".join(p.get("text", "") for p in normalized_pages if p.get("text"))
    return ParseResult(
        text=text,
        pages=normalized_pages,
        metadata={
            "course_id": course_id,
            "doc_path": os.path.abspath(file_path),
            "doc_name": os.path.basename(file_path),
            "file_ext": ext,
            "file_type": file_type,
            "page_count": len(normalized_pages),
            "failed_pages": failed_pages,
            "failed_page_count": len(failed_pages),
            "char_count": len(text),
        },
    )


def parse_document_pages(
    file_path: str,
    config: Optional[Union[ExtractionConfig, Dict]] = None,
) -> List[Dict]:
    """兼容式接口：返回逐页文本。"""
    return parse_document_result(file_path, config).pages


def parse_document(
    file_path: str,
    course_id: Optional[str] = None,
    config: Optional[Union[ExtractionConfig, Dict]] = None,
) -> str:
    """兼容原接口：只返回完整文本。"""
    if isinstance(course_id, (ExtractionConfig, dict)) and config is None:
        config = course_id
        course_id = None
    return parse_document_result(file_path, config, course_id=course_id).text


def _extract_pages_from_legacy_doc(file_path: str) -> List[Dict]:
    """
    尽量解析旧版 .doc。

    Windows 上优先尝试 Word COM；其他环境可安装 antiword。两者都不可用时抛出
    明确错误，避免静默产出空文本。
    """
    try:
        import win32com.client  # type: ignore

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(os.path.abspath(file_path))
        text = clean_text(doc.Content.Text)
        doc.Close(False)
        word.Quit()
        return [{"page": None, "text": text, "method": "doc_com", "char_count": len(text)}] if text else []
    except Exception:
        pass

    try:
        import subprocess

        proc = subprocess.run(
            ["antiword", file_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = clean_text(proc.stdout)
        return [{"page": None, "text": text, "method": "antiword", "char_count": len(text)}] if text else []
    except Exception as exc:
        raise DocumentParseError(".doc 解析失败：请安装 Microsoft Word COM、antiword，或转换为 .docx") from exc


def _convert_with_libreoffice(file_path: str, target_ext: str) -> Optional[str]:
    """用 LibreOffice/soffice 将旧版 Office 格式转成 docx/pptx。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    out_dir = tempfile.mkdtemp(prefix="aigc_office_convert_")
    target_ext = target_ext.lstrip(".")
    try:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                target_ext,
                "--outdir",
                out_dir,
                file_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        converted = os.path.join(out_dir, os.path.splitext(os.path.basename(file_path))[0] + f".{target_ext}")
        return converted if os.path.exists(converted) else None
    except Exception:
        return None


__all__ = [
    "ParseResult",
    "parse_document_result",
    "parse_document_pages",
    "parse_document",
    "detect_file_type",
    "extract_pdf_text",
    "detect_scanned_pdf",
    "extract_scanned_pdf_ocr",
    "extract_docx_text",
    "extract_pptx_text",
    "extract_image_text",
    "clean_text",
    "normalize_math_text",
]
