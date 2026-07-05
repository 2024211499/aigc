"""PDF 解析模块：PyPDF2/pypdf 直接提取 + 扫描件自动 OCR 降级。"""

from __future__ import annotations

import logging
import os
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union

from PIL import Image

from ..processing.cleaners import clean_document_pages, clean_ocr_text_with_stats, clean_textbook_text, gibberish_ratio
from ..config import ExtractionConfig
from ..retrieval.embeddings import file_md5
from ..exceptions import DamagedPDFError, EncryptedPDFError, OCRDependencyError, OCRTimeoutError, PageExtractionError, PDFExtractionError
from .image_preprocess import preprocess_for_ocr
from ..models import PageParseResult
from .ocr_backends import OCRBackend, OCRResult, get_ocr_backend
from .ocr_cache import OCRCache

try:  # pypdf 是 PyPDF2 的现代维护分支
    from pypdf import PdfReader
except ImportError:  # 兼容旧环境
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except ImportError:  # PDF 功能按需报错，避免影响非 PDF 测试和导入。
        PdfReader = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class PageData:
    page: int
    text: str
    method: str
    char_count: int
    image_count: int = 0
    image_coverage: float = 0.0
    gibberish_ratio: float = 0.0


class PDFExtractor:
    """
    PDF 文本提取器。

    工作逻辑：
    - 先用 PyPDF2/pypdf 提取文本；
    - 如果整本文本为空/极少，判定为扫描型 PDF，自动 OCR；
    - 如果只有部分页面文本为空，按页 OCR，支持混合型 PDF；
    - 清洗 OCR 噪声、页眉页脚、页码。
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc_md5 = file_md5(pdf_path) if os.path.exists(pdf_path) else ""
        self._reader: Optional[PdfReader] = None
        self._fitz_doc = None
        self._ocr_backend: Optional[OCRBackend] = None
        self.failed_pages: List[Dict] = []

    def __enter__(self) -> "PDFExtractor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._reader = None
        if self._fitz_doc is not None:
            try:
                self._fitz_doc.close()
            except Exception:
                logger.debug("关闭 PyMuPDF 文档失败", exc_info=True)
        self._fitz_doc = None
        self._ocr_backend = None

    @staticmethod
    def _normalize_config(config: Optional[Union[ExtractionConfig, Dict]]) -> ExtractionConfig:
        if isinstance(config, dict):
            return ExtractionConfig.from_dict(config)
        return config or ExtractionConfig()

    def _open_reader(self, config: ExtractionConfig) -> PdfReader:
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"PDF 文件不存在: {self.pdf_path}")
        if PdfReader is None:
            if self._fitz_for() is not None:
                return None  # type: ignore[return-value]
            raise PDFExtractionError("缺少 pypdf/PyPDF2/PyMuPDF：pip install pypdf PyMuPDF")
        try:
            reader = PdfReader(self.pdf_path)
        except Exception as exc:
            raise DamagedPDFError(f"PDF 可能损坏或格式异常: {self.pdf_path}") from exc

        if getattr(reader, "is_encrypted", False):
            password = config.pdf_password or ""
            try:
                ok = reader.decrypt(password)
            except Exception as exc:
                raise EncryptedPDFError(f"PDF 已加密且解密失败: {self.pdf_path}") from exc
            if ok == 0:
                raise EncryptedPDFError(f"PDF 已加密，请提供正确 pdf_password: {self.pdf_path}")
        return reader

    def _reader_for(self, config: ExtractionConfig) -> PdfReader:
        if self._reader is None:
            self._reader = self._open_reader(config)
        return self._reader

    @property
    def total_pages(self) -> int:
        reader = self._reader_for(ExtractionConfig())
        if reader is not None:
            return len(reader.pages)
        fitz_doc = self._fitz_for()
        return len(fitz_doc) if fitz_doc is not None else 0

    def _ocr_for(self, config: ExtractionConfig) -> Optional[OCRBackend]:
        if not config.enable_ocr:
            return None
        if self._ocr_backend is None:
            self._ocr_backend = get_ocr_backend(config)
        return self._ocr_backend

    def _fitz_for(self):
        if self._fitz_doc is None:
            try:
                import fitz

                self._fitz_doc = fitz.open(self.pdf_path)
            except ImportError:
                return None
            except Exception as exc:
                logger.debug("PyMuPDF 打开失败，回退 pypdf: %s", exc)
                return None
        return self._fitz_doc

    def _extract_direct_text(self, page, page_num: int, config: ExtractionConfig) -> str:
        fitz_doc = self._fitz_for()
        if fitz_doc is not None:
            try:
                text = fitz_doc[page_num - 1].get_text("text") or ""
                if text.strip():
                    return text.strip()
            except Exception as exc:
                logger.debug("第 %s 页 PyMuPDF 提取失败，回退 pypdf: %s", page_num, exc)
        try:
            text = page.extract_text() or ""
            return text.strip()
        except Exception as exc:
            if config.skip_bad_pages:
                logger.warning("第 %s 页 PyPDF2 提取失败，准备跳过或 OCR: %s", page_num, exc)
                return ""
            raise PageExtractionError(f"第 {page_num} 页文本提取失败") from exc

    def _count_page_images(self, page) -> int:
        """尽量统计页面图像对象数量，用于扫描件判断。"""
        try:
            resources = page.get("/Resources") or {}
            xobject = resources.get("/XObject") or {}
            xobject = xobject.get_object() if hasattr(xobject, "get_object") else xobject
            count = 0
            for obj in xobject.values():
                obj = obj.get_object() if hasattr(obj, "get_object") else obj
                if obj.get("/Subtype") == "/Image":
                    count += 1
            return count
        except Exception:
            return 0

    def _page_image_coverage(self, page_num: int, pypdf_page=None) -> float:
        """Approximate image area coverage for scanned-page detection."""
        fitz_doc = self._fitz_for()
        if fitz_doc is not None:
            try:
                page = fitz_doc[page_num - 1]
                page_area = max(float(page.rect.width * page.rect.height), 1.0)
                coverage = 0.0
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") == 1:
                        x0, y0, x1, y1 = block.get("bbox", (0, 0, 0, 0))
                        coverage += max(0.0, (x1 - x0) * (y1 - y0)) / page_area
                return min(1.0, coverage)
            except Exception:
                return 0.0
        return 1.0 if pypdf_page is not None and self._count_page_images(pypdf_page) else 0.0

    def _page_profile(self, page, page_num: int, config: ExtractionConfig) -> Dict:
        direct_text = self._extract_direct_text(page, page_num, config)
        image_count = self._count_page_images(page)
        image_coverage = self._page_image_coverage(page_num, page)
        ratio = gibberish_ratio(direct_text)
        text_len = len(direct_text.strip())
        # Do not mark a short but clean text-only page as scanned.
        # Textbook title pages / chapter dividers are often short; OCRing them wastes
        # time and can even replace good embedded text with noisy OCR.
        has_image_layer = image_count > 0 or image_coverage >= config.image_ratio_threshold
        text_empty = text_len == 0
        text_very_short = text_len < config.min_text_chars_per_page
        text_garbled = ratio >= config.gibberish_ratio_threshold
        image_dominant = image_coverage >= config.image_ratio_threshold
        is_scanned = (
            (text_empty and has_image_layer)
            or (text_garbled and (has_image_layer or text_len >= config.min_text_chars_per_page))
            or (image_dominant and text_len < config.scan_avg_text_threshold)
        )
        low_quality = text_empty or text_garbled or (has_image_layer and text_very_short)
        return {
            "direct_text": direct_text,
            "image_count": image_count,
            "image_coverage": image_coverage,
            "gibberish_ratio": ratio,
            "text_length": text_len,
            "is_scanned_page": is_scanned,
            "low_quality": low_quality,
        }

    def detect_scan_profile(self, config: Optional[Union[ExtractionConfig, Dict]] = None) -> Dict[str, float]:
        """
        抽样判断 PDF 是否疑似扫描件。
        返回:
        - avg_text_chars: 样本页平均文本长度
        - low_text_ratio: 低文本页比例
        - image_ratio: 含图片页比例
        - likely_scanned: 是否疑似扫描件
        """
        cfg = self._normalize_config(config)
        reader = self._reader_for(cfg)
        if reader is None:
            return self._detect_scan_profile_fitz(cfg)
        sample_n = min(cfg.scan_detect_sample_pages, len(reader.pages))
        if sample_n <= 0:
            return {"avg_text_chars": 0, "low_text_ratio": 0, "image_ratio": 0, "likely_scanned": 0}

        chars: List[int] = []
        image_pages = 0
        for idx in range(sample_n):
            page = reader.pages[idx]
            profile = self._page_profile(page, idx + 1, cfg)
            chars.append(profile["text_length"])
            if profile["image_count"] > 0 or profile["image_coverage"] >= cfg.image_ratio_threshold:
                image_pages += 1

        avg_text = sum(chars) / sample_n
        low_ratio = sum(c < cfg.min_text_chars_per_page for c in chars) / sample_n
        image_ratio = image_pages / sample_n
        likely = (
            avg_text < cfg.scan_avg_text_threshold
            and low_ratio >= cfg.scan_low_text_ratio_threshold
        ) or (
            image_ratio >= cfg.image_ratio_threshold
            and avg_text < cfg.scan_avg_text_threshold
        )
        return {
            "avg_text_chars": avg_text,
            "low_text_ratio": low_ratio,
            "image_ratio": image_ratio,
            "likely_scanned": float(bool(likely)),
        }

    def _detect_scan_profile_fitz(self, cfg: ExtractionConfig) -> Dict[str, float]:
        fitz_doc = self._fitz_for()
        if fitz_doc is None:
            return {"avg_text_chars": 0, "low_text_ratio": 0, "image_ratio": 0, "likely_scanned": 0}
        sample_n = min(cfg.scan_detect_sample_pages, len(fitz_doc))
        chars: List[int] = []
        image_pages = 0
        for idx in range(sample_n):
            text = fitz_doc[idx].get_text("text") or ""
            chars.append(len(text.strip()))
            if fitz_doc[idx].get_images(full=True):
                image_pages += 1
        avg_text = sum(chars) / max(sample_n, 1)
        low_ratio = sum(c < cfg.min_text_chars_per_page for c in chars) / max(sample_n, 1)
        image_ratio = image_pages / max(sample_n, 1)
        likely = avg_text < cfg.scan_avg_text_threshold and (low_ratio >= cfg.scan_low_text_ratio_threshold or image_ratio >= cfg.image_ratio_threshold)
        return {"avg_text_chars": avg_text, "low_text_ratio": low_ratio, "image_ratio": image_ratio, "likely_scanned": float(bool(likely))}

    def _render_page_to_image(self, page_num: int, config: ExtractionConfig) -> Image.Image:
        """
        将 PDF 单页渲染为图片。
        优先 pdf2image，缺失时尝试 PyMuPDF。
        """
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(
                self.pdf_path,
                dpi=config.ocr_dpi,
                first_page=page_num,
                last_page=page_num,
                fmt="png",
                thread_count=1,
                use_pdftocairo=True,
            )
            if not images:
                raise PDFExtractionError(f"第 {page_num} 页渲染为空")
            return _resize_if_needed(images[0], config.ocr_render_max_side)
        except ImportError:
            logger.debug("pdf2image 未安装，尝试 PyMuPDF 渲染")
        except Exception as exc:
            logger.warning("pdf2image 渲染第 %s 页失败，尝试 PyMuPDF: %s", page_num, exc)

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(self.pdf_path)
            page = doc[page_num - 1]
            zoom = config.ocr_dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            return _resize_if_needed(image, config.ocr_render_max_side)
        except ImportError as exc:
            raise OCRDependencyError("需要安装 pdf2image 或 PyMuPDF 才能渲染扫描 PDF 页面") from exc
        except Exception as exc:
            raise PDFExtractionError(f"第 {page_num} 页渲染失败: {exc}") from exc

    def _ocr_page(self, page_num: int, config: ExtractionConfig) -> str:
        result = self._ocr_page_result(page_num, config)
        return result.text

    def _ocr_page_result(self, page_num: int, config: ExtractionConfig) -> OCRResult:
        backend = self._ocr_for(config)
        if backend is None:
            return OCRResult(text="", confidence=None, backend="")
        backend_name = getattr(backend, "name", config.ocr_backend)
        lang = config.paddle_lang if config.ocr_backend == "paddle" else config.ocr_lang
        cache = OCRCache(config.ocr_cache_dir)
        preprocess_hash = _preprocess_config_hash(config)
        cache_key = cache.make_key(
            doc_md5=self.doc_md5,
            page_number=page_num,
            backend=backend_name,
            dpi=config.ocr_dpi,
            lang=lang,
            preprocess_version=config.preprocess_version,
            preprocess_config_hash=preprocess_hash,
        )
        cached = cache.get(cache_key)
        # Only reuse successful OCR results. A cached dependency failure should not
        # poison future runs after the user installs PaddleOCR/Tesseract or changes
        # the online OCR configuration.
        if cached and cached.get("text") and not cached.get("failure_reason"):
            return OCRResult(text=cached.get("text") or "", confidence=cached.get("confidence"), backend=cached.get("backend") or backend_name)
        image = self._render_page_to_image(page_num, config)
        if config.preprocess_images:
            image = preprocess_for_ocr(image, config.ocr_render_max_side)
        start = time.monotonic()
        last_error: Optional[Exception] = None
        for attempt in range(config.ocr_retries + 1):
            try:
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(backend.image_to_result, image)
                try:
                    result = future.result(timeout=config.ocr_timeout_seconds)
                except FutureTimeoutError as exc:
                    future.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise OCRTimeoutError(f"第 {page_num} 页 OCR 超时: {config.ocr_timeout_seconds}s") from exc
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
                result.text = result.text.strip()
                elapsed_ms = int((time.monotonic() - start) * 1000)
                cache.put(
                    cache_key=cache_key,
                    doc_md5=self.doc_md5,
                    page_number=page_num,
                    backend=result.backend or backend_name,
                    dpi=config.ocr_dpi,
                    lang=lang,
                    preprocess_version=config.preprocess_version,
                    text=result.text,
                    confidence=result.confidence,
                    elapsed_ms=elapsed_ms,
                )
                return result
            except Exception as exc:
                last_error = exc
                if attempt < config.ocr_retries:
                    logger.warning("第 %s 页 OCR 第 %s 次失败，准备重试: %s", page_num, attempt + 1, exc)
        # Do not persist failed OCR as a normal cache entry. Dependency/configuration
        # failures are common during deployment and should not survive after the
        # environment has been fixed.
        raise PDFExtractionError(f"第 {page_num} 页 OCR 失败: {last_error}")

    def extract_pages(self, config: Optional[Union[ExtractionConfig, Dict]] = None) -> List[Dict]:
        """提取每页文本并保留页码、提取方式等元数据。"""
        cfg = self._normalize_config(config)
        reader = self._reader_for(cfg)
        if reader is None:
            return self._extract_pages_fitz_only(cfg)
        self.failed_pages = []
        scan_profile = self.detect_scan_profile(cfg)
        # A document-level scanned signal is only a hint. OCR is still decided per
        # page so mixed PDFs do not OCR every page unnecessarily.
        force_doc_ocr = cfg.enable_ocr and bool(scan_profile["likely_scanned"])

        logger.info(
            "PDF 扫描检测: avg_text=%.1f, low_text_ratio=%.2f, image_ratio=%.2f, likely_scanned=%s",
            scan_profile["avg_text_chars"],
            scan_profile["low_text_ratio"],
            scan_profile["image_ratio"],
            bool(scan_profile["likely_scanned"]),
        )

        pages: List[Dict] = []
        ocr_used = 0
        for idx, page in enumerate(reader.pages, start=1):
            profile = self._page_profile(page, idx, cfg)
            direct_text = profile["direct_text"]
            image_count = profile["image_count"]
            low_text = profile["low_quality"]

            need_ocr = (
                cfg.enable_ocr
                and (
                    profile["is_scanned_page"]
                    or (force_doc_ocr and profile["text_length"] == 0)
                    or (cfg.force_ocr_for_low_text_pages and low_text and (profile["image_count"] > 0 or profile["image_coverage"] >= cfg.image_ratio_threshold))
                )
            )
            if cfg.ocr_max_pages is not None and ocr_used >= cfg.ocr_max_pages:
                need_ocr = False

            if need_ocr:
                try:
                    ocr_result = self._ocr_page_result(idx, cfg)
                    ocr_text, clean_stats = clean_ocr_text_with_stats(ocr_result.text)
                    ocr_used += 1
                    if len(ocr_text) >= len(direct_text):
                        pages.append(PageParseResult(
                            page_number=idx,
                            text=ocr_text,
                            raw_text=ocr_result.text,
                            cleaned_text=ocr_text,
                            extraction_method="ocr" if not direct_text else "mixed",
                            ocr_backend=ocr_result.backend,
                            ocr_confidence=ocr_result.confidence,
                            is_scanned_page=bool(profile["is_scanned_page"]),
                            quality_stats={**profile, **clean_stats.to_dict()},
                            image_count=image_count,
                            image_coverage=profile["image_coverage"],
                            text_length=len(ocr_text),
                        ).to_dict())
                        continue
                except Exception as exc:
                    if cfg.skip_bad_pages:
                        logger.warning("第 %s 页 OCR 失败，回退直接文本: %s", idx, exc)
                        self.failed_pages.append({
                            "page_number": idx,
                            "page": idx,
                            "extraction_method": "ocr",
                            "method": "ocr",
                            "failure_reason": str(exc),
                            "error": str(exc),
                        })
                    else:
                        raise

            if direct_text:
                cleaned, clean_stats = clean_textbook_text(direct_text, return_stats=True)
                pages.append(PageParseResult(
                            page_number=idx,
                            raw_text=direct_text,
                            text=cleaned,
                            cleaned_text=cleaned,
                            extraction_method="direct",
                    is_scanned_page=bool(profile["is_scanned_page"]),
                    quality_stats={**profile, **clean_stats.to_dict()},
                    image_count=image_count,
                    image_coverage=profile["image_coverage"],
                    text_length=len(cleaned),
                    failure_reason="low_quality_direct_text" if profile["low_quality"] else "",
                ).to_dict())
            elif cfg.skip_bad_pages:
                logger.warning("第 %s 页没有可用文本", idx)
                self.failed_pages.append({
                    "page_number": idx,
                    "page": idx,
                    "extraction_method": "direct" if not need_ocr else "failed",
                    "method": "direct" if not need_ocr else "failed",
                    "failure_reason": "没有可用文本",
                    "error": "没有可用文本",
                })
            else:
                raise PageExtractionError(f"第 {idx} 页没有可用文本")

        if cfg.remove_repeated_headers_footers:
            pages = clean_document_pages(pages, min_occurrences=cfg.repeated_line_min_occurrences)

        total_chars = sum(p.get("char_count", len(p.get("text", ""))) for p in pages)
        if total_chars < cfg.min_text_chars_total:
            logger.warning("PDF 提取文本总量较少: %s 字符，可能仍需调整 OCR 参数或语言包", total_chars)

        logger.info("PDF 提取完成: %s/%s 页有效，其中 OCR 页约 %s 页", len(pages), len(reader.pages), ocr_used)
        return pages

    def _extract_pages_fitz_only(self, cfg: ExtractionConfig) -> List[Dict]:
        fitz_doc = self._fitz_for()
        if fitz_doc is None:
            raise PDFExtractionError("缺少可用 PDF 解析后端")
        self.failed_pages = []
        scan_profile = self._detect_scan_profile_fitz(cfg)
        pages: List[Dict] = []
        ocr_used = 0
        for idx in range(1, len(fitz_doc) + 1):
            page = fitz_doc[idx - 1]
            direct_text = (page.get_text("text") or "").strip()
            image_count = len(page.get_images(full=True) or [])
            image_coverage = self._page_image_coverage(idx)
            ratio = gibberish_ratio(direct_text)
            has_image_layer = image_count > 0 or image_coverage >= cfg.image_ratio_threshold
            text_len = len(direct_text)
            text_empty = text_len == 0
            text_garbled = ratio >= cfg.gibberish_ratio_threshold
            low_quality = text_empty or text_garbled or (has_image_layer and text_len < cfg.min_text_chars_per_page)
            is_scanned = (text_empty and has_image_layer) or (text_garbled and has_image_layer) or (image_coverage >= cfg.image_ratio_threshold and text_len < cfg.scan_avg_text_threshold)
            profile = {
                "image_count": image_count,
                "image_coverage": image_coverage,
                "gibberish_ratio": ratio,
                "text_length": len(direct_text),
                "is_scanned_page": is_scanned,
                "low_quality": low_quality,
            }
            need_ocr = cfg.enable_ocr and (is_scanned or (bool(scan_profile["likely_scanned"]) and not direct_text))
            if cfg.ocr_max_pages is not None and ocr_used >= cfg.ocr_max_pages:
                need_ocr = False
            if need_ocr:
                try:
                    ocr_result = self._ocr_page_result(idx, cfg)
                    ocr_text, clean_stats = clean_ocr_text_with_stats(ocr_result.text)
                    ocr_used += 1
                    if len(ocr_text) >= len(direct_text):
                        pages.append(PageParseResult(
                            page_number=idx,
                            text=ocr_text,
                            raw_text=ocr_result.text,
                            cleaned_text=ocr_text,
                            extraction_method="ocr" if not direct_text else "mixed",
                            ocr_backend=ocr_result.backend,
                            ocr_confidence=ocr_result.confidence,
                            is_scanned_page=bool(is_scanned),
                            quality_stats={**profile, **clean_stats.to_dict()},
                            image_count=image_count,
                            image_coverage=image_coverage,
                            text_length=len(ocr_text),
                        ).to_dict())
                        continue
                except Exception as exc:
                    logger.warning("第 %s 页 OCR 失败，回退直接文本: %s", idx, exc)
                    self.failed_pages.append({"page_number": idx, "page": idx, "method": "ocr", "extraction_method": "ocr", "error": str(exc), "failure_reason": str(exc)})
            if direct_text:
                cleaned, clean_stats = clean_textbook_text(direct_text, return_stats=True)
                pages.append(PageParseResult(
                    page_number=idx,
                    raw_text=direct_text,
                    text=cleaned,
                    cleaned_text=cleaned,
                    extraction_method="direct",
                    is_scanned_page=bool(is_scanned),
                    failure_reason="low_quality_direct_text" if low_quality else "",
                    quality_stats={**profile, **clean_stats.to_dict()},
                    image_count=image_count,
                    image_coverage=image_coverage,
                    text_length=len(cleaned),
                ).to_dict())
            else:
                self.failed_pages.append({"page_number": idx, "page": idx, "method": "failed", "extraction_method": "failed", "error": "没有可用文本", "failure_reason": "没有可用文本"})
        if cfg.remove_repeated_headers_footers:
            pages = clean_document_pages(pages, min_occurrences=cfg.repeated_line_min_occurrences)
        logger.info("PDF(PyMuPDF) 提取完成: %s/%s 页有效，其中 OCR 页约 %s 页", len(pages), len(fitz_doc), ocr_used)
        return pages

    def extract_text(self, config: Optional[Union[ExtractionConfig, Dict]] = None) -> str:
        pages = self.extract_pages(config)
        return "\n\n".join(p["text"] for p in pages if p.get("text"))

    def iter_pages(self, config: Optional[Union[ExtractionConfig, Dict]] = None) -> Iterator[Tuple[int, str]]:
        for p in self.extract_pages(config):
            yield int(p["page"]), str(p["text"])


def _resize_if_needed(image: Image.Image, max_side: int) -> Image.Image:
    w, h = image.size
    longest = max(w, h)
    if longest <= max_side:
        return image
    ratio = max_side / longest
    new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
    return image.resize(new_size)


def _preprocess_config_hash(config: ExtractionConfig) -> str:
    raw = f"{config.preprocess_version}|{config.preprocess_images}|{config.ocr_render_max_side}|{config.ocr_dpi}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
