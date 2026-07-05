"""章节、小节与内容块结构识别。"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from rapidfuzz import fuzz, process

from .cleaners import clean_text, normalize_whitespace


CN_NUM = "一二三四五六七八九十百千万零〇两0-9"
CHAPTER_RE = re.compile(
    rf"^\s*(?P<title>(?:第[{CN_NUM}]+[章节篇编]\s*[^。\n]{{0,80}})|"
    r"(?:Chapter|CHAPTER)\s+[0-9IVXLC]+[^\n]{0,80}|"
    r"(?:[0-9]{1,2})\s+[^\n。]{2,60})\s*$"
)
SECTION_RE = re.compile(
    rf"^\s*(?P<title>(?:[0-9]+(?:\.[0-9]+){{1,4}}\s*[^。\n]{{0,80}})|"
    rf"(?:[{CN_NUM}]+[、.．]\s*[^。\n]{{1,80}})|"
    r"(?:§\s*[0-9]+(?:\.[0-9]+)*\s*[^\n]{0,80})|"
    r"(?:Section\s+[0-9IVXLC]+[^\n]{0,80}))\s*$"
)
BLOCK_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("definition", re.compile(r"^\s*(定义|概念|记作|称为|所谓|Definition)\b", re.IGNORECASE)),
    ("theorem", re.compile(r"^\s*(定理|引理|推论|命题|性质|法则|公式|Theorem|Lemma)\b", re.IGNORECASE)),
    ("example", re.compile(r"^\s*(例题?|例\s*[0-9一二三四五六七八九十]*|Example)\b", re.IGNORECASE)),
    ("proof", re.compile(r"^\s*(证明|证|Proof)\b", re.IGNORECASE)),
    ("exercise", re.compile(r"^\s*(习题|练习|作业|思考题|选择题|填空题|解答题|Exercises?)\b", re.IGNORECASE)),
    ("summary", re.compile(r"^\s*(小结|总结|本章小结|复习|Summary)\b", re.IGNORECASE)),
]


def _coerce_pages(text_pages: Union[str, Sequence[Dict], Sequence[str]]) -> List[Dict]:
    if isinstance(text_pages, str):
        return [{"page": None, "text": clean_text(text_pages), "method": "text"}]
    pages: List[Dict] = []
    for idx, item in enumerate(text_pages, start=1):
        if isinstance(item, dict):
            page = dict(item)
            page.setdefault("page", idx)
            page["text"] = clean_text(page.get("text", ""))
            pages.append(page)
        else:
            pages.append({"page": idx, "text": clean_text(str(item)), "method": "text"})
    return pages


def _iter_lines_with_pages(pages: Sequence[Dict]) -> List[Dict]:
    lines: List[Dict] = []
    line_no = 0
    for page in pages:
        page_no = page.get("page")
        for raw in str(page.get("text", "")).splitlines():
            text = normalize_whitespace(raw)
            if not text:
                continue
            lines.append({"line_no": line_no, "page": page_no, "text": text})
            line_no += 1
    return lines


def _is_probable_heading(line: str) -> bool:
    if len(line) > 96:
        return False
    if line.count("。") + line.count("，") + line.count(",") >= 2:
        return False
    return True


def _detect_chapter_title(line: str) -> Optional[str]:
    if not _is_probable_heading(line):
        return None
    match = CHAPTER_RE.match(line)
    return normalize_whitespace(match.group("title")) if match else None


def _detect_section_title(line: str) -> Optional[str]:
    if not _is_probable_heading(line):
        return None
    match = SECTION_RE.match(line)
    return normalize_whitespace(match.group("title")) if match else None


def detect_chapters(text_pages: Union[str, Sequence[Dict], Sequence[str]]) -> List[Dict]:
    """
    从全文或页级文本中识别章标题，并返回带正文范围的章节列表。

    返回字段包括 chapter_id、chapter_name、page_start、page_end、text、sections。
    """
    pages = _coerce_pages(text_pages)
    lines = _iter_lines_with_pages(pages)
    markers: List[Dict] = []
    for item in lines:
        title = _detect_chapter_title(item["text"])
        if title:
            markers.append({**item, "title": title})

    if not lines:
        return []

    if not markers:
        full_text = "\n".join(line["text"] for line in lines)
        return [{
            "chapter_id": "chapter_001",
            "chapter_name": "正文",
            "title": "正文",
            "level": "chapter",
            "page_start": lines[0].get("page"),
            "page_end": lines[-1].get("page"),
            "line_start": lines[0]["line_no"],
            "line_end": lines[-1]["line_no"],
            "text": full_text,
            "sections": detect_sections(full_text),
        }]

    chapters: List[Dict] = []
    for idx, marker in enumerate(markers):
        next_line_no = markers[idx + 1]["line_no"] if idx + 1 < len(markers) else lines[-1]["line_no"] + 1
        body_lines = [line for line in lines if marker["line_no"] <= line["line_no"] < next_line_no]
        if not body_lines:
            continue
        text = "\n".join(line["text"] for line in body_lines)
        chapters.append({
            "chapter_id": f"chapter_{idx + 1:03d}",
            "chapter_name": marker["title"],
            "title": marker["title"],
            "level": "chapter",
            "page_start": body_lines[0].get("page"),
            "page_end": body_lines[-1].get("page"),
            "line_start": body_lines[0]["line_no"],
            "line_end": body_lines[-1]["line_no"],
            "text": text,
            "sections": detect_sections(text),
        })
    return chapters


def detect_sections(chapter_text: str) -> List[Dict]:
    """识别小节标题，例如 1.1、1.2、一、二、三。"""
    lines = [normalize_whitespace(x) for x in str(chapter_text or "").splitlines() if normalize_whitespace(x)]
    markers: List[Dict] = []
    for idx, line in enumerate(lines):
        title = _detect_section_title(line)
        if title:
            markers.append({"section_id": f"section_{len(markers) + 1:03d}", "section_name": title, "line_start": idx})

    if not markers and lines:
        return [{
            "section_id": "section_001",
            "section_name": "正文",
            "line_start": 0,
            "line_end": len(lines) - 1,
            "text": "\n".join(lines),
        }]

    sections: List[Dict] = []
    for idx, marker in enumerate(markers):
        end = markers[idx + 1]["line_start"] - 1 if idx + 1 < len(markers) else len(lines) - 1
        text = "\n".join(lines[marker["line_start"]:end + 1])
        sections.append({**marker, "line_end": end, "text": text})
    return sections


def classify_block_type(text_block: str) -> str:
    """
    判断文本块类型：概念定义、公式定理、例题解析、证明、习题、小结或普通讲解。
    """
    text = normalize_whitespace(text_block)
    if not text:
        return "empty"
    first_line = text.splitlines()[0] if "\n" in text else text[:80]
    for block_type, pattern in BLOCK_PATTERNS:
        if pattern.search(first_line) or pattern.search(text[:160]):
            return block_type
    if re.search(r"(\$.*?\$|\\frac|\\sum|\\int|[=<>≤≥≈≠]|∫|∑|√|lim)", text):
        return "formula"
    return "explanation"


def iter_typed_blocks(section_text: str) -> List[Dict]:
    """按定义、定理、例题、证明、习题等语义边界拆分小节。"""
    lines = [normalize_whitespace(x) for x in str(section_text or "").splitlines() if normalize_whitespace(x)]
    if not lines:
        return []

    blocks: List[Dict] = []
    cur: List[str] = []
    cur_type = "explanation"

    def flush() -> None:
        nonlocal cur, cur_type
        if not cur:
            return
        text = "\n".join(cur)
        block_type = cur_type if cur_type != "explanation" else classify_block_type(text)
        blocks.append({"content_type": block_type, "text": text})
        cur = []
        cur_type = "explanation"

    for line in lines:
        line_type = classify_block_type(line)
        starts_new = line_type in {"definition", "theorem", "example", "proof", "exercise", "summary"}
        if starts_new and cur:
            flush()
        if starts_new:
            cur_type = line_type
        cur.append(line)
    flush()
    return blocks


def build_course_outline(document_id: str, db_path: Optional[str] = None) -> Dict:
    """根据数据库中保存的页级文本生成课程目录结构。"""
    from ..storage.sqlite import CourseDB

    db = CourseDB(db_path)
    pages = db.get_pages(document_id)
    chapters = detect_chapters(pages)
    return {
        "document_id": document_id,
        "chapter_count": len(chapters),
        "section_count": sum(len(ch.get("sections", [])) for ch in chapters),
        "chapters": chapters,
    }


def match_chapter_by_query(course_id: str, chapter_query: str, db_path: Optional[str] = None) -> Optional[Dict]:
    """根据用户输入"第一章""函数与极限""极限"匹配最接近的章节。"""
    from ..storage.sqlite import CourseDB

    db = CourseDB(db_path)
    names = db.get_chapter_names(course_id)
    if not names:
        return None
    match = process.extractOne(chapter_query, names, scorer=fuzz.WRatio)
    if not match:
        return None
    name, score, _ = match
    return {"course_id": course_id, "chapter_name": name, "score": float(score)}


__all__ = [
    "detect_chapters",
    "detect_sections",
    "classify_block_type",
    "build_course_outline",
    "match_chapter_by_query",
    "iter_typed_blocks",
]
