"""Stable data contracts for the course knowledge base."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class CleanStats:
    before_chars: int = 0
    after_chars: int = 0
    raw_chars: int = 0
    cleaned_chars: int = 0
    removed_lines: int = 0
    duplicate_header_footer_lines: int = 0
    suspicious_char_ratio: float = 0.0
    gibberish_ratio: float = 0.0
    quality_score: float = 1.0

    def to_dict(self) -> Dict:
        data = asdict(self)
        if not data["before_chars"]:
            data["before_chars"] = data["raw_chars"]
        if not data["after_chars"]:
            data["after_chars"] = data["cleaned_chars"]
        if not data["raw_chars"]:
            data["raw_chars"] = data["before_chars"]
        if not data["cleaned_chars"]:
            data["cleaned_chars"] = data["after_chars"]
        if not data["suspicious_char_ratio"]:
            data["suspicious_char_ratio"] = data["gibberish_ratio"]
        if not data["gibberish_ratio"]:
            data["gibberish_ratio"] = data["suspicious_char_ratio"]
        return data


@dataclass
class PageParseResult:
    page_number: Optional[int]
    text: str
    extraction_method: str
    raw_text: str = ""
    cleaned_text: str = ""
    ocr_backend: str = ""
    ocr_confidence: Optional[float] = None
    is_scanned_page: bool = False
    failure_reason: str = ""
    quality_stats: Dict = field(default_factory=dict)
    image_count: int = 0
    image_coverage: float = 0.0
    text_length: int = 0

    def to_dict(self) -> Dict:
        data = asdict(self)
        cleaned = self.cleaned_text or self.text or ""
        raw = self.raw_text if self.raw_text != "" else self.text
        data["raw_text"] = raw
        data["cleaned_text"] = cleaned
        data["text"] = cleaned
        data["page"] = self.page_number
        data["method"] = self.extraction_method
        data["char_count"] = self.text_length or len(cleaned)
        data["is_ocr"] = "ocr" in self.extraction_method
        data["is_ocr_text"] = data["is_ocr"]
        return data


@dataclass
class RetrievalHit:
    text: str
    score: float
    source: str
    doc_name: str
    chapter: str
    section: str
    page_start: Optional[int]
    page_end: Optional[int]
    chunk_type: str
    retrieval_method: str
    why_matched: str
    citation: str
    chunk_id: str = ""
    doc_id: str = ""
    course_id: str = ""
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0
    source_quality_score: float = 1.0

    def to_dict(self) -> Dict:
        return asdict(self)


def page_from_dict(page: Dict) -> PageParseResult:
    text = page.get("text", "") or ""
    return PageParseResult(
        page_number=page.get("page_number", page.get("page")),
        text=text,
        extraction_method=page.get("extraction_method", page.get("method", "")),
        ocr_backend=page.get("ocr_backend", ""),
        ocr_confidence=page.get("ocr_confidence"),
        is_scanned_page=bool(page.get("is_scanned_page", False)),
        failure_reason=page.get("failure_reason", page.get("error", "")) or "",
        quality_stats=page.get("quality_stats", {}) or {},
        image_count=int(page.get("image_count") or 0),
        image_coverage=float(page.get("image_coverage") or 0.0),
        text_length=int(page.get("text_length") or page.get("char_count") or len(text)),
    )
