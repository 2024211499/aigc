"""结构化分块与元数据构建。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from .cleaners import clean_text, normalize_whitespace
from ..knowledge.extractor import estimate_difficulty, extract_formulas, tag_knowledge_points
from .structure import classify_block_type, detect_chapters, iter_typed_blocks


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_chunk_id(course_id: str, document_id: str, index: int, text: str) -> str:
    digest = hashlib.md5(f"{course_id}:{document_id}:{index}:{text[:200]}".encode("utf-8", errors="ignore")).hexdigest()
    return f"chunk_{digest[:16]}"


def sentence_splitter(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """对长文本继续切分，优先按句号、问号、分号和换行边界。"""
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    pieces: List[str] = []
    buff: List[str] = []
    for ch in text:
        buff.append(ch)
        if ch in "。！？；;!?\n":
            s = "".join(buff).strip()
            if s:
                pieces.append(s)
            buff = []
    if buff:
        pieces.append("".join(buff).strip())

    chunks: List[str] = []
    cur = ""
    for piece in pieces:
        if len(piece) > chunk_size:
            if cur:
                chunks.append(cur)
                cur = ""
            for i in range(0, len(piece), max(1, chunk_size - overlap)):
                chunks.append(piece[i:i + chunk_size])
            continue

        if cur and len(cur) + len(piece) > chunk_size:
            chunks.append(cur)
            cur = cur[-overlap:] + piece if overlap > 0 else piece
        else:
            cur += ("\n" if cur else "") + piece
    if cur:
        chunks.append(cur)
    return [normalize_whitespace(x) for x in chunks if normalize_whitespace(x)]


def _contains_example(text: str) -> bool:
    return bool(re.search(r"(^|\n)\s*(例题?|例\s*[0-9一二三四五六七八九十]*|Example)\b", text, re.IGNORECASE))


def _contains_exercise(text: str) -> bool:
    return bool(re.search(r"(^|\n)\s*(习题|练习|作业|选择题|填空题|解答题|Exercises?)\b", text, re.IGNORECASE))


def build_chunk_metadata(
    *,
    text: str,
    chunk_index: int,
    course_id: str,
    document_id: str,
    file_name: str,
    source_path: str,
    course_name: Optional[str] = None,
    chapter_id: Optional[str] = None,
    chapter_name: Optional[str] = None,
    section_name: Optional[str] = None,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    content_type: Optional[str] = None,
    subsection: Optional[str] = None,
    source_refs: Optional[Sequence[Dict]] = None,
    source_quality_score: float = 1.0,
    start_offset: int = 0,
    end_offset: Optional[int] = None,
    knowledge_points: Optional[Sequence[str]] = None,
    difficulty: Optional[str] = None,
    is_ocr: bool = False,
    extra: Optional[Dict] = None,
) -> Dict:
    """生成每个 chunk 的完整元数据。"""
    text = clean_text(text)
    formulas = extract_formulas(text)
    chunk_type = content_type or classify_block_type(text)
    example_match = re.search(r"(例题?|例\s*\d+|Example\s*\d+)", text, re.IGNORECASE)
    exercise_match = re.search(r"(习题\s*[\d\-一二三四五六七八九十]*|Exercises?)", text, re.IGNORECASE)
    metadata = {
        "chunk_id": _stable_chunk_id(course_id, document_id, chunk_index, text),
        "course_id": course_id,
        "document_id": document_id,
        "doc_id": document_id,
        "file_name": file_name,
        "doc_name": file_name,
        "course_name": course_name or course_id,
        "chapter_id": chapter_id or "chapter_000",
        "chapter_name": chapter_name or "正文",
        "chapter": chapter_name or "正文",
        "section_name": section_name or chapter_name or "正文",
        "section": section_name or chapter_name or "正文",
        "subsection": subsection or "",
        "page_start": page_start,
        "page_end": page_end,
        "content_type": chunk_type,
        "chunk_type": chunk_type,
        "knowledge_points": list(knowledge_points or []),
        "example_id": _stable_chunk_id(course_id, document_id, chunk_index, example_match.group(0)) if example_match else "",
        "exercise_id": _stable_chunk_id(course_id, document_id, chunk_index, exercise_match.group(0)) if exercise_match else "",
        "difficulty": difficulty or estimate_difficulty(text),
        "source_path": os.path.abspath(source_path) if source_path else "",
        "source_refs": list(source_refs or []),
        "created_at": _now_iso(),
        "text": text,
        "embedding_id": "",
        "is_ocr": bool(is_ocr),
        "is_ocr_text": bool(is_ocr),
        "has_formula": bool(formulas),
        "has_example": _contains_example(text),
        "has_exercise": _contains_exercise(text),
        "formula_count": len(formulas),
        "source_quality_score": source_quality_score,
        "start_offset": start_offset,
        "end_offset": len(text) if end_offset is None else end_offset,
        "char_count": len(text),
    }
    if extra:
        metadata.update(extra)
    return metadata


def _heading_from_line(line: str) -> Optional[str]:
    """Return a chapter/section heading if the line looks like one."""
    line = normalize_whitespace(line)
    if not line or len(line) > 96:
        return None
    patterns = [
        r"^第[一二三四五六七八九十百零〇0-9]+[章节篇编]\s*[^。；;]{0,80}$",
        r"^[0-9]+(?:\.[0-9]+){1,4}\s*[^。；;]{0,80}$",
        r"^§\s*[0-9]+(?:\.[0-9]+)*\s*[^。；;]{0,80}$",
        r"^(?:Chapter|CHAPTER|Section)\s+[0-9IVXLC]+[^。；;]{0,80}$",
    ]
    return line if any(re.match(pattern, line) for pattern in patterns) else None


def _is_chapter_heading(line: str) -> bool:
    return bool(re.match(r"^\s*(第[一二三四五六七八九十百零〇0-9]+[章篇编]|(?:Chapter|CHAPTER)\s+[0-9IVXLC]+)", line or ""))


def _is_section_heading(line: str) -> bool:
    return bool(_heading_from_line(line)) and not _is_chapter_heading(line)


def _page_quality(page: Dict) -> float:
    stats = page.get("quality_stats") or {}
    try:
        return float(stats.get("quality_score", 1.0))
    except Exception:
        return 1.0


def _page_number(page: Dict, default: int) -> int:
    value = page.get("page_number", page.get("page", default))
    try:
        return int(value)
    except Exception:
        return default


def split_pages_by_structure(
    pages: Sequence[Dict],
    *,
    course_id: str = "default_course",
    document_id: str = "default_document",
    file_name: str = "",
    source_path: str = "",
    course_name: Optional[str] = None,
    chunk_size: int = 800,
    overlap: int = 100,
) -> List[Dict]:
    """
    Page-first structure-aware chunking.

    This implementation deliberately keeps every chunk tied to the real source
    page(s).  It avoids the old prototype behavior of joining the whole document
    and then assigning a broad chapter page range to every fragment, which made
    citations less trustworthy.
    """
    fragments: List[Dict] = []
    current_chapter = "正文"
    current_chapter_id = "chapter_000"
    current_section = "正文"
    chapter_counter = 0
    global_offset = 0

    for page_idx, page in enumerate(pages, start=1):
        page_no = _page_number(page, page_idx)
        raw_text = clean_text(page.get("text") or page.get("cleaned_text") or "")
        if not raw_text:
            continue

        # Update chapter/section state from headings on this page before chunking.
        for line in raw_text.splitlines():
            heading = _heading_from_line(line)
            if not heading:
                continue
            if _is_chapter_heading(heading):
                chapter_counter += 1
                current_chapter = heading
                current_chapter_id = f"chapter_{chapter_counter:03d}"
                current_section = heading
            elif _is_section_heading(heading):
                current_section = heading

        blocks = iter_typed_blocks(raw_text) or [{"content_type": classify_block_type(raw_text), "text": raw_text}]
        for block in blocks:
            block_text = block.get("text", "")
            if not block_text.strip():
                continue

            # A block may itself start with a new heading; update state precisely.
            first_line = normalize_whitespace(block_text.splitlines()[0]) if block_text.splitlines() else ""
            heading = _heading_from_line(first_line)
            if heading:
                if _is_chapter_heading(heading):
                    if heading != current_chapter:
                        chapter_counter += 1
                    current_chapter = heading
                    current_chapter_id = f"chapter_{chapter_counter:03d}"
                    current_section = heading
                elif _is_section_heading(heading):
                    current_section = heading

            parts = sentence_splitter(block_text, chunk_size=chunk_size, overlap=overlap)
            search_from = 0
            for part in parts:
                part = normalize_whitespace(part)
                if not part:
                    continue
                rel_start = block_text.find(part, search_from)
                if rel_start < 0:
                    rel_start = search_from
                rel_end = rel_start + len(part)
                search_from = max(rel_start + 1, rel_end - overlap)
                extraction_method = page.get("extraction_method", page.get("method", ""))
                source_ref = {
                    "doc_id": document_id,
                    "doc_name": file_name,
                    "page": page_no,
                    "extraction_method": extraction_method,
                    "is_ocr_text": bool(page.get("is_ocr") or page.get("is_ocr_text") or "ocr" in str(extraction_method)),
                }
                fragments.append(build_chunk_metadata(
                    text=part,
                    chunk_index=len(fragments),
                    course_id=course_id,
                    document_id=document_id,
                    file_name=file_name,
                    course_name=course_name,
                    source_path=source_path,
                    chapter_id=current_chapter_id,
                    chapter_name=current_chapter,
                    section_name=current_section,
                    page_start=page_no,
                    page_end=page_no,
                    content_type=block.get("content_type"),
                    source_refs=[source_ref],
                    source_quality_score=_page_quality(page),
                    start_offset=global_offset + rel_start,
                    end_offset=global_offset + rel_end,
                    is_ocr=source_ref["is_ocr_text"],
                ))
        global_offset += len(raw_text) + 2

    return tag_knowledge_points(fragments)

def split_by_structure(
    document_text: str,
    outline: Optional[Dict],
    *,
    course_id: str = "default_course",
    document_id: str = "default_document",
    file_name: str = "",
    source_path: str = "",
    course_name: Optional[str] = None,
    chunk_size: int = 800,
    overlap: int = 100,
    is_ocr: bool = False,
) -> List[Dict]:
    """
    先根据章节/小节/语义块切分，过长内容再按句子切分。
    """
    if not outline:
        outline = {"chapters": detect_chapters(document_text)}
    chapters = outline.get("chapters", []) or detect_chapters(document_text)
    fragments: List[Dict] = []

    for chapter in chapters:
        chapter_text = chapter.get("text", "")
        sections = chapter.get("sections") or [{
            "section_name": chapter.get("chapter_name", "正文"),
            "text": chapter_text,
        }]
        for section in sections:
            blocks = iter_typed_blocks(section.get("text", "")) or [{
                "content_type": classify_block_type(section.get("text", "")),
                "text": section.get("text", ""),
            }]
            for block in blocks:
                block_text = block.get("text", "")
                parts = sentence_splitter(block_text, chunk_size=chunk_size, overlap=overlap)
                search_from = 0
                for part in parts:
                    if len(part) < 6 and fragments:
                        continue
                    rel_start = block_text.find(part, search_from)
                    if rel_start < 0:
                        rel_start = search_from
                    rel_end = rel_start + len(part)
                    search_from = max(rel_start + 1, rel_end - overlap)
                    fragments.append(build_chunk_metadata(
                        text=part,
                        chunk_index=len(fragments),
                        course_id=course_id,
                        document_id=document_id,
                        file_name=file_name,
                        course_name=course_name,
                        source_path=source_path,
                        chapter_id=chapter.get("chapter_id"),
                        chapter_name=chapter.get("chapter_name"),
                        section_name=section.get("section_name"),
                        page_start=chapter.get("page_start"),
                        page_end=chapter.get("page_end"),
                        content_type=block.get("content_type"),
                        start_offset=rel_start,
                        end_offset=rel_end,
                        is_ocr=is_ocr,
                    ))

    return tag_knowledge_points(fragments)


def fragments_to_jsonl(fragments: Sequence[Dict]) -> str:
    """便于调试或导出的 JSONL。"""
    return "\n".join(json.dumps(f, ensure_ascii=False) for f in fragments)


__all__ = [
    "split_by_structure",
    "split_pages_by_structure",
    "sentence_splitter",
    "build_chunk_metadata",
    "fragments_to_jsonl",
]
