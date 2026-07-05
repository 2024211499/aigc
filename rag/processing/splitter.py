"""智能分块模块：章节识别 + 页码元数据 + 语义边界切分。"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence

from .cleaners import normalize_whitespace
from ..config import SplitterConfig

CN_NUM = "一二三四五六七八九十百零〇0-9"


def normalize_section(section: str) -> str:
    """章节归一化，用于元数据精确过滤。"""
    section = normalize_whitespace(section).lower()
    section = re.sub(r"\s+", "", section)
    section = section.replace("：", ":")
    return section


def detect_section(line: str, config: SplitterConfig) -> Optional[str]:
    """判断某行是否为章节标题。"""
    if not line:
        return None
    pattern = re.compile(config.section_pattern, re.IGNORECASE)
    m = pattern.match(line.strip())
    if not m:
        return None
    return normalize_whitespace(m.group(1))


def split_sentences(text: str, language: str = "zh") -> List[str]:
    """
    轻量句子切分，避免强依赖 sentence_splitter。
    中文按 。！？； 换行切，英文同时兼容 .?!。
    """
    text = normalize_whitespace(text)
    if not text:
        return []

    pieces: List[str] = []
    buff: List[str] = []
    terminators = set("。！？；;!?")
    for ch in text:
        buff.append(ch)
        if ch in terminators or ch == "\n":
            s = "".join(buff).strip()
            if s:
                pieces.append(s)
            buff = []
    if buff:
        tail = "".join(buff).strip()
        if tail:
            pieces.append(tail)

    # 超长句兜底硬切，防止 OCR 大段无标点导致块过大。
    final: List[str] = []
    hard_limit = 500 if language.startswith("zh") else 700
    for p in pieces:
        if len(p) <= hard_limit:
            final.append(p)
        else:
            final.extend(p[i:i + hard_limit] for i in range(0, len(p), hard_limit))
    return final


def _iter_page_sentences(pages: Sequence[Dict], cfg: SplitterConfig):
    current_section = "正文"
    for page in pages:
        page_no = page.get("page")
        lines = [normalize_whitespace(x) for x in page.get("text", "").splitlines() if normalize_whitespace(x)]
        for line in lines:
            section = detect_section(line, cfg)
            if section:
                current_section = section
                yield {
                    "text": line,
                    "page": page_no,
                    "section": current_section,
                    "is_heading": True,
                }
                continue

            for sent in split_sentences(line, cfg.language):
                yield {
                    "text": sent,
                    "page": page_no,
                    "section": current_section,
                    "is_heading": False,
                }


def split_pages_into_chunks(
    pages: Sequence[Dict],
    config: Optional[SplitterConfig] = None,
) -> List[Dict]:
    """
    将逐页文本分块，输出适合入库的 chunk 字典：
    text, section, section_norm, page_start, page_end, chunk_index。
    """
    cfg = config or SplitterConfig()
    chunks: List[Dict] = []
    cur_parts: List[str] = []
    cur_len = 0
    cur_section = "正文"
    page_start = None
    page_end = None

    def flush() -> None:
        nonlocal cur_parts, cur_len, page_start, page_end, cur_section
        text = normalize_whitespace("\n".join(cur_parts))
        if len(text) >= cfg.min_chunk_chars or (text and not chunks):
            chunks.append({
                "text": text,
                "section": cur_section,
                "section_norm": normalize_section(cur_section),
                "page_start": page_start,
                "page_end": page_end,
                "chunk_index": len(chunks),
                "char_count": len(text),
            })

        if cfg.chunk_overlap > 0 and text:
            overlap = text[-cfg.chunk_overlap:]
            cur_parts = [overlap]
            cur_len = len(overlap)
            page_start = page_end
        else:
            cur_parts = []
            cur_len = 0
            page_start = None

    for item in _iter_page_sentences(pages, cfg):
        sent = item["text"]
        if item["section"]:
            cur_section = item["section"]
        sent_len = len(sent)

        if page_start is None:
            page_start = item.get("page")
        page_end = item.get("page")

        if cur_len and cur_len + sent_len > cfg.chunk_size:
            flush()

        cur_parts.append(sent)
        cur_len += sent_len

    if cur_parts:
        flush()

    return chunks


def split_text_into_chunks(text: str, config: Optional[SplitterConfig] = None) -> List[Dict]:
    """兼容原接口：输入整段文本，无页码。"""
    pages = [{"page": None, "text": text, "method": "text", "char_count": len(text or "")}]
    return split_pages_into_chunks(pages, config)
