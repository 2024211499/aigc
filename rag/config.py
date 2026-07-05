"""配置模块：集中管理解析、OCR、分块、向量库与检索参数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .exceptions import ConfigurationError


def _positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ConfigurationError(f"{name} 必须为正整数，收到: {value}")


@dataclass
class ExtractionConfig:
    """
    文档解析配置。

    关键目标：
    1. 文字型 PDF 直接用 PyPDF2 / pypdf 提取；
    2. 扫描型 PDF 自动切换 OCR；
    3. 混合型 PDF 只对空文本页或低文本页做 OCR；
    4. OCR 结果进入专项清洗流程。
    """

    # PDF 基础解析
    skip_bad_pages: bool = True
    pdf_password: Optional[str] = None

    # 扫描 PDF 判定阈值
    min_text_chars_per_page: int = 20
    min_text_chars_total: int = 80
    scan_detect_sample_pages: int = 5
    scan_avg_text_threshold: int = 30
    scan_low_text_ratio_threshold: float = 0.60
    image_ratio_threshold: float = 0.50
    gibberish_ratio_threshold: float = 0.35
    text_coverage_threshold: float = 0.04

    # OCR 开关与后端
    enable_ocr: bool = True
    ocr_backend: str = "auto"  # auto / tesseract / paddle / baidu / tencent / none
    enable_online_ocr: bool = False
    ocr_lang: str = "chi_sim+eng"  # pytesseract 语言包
    paddle_lang: str = "ch"
    ocr_dpi: int = 220
    ocr_max_pages: Optional[int] = None
    ocr_render_max_side: int = 2600
    force_ocr_for_low_text_pages: bool = True
    ocr_timeout_seconds: int = 45
    ocr_retries: int = 1
    ocr_cache_dir: str = "./ocr_cache"
    preprocess_images: bool = True
    preprocess_version: str = "v1"
    min_ocr_confidence: float = 0.30

    # 在线 OCR：通过环境变量读取凭证，避免把密钥写死在代码里
    baidu_api_key_env: str = "BAIDU_OCR_API_KEY"
    baidu_secret_key_env: str = "BAIDU_OCR_SECRET_KEY"
    tencent_secret_id_env: str = "TENCENT_SECRET_ID"
    tencent_secret_key_env: str = "TENCENT_SECRET_KEY"
    tencent_region: str = "ap-guangzhou"
    vivo_app_id_env: str = "VIVO_OCR_APP_ID"
    vivo_app_key_env: str = "VIVO_OCR_APP_KEY"

    # 清洗
    clean_ocr_noise: bool = True
    remove_repeated_headers_footers: bool = True
    repeated_line_min_occurrences: int = 3
    enable_quality_stats: bool = True

    @classmethod
    def from_dict(cls, params: Optional[Dict[str, Any]]) -> "ExtractionConfig":
        if not params:
            return cls()
        valid = set(cls.__dataclass_fields__.keys())
        return cls(**{k: v for k, v in params.items() if k in valid})

    def __post_init__(self) -> None:
        _positive_int("scan_detect_sample_pages", self.scan_detect_sample_pages)
        _positive_int("ocr_dpi", self.ocr_dpi)
        _positive_int("ocr_render_max_side", self.ocr_render_max_side)
        _positive_int("ocr_timeout_seconds", self.ocr_timeout_seconds)
        if self.ocr_retries < 0:
            raise ConfigurationError("ocr_retries 不能为负数")
        if self.min_text_chars_per_page < 0:
            raise ConfigurationError("min_text_chars_per_page 不能为负数")
        if not (0 <= self.scan_low_text_ratio_threshold <= 1):
            raise ConfigurationError("scan_low_text_ratio_threshold 必须位于 0-1")
        if not (0 <= self.image_ratio_threshold <= 1):
            raise ConfigurationError("image_ratio_threshold 必须位于 0-1")
        if not (0 <= self.gibberish_ratio_threshold <= 1):
            raise ConfigurationError("gibberish_ratio_threshold 必须位于 0-1")
        if not (0 <= self.min_ocr_confidence <= 1):
            raise ConfigurationError("min_ocr_confidence 必须位于 0-1")
        if self.ocr_backend.lower() not in {"auto", "tesseract", "paddle", "baidu", "tencent", "vivo", "qwen_vl", "none"}:
            raise ConfigurationError(f"未知 OCR 后端: {self.ocr_backend}")


@dataclass
class SplitterConfig:
    """文本分块配置。"""

    chunk_size: int = 800
    chunk_overlap: int = 120
    min_chunk_chars: int = 80
    language: str = "zh"
    keep_page_metadata: bool = True

    # 章节识别：兼容中文教材、英文教材、编号标题
    section_pattern: str = (
        r"^\s*("
        r"第[一二三四五六七八九十百零〇0-9]+[章节篇]\s*[^\\n]{0,50}|"
        r"[0-9]+(?:\.[0-9]+){0,3}\s+[^\\n]{1,60}|"
        r"Chapter\s+[0-9IVXLC]+[^\\n]{0,60}|"
        r"§\s*[0-9]+(?:\.[0-9]+)*\s*[^\\n]{0,60}"
        r")\s*$"
    )

    def __post_init__(self) -> None:
        _positive_int("chunk_size", self.chunk_size)
        if self.chunk_overlap < 0:
            raise ConfigurationError("chunk_overlap 不能为负数")
        if self.chunk_overlap >= self.chunk_size:
            raise ConfigurationError("chunk_overlap 必须小于 chunk_size")
        if self.min_chunk_chars < 0:
            raise ConfigurationError("min_chunk_chars 不能为负数")


@dataclass
class EmbeddingConfig:
    """Embedding 配置。"""

    provider: str = "local"  # local / openai / gte / siliconflow / hash
    model_name: str = "BAAI/bge-small-zh-v1.5"
    api_key_env: str = "OPENAI_API_KEY"  # 降级用 LLM key
    api_base_env: str = "EMBEDDING_API_BASE"  # 独立 embedding API 地址
    # 实际优先从 EMBEDDING_API_KEY 读取，未设置时回退 api_key_env
    cache_dir: str = "./embedding_cache"
    batch_size: int = 16
    normalize_embeddings: bool = True
    max_input_chars: Optional[int] = None
    retries: int = 2
    retry_seconds: float = 1.0
    debug_fallback: bool = False

    def __post_init__(self) -> None:
        _positive_int("batch_size", self.batch_size)
        if self.retries < 0:
            raise ConfigurationError("retries 不能为负数")


@dataclass
class VectorStoreConfig:
    """Chroma 向量库配置。"""

    persist_dir: str = "./chroma_db"
    collection_name: str = "textbook_chunks"

    def __post_init__(self) -> None:
        if not self.collection_name.strip():
            raise ConfigurationError("collection_name 不能为空")


@dataclass
class RetrieverConfig:
    """检索配置。"""

    default_top_k: int = 5
    prefilter_top_k: int = 30
    fuzzy_threshold: int = 72
    use_chapter_filter: bool = True
    allow_fuzzy_chapter_fallback: bool = True
    allow_no_filter_fallback: bool = True
    enable_rerank: bool = False
    enable_mock_fallback: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    filter_relaxation: bool = True

    def __post_init__(self) -> None:
        _positive_int("default_top_k", self.default_top_k)
        _positive_int("prefilter_top_k", self.prefilter_top_k)
        if not (0 <= self.fuzzy_threshold <= 100):
            raise ConfigurationError("fuzzy_threshold 必须在 0-100")
