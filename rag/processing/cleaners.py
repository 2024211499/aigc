"""文本清洗模块：尤其针对 OCR 常见噪声做专项处理。"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Dict, Iterable, List, Sequence, Tuple

from ..models import CleanStats


CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MULTI_SPACE_RE = re.compile(r"[ \t　]+")
PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:第?\s*\d+\s*页?|[-—–]?\s*\d+\s*[-—–]?|\d+\s*/\s*\d+|Page\s+\d+(?:\s+of\s+\d+)?)\s*$",
    re.IGNORECASE,
)
NOISE_SYMBOL_RE = re.compile(r"^[\W_]{4,}$", re.UNICODE)
BROKEN_HYPHEN_RE = re.compile(r"([A-Za-z])-\n([A-Za-z])")
MANY_DOTS_RE = re.compile(r"[.·•]{5,}")
MANY_UNDERSCORES_RE = re.compile(r"[_＿]{3,}")
MATH_SPACE_RE = re.compile(r"\s*([=+\-*/^<>≤≥≈≠∫∑∏√∞∂∆Δπλμθαβγ（）()\[\]{}])\s*")
LATEX_BLOCK_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))", re.DOTALL)


def normalize_unicode(text: str) -> str:
    """统一 Unicode 形态，减少全角半角与兼容字符带来的检索噪声。"""
    return unicodedata.normalize("NFKC", text or "")


def remove_control_chars(text: str) -> str:
    return CONTROL_RE.sub("", text or "")


def normalize_whitespace(text: str) -> str:
    text = MULTI_SPACE_RE.sub(" ", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def gibberish_ratio(text: str) -> float:
    """Estimate how much of a text is non-meaningful symbols."""
    if not text:
        return 0.0
    meaningful = re.findall(r"[一-鿿A-Za-z0-9=+\-*/^<>≤≥≈≠∫∑∏√∞]", text)
    return 1.0 - (len(meaningful) / max(len(text), 1))


def compute_text_quality(text: str) -> Dict:
    """Compute quality metrics used by parsing, cleaning and chunking."""
    text = text or ""
    suspicious = gibberish_ratio(text)
    meaningful_chars = len(re.findall(r"[一-鿿A-Za-z0-9]", text))
    lines = [x for x in text.splitlines() if x.strip()]
    very_short_ratio = sum(1 for x in lines if len(x.strip()) <= 2) / max(len(lines), 1)
    quality = max(0.0, min(1.0, 1.0 - suspicious * 0.75 - very_short_ratio * 0.25))
    return {
        "before_chars": len(text),
        "after_chars": len(text),
        "suspicious_char_ratio": suspicious,
        "gibberish_ratio": suspicious,
        "meaningful_chars": meaningful_chars,
        "line_count": len(lines),
        "quality_score": quality,
    }


def is_probable_gibberish(line: str) -> bool:
    """
    判断 OCR 乱码行。
    保守策略：只删除几乎没有中英文数字、且符号占比极高的短行。
    """
    s = line.strip()
    if not s:
        return True
    if PAGE_NUMBER_RE.match(s):
        return True
    if NOISE_SYMBOL_RE.match(s):
        return True

    meaningful = re.findall(r"[一-鿿A-Za-z0-9]", s)
    if len(s) <= 4 and not meaningful:
        return True

    ratio = len(meaningful) / max(len(s), 1)
    return len(s) >= 8 and ratio < 0.18


def clean_ocr_text(text: str) -> str:
    """
    清洗 OCR 结果：
    - 去除控制字符、目录点线、连续下划线；
    - 去掉单独页码、明显符号噪声；
    - 修复英文断词换行；
    - 合并重复空行。
    """
    text = normalize_unicode(text)
    text = remove_control_chars(text)
    text = BROKEN_HYPHEN_RE.sub(r"\1\2", text)
    text = MANY_DOTS_RE.sub(" ", text)
    text = MANY_UNDERSCORES_RE.sub(" ", text)

    cleaned_lines: List[str] = []
    previous = None
    for raw in text.splitlines():
        line = normalize_whitespace(raw)
        if not line or is_probable_gibberish(line):
            continue
        # OCR 常见同一行重复识别：只折叠相邻重复，避免误删公式/列表。
        if line == previous:
            continue
        cleaned_lines.append(line)
        previous = line

    return normalize_whitespace("\n".join(cleaned_lines))


def basic_clean(text: str, *, return_stats: bool = False):
    """Basic cleaning shared by all parsers."""
    raw = text or ""
    text = normalize_unicode(raw)
    text = remove_control_chars(text)
    lines = [normalize_whitespace(x) for x in text.splitlines()]
    kept = [x for x in lines if x]
    cleaned = normalize_whitespace("\n".join(kept))
    stats = CleanStats(
        before_chars=len(raw),
        after_chars=len(cleaned),
        raw_chars=len(raw),
        cleaned_chars=len(cleaned),
        removed_lines=max(0, len(lines) - len(kept)),
        suspicious_char_ratio=gibberish_ratio(cleaned),
        gibberish_ratio=gibberish_ratio(cleaned),
        quality_score=compute_text_quality(cleaned)["quality_score"],
    )
    return (cleaned, stats) if return_stats else cleaned


def clean_basic_text(text: str, *, return_stats: bool = False):
    """Public basic cleaner."""
    return basic_clean(text, return_stats=return_stats)


def clean_ocr_text_with_stats(text: str) -> Tuple[str, CleanStats]:
    """OCR-specific cleaning with quality stats."""
    raw = text or ""
    text = normalize_unicode(raw)
    text = remove_control_chars(text)
    text = BROKEN_HYPHEN_RE.sub(r"\1\2", text)
    text = MANY_DOTS_RE.sub(" ", text)
    text = MANY_UNDERSCORES_RE.sub(" ", text)

    lines = text.splitlines()
    cleaned_lines: List[str] = []
    previous = None
    removed = 0
    for raw_line in lines:
        line = normalize_whitespace(raw_line)
        if not line or is_probable_gibberish(line):
            removed += 1
            continue
        if line == previous:
            removed += 1
            continue
        cleaned_lines.append(line)
        previous = line
    cleaned = normalize_whitespace("\n".join(cleaned_lines))
    cleaned = normalize_math_text(cleaned)
    return cleaned, CleanStats(
        before_chars=len(raw),
        after_chars=len(cleaned),
        raw_chars=len(raw),
        cleaned_chars=len(cleaned),
        removed_lines=removed,
        suspicious_char_ratio=gibberish_ratio(cleaned),
        gibberish_ratio=gibberish_ratio(cleaned),
        quality_score=compute_text_quality(cleaned)["quality_score"],
    )


def clean_textbook_text(text: str, *, return_stats: bool = False):
    """Textbook-aware cleanup: remove repeated catalog dots/watermark-like noise while keeping formulas."""
    cleaned, stats = basic_clean(text, return_stats=True)
    lines: List[str] = []
    removed = stats.removed_lines
    for line in cleaned.splitlines():
        stripped = normalize_whitespace(line)
        if not stripped:
            removed += 1
            continue
        if re.match(r"^(目录|CONTENTS?)\s*$", stripped, re.IGNORECASE):
            removed += 1
            continue
        if re.search(r"(仅供学习|扫码|水印|公众号|版权所有|未经许可)", stripped) and len(stripped) < 80:
            removed += 1
            continue
        lines.append(stripped)
    final = normalize_math_text("\n".join(lines))
    stats = CleanStats(
        before_chars=stats.raw_chars,
        after_chars=len(final),
        raw_chars=stats.raw_chars,
        cleaned_chars=len(final),
        removed_lines=removed,
        suspicious_char_ratio=gibberish_ratio(final),
        gibberish_ratio=gibberish_ratio(final),
        quality_score=compute_text_quality(final)["quality_score"],
    )
    return (final, stats) if return_stats else final


def clean_textbook_noise(text: str, *, return_stats: bool = False):
    """Public textbook noise cleaner."""
    return clean_textbook_text(text, return_stats=return_stats)


def clean_plain_text(text: str) -> str:
    """对普通文本型 PDF / Word 的轻量清洗。"""
    return basic_clean(text)


def normalize_math_text(text: str) -> str:
    """
    尽量保留并规整数学表达式。

    这里不做激进重写，避免把教材里的公式改坏；只处理 OCR/排版里最常见的
    数学符号误差和符号周围的多余空格。
    """
    if not text:
        return ""

    protected: List[str] = []

    def keep_latex(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"__LATEX_BLOCK_{len(protected) - 1}__"

    text = LATEX_BLOCK_RE.sub(keep_latex, text)
    replacements = {
        "lim ": "lim ",
        "l i m": "lim",
        "s i n": "sin",
        "c o s": "cos",
        "t a n": "tan",
        "ln ": "ln ",
        "∫ ": "∫",
        "Σ": "∑",
        "Π": "∏",
        "—": "-",
        "−": "-",
        "×": "*",
        "÷": "/",
        "≤": "≤",
        "≥": "≥",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = MATH_SPACE_RE.sub(r"\1", text)
    text = re.sub(r"([A-Za-z0-9一-鿿])([=<>≤≥≈≠])", r"\1 \2", text)
    text = re.sub(r"([=<>≤≥≈≠])([A-Za-z0-9一-鿿])", r"\1 \2", text)

    for idx, block in enumerate(protected):
        text = text.replace(f"__LATEX_BLOCK_{idx}__", block)
    return normalize_whitespace(text)


def clean_math_text(text: str) -> str:
    """Public math-preserving cleaner."""
    return normalize_math_text(text)


def clean_text(raw_text: str) -> str:
    """
    对外统一清洗入口。

    适用于 PDF 文本、Word/PPT 文本、OCR 结果的二次清理，并保留数学符号。
    """
    return clean_textbook_text(raw_text or "")


def _candidate_edge_lines(page_text: str) -> List[str]:
    """提取每页页眉页脚候选行。"""
    lines = [normalize_whitespace(x) for x in page_text.splitlines() if normalize_whitespace(x)]
    if not lines:
        return []
    candidates = []
    candidates.extend(lines[:2])
    candidates.extend(lines[-2:])
    return [x for x in candidates if len(x) <= 80 and not PAGE_NUMBER_RE.match(x)]


def remove_repeated_headers_footers_from_pages(
    pages: Sequence[Dict],
    min_occurrences: int = 3,
) -> List[Dict]:
    """
    根据多页重复边缘行删除页眉页脚。
    pages 元素需至少包含 {"text": "..."}，会返回新的列表，不原地修改。
    """
    if len(pages) < min_occurrences:
        return list(pages)

    counter: Counter[str] = Counter()
    for page in pages:
        counter.update(_candidate_edge_lines(page.get("text", "")))

    repeated = {
        line for line, count in counter.items()
        if count >= min_occurrences and len(line) >= 3
    }
    if not repeated:
        return list(pages)

    new_pages: List[Dict] = []
    for page in pages:
        lines = [normalize_whitespace(x) for x in page.get("text", "").splitlines()]
        lines = [x for x in lines if x and x not in repeated and not PAGE_NUMBER_RE.match(x)]
        new_page = dict(page)
        new_page["text"] = normalize_whitespace("\n".join(lines))
        new_pages.append(new_page)
    return new_pages


def clean_document_pages(pages: Sequence[Dict], min_occurrences: int = 2) -> List[Dict]:
    """
    Clean pages with document-level repeated header/footer detection.

    Input pages may contain raw_text, cleaned_text or text. Output pages always contain
    raw_text, cleaned_text, text and quality_stats.
    """
    prepared: List[Dict] = []
    for page in pages:
        raw = page.get("raw_text", page.get("text", "")) or ""
        method = str(page.get("extraction_method", page.get("method", ""))).lower()
        if "ocr" in method:
            cleaned, stats = clean_ocr_text_with_stats(raw)
        else:
            cleaned, stats = clean_textbook_text(raw, return_stats=True)
        item = dict(page)
        item["raw_text"] = raw
        item["cleaned_text"] = cleaned
        item["text"] = cleaned
        item["char_count"] = len(cleaned)
        item["quality_stats"] = {**item.get("quality_stats", {}), **stats.to_dict()}
        prepared.append(item)

    if len(prepared) < min_occurrences:
        return prepared

    counter: Counter[str] = Counter()
    for page in prepared:
        counter.update(_candidate_edge_lines(page.get("cleaned_text", "")))
    repeated = {
        line for line, count in counter.items()
        if count >= min_occurrences and len(line) >= 3
    }
    if not repeated:
        return prepared

    output: List[Dict] = []
    for page in prepared:
        removed = 0
        lines = []
        for line in page.get("cleaned_text", "").splitlines():
            clean_line = normalize_whitespace(line)
            if clean_line in repeated:
                removed += 1
                continue
            lines.append(clean_line)
        cleaned = normalize_whitespace("\n".join(lines))
        item = dict(page)
        item["cleaned_text"] = cleaned
        item["text"] = cleaned
        item["char_count"] = len(cleaned)
        stats = dict(item.get("quality_stats", {}))
        stats["duplicate_header_footer_lines"] = int(stats.get("duplicate_header_footer_lines", 0)) + removed
        stats["after_chars"] = len(cleaned)
        stats["cleaned_chars"] = len(cleaned)
        stats["quality_score"] = compute_text_quality(cleaned)["quality_score"]
        item["quality_stats"] = stats
        output.append(item)
    return output


def clean_pages(pages: Sequence[Dict], ocr_methods: Iterable[str] = ("ocr",)) -> List[Dict]:
    """
    按页清洗。method 包含 ocr 的页走 OCR 清洗，否则走普通清洗。
    """
    ocr_methods = set(ocr_methods)
    result: List[Dict] = []
    for page in pages:
        method = str(page.get("method", "")).lower()
        text = page.get("text", "")
        if any(m in method for m in ocr_methods):
            cleaned, stats = clean_ocr_text_with_stats(text)
        else:
            cleaned, stats = clean_textbook_text(text, return_stats=True)
        if cleaned:
            new_page = dict(page)
            new_page["text"] = cleaned
            new_page["char_count"] = len(cleaned)
            new_page["text_length"] = len(cleaned)
            new_page["quality_stats"] = stats.to_dict()
            result.append(new_page)
    return result
