"""知识点、公式、例题、习题与难度标签抽取。"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Sequence

from ..processing.cleaners import normalize_whitespace
from ..processing.structure import classify_block_type, detect_sections, iter_typed_blocks


FORMULA_RE = re.compile(
    r"(\$\$.*?\$\$|\$[^$]{1,200}\$|\\\[[\s\S]{1,500}?\\\]|\\\([\s\S]{1,300}?\\\)|"
    r"(?:[A-Za-z0-9_{}一-鿿]+)\s*[=<>≤≥≈≠]\s*[^，。；;\n]{1,120}|"
    r"(?:∫|∑|∏|√|lim|\\frac|\\sum|\\int)[^，。；;\n]{0,160})",
    re.IGNORECASE,
)
DEFINITION_RE = re.compile(
    r"(?:定义|概念|所谓|称为|叫做|记作)[:：]?\s*(?P<body>[^。；;\n]{4,160})",
    re.IGNORECASE,
)
NAME_BY_IS_RE = re.compile(
    r"(?P<name>[一-鿿A-Za-z0-9（）()·]{2,30})\s*(?:是指|是|称为|叫做)\s*[^。；;\n]{4,120}"
)
EXAMPLE_START_RE = re.compile(r"^\s*(例题?|例\s*[0-9一二三四五六七八九十]*|Example)\b", re.IGNORECASE)
EXERCISE_START_RE = re.compile(r"^\s*(习题|练习|作业|思考题|选择题|填空题|解答题|Exercises?)\b", re.IGNORECASE)
SYNONYM_GROUPS = {
    "不定积分": ["原函数与不定积分", "原函数", "不定积分"],
    "定积分": ["定积分", "黎曼积分"],
    "极限": ["函数极限", "数列极限", "极限"],
    "导数": ["导数", "微分", "变化率"],
}


def _stable_id(prefix: str, text: str) -> str:
    return f"{prefix}_{hashlib.md5(text.encode('utf-8', errors='ignore')).hexdigest()[:12]}"


def canonical_knowledge_name(name: str) -> str:
    cleaned = normalize_whitespace(name)
    for canonical, variants in SYNONYM_GROUPS.items():
        if any(v in cleaned or cleaned in v for v in variants):
            return canonical
    return cleaned


def extract_formulas(chapter_text: str) -> List[Dict]:
    """抽取公式和数学表达式。"""
    formulas: List[Dict] = []
    seen = set()
    for match in FORMULA_RE.finditer(chapter_text or ""):
        formula = normalize_whitespace(match.group(0))
        if len(formula) < 2 or formula in seen:
            continue
        seen.add(formula)
        formulas.append({
            "formula_id": _stable_id("formula", formula),
            "text": formula,
            "start": match.start(),
            "end": match.end(),
        })
    return formulas


def _collect_prefixed_blocks(text: str, start_pattern: re.Pattern, default_type: str) -> List[Dict]:
    lines = [normalize_whitespace(x) for x in str(text or "").splitlines() if normalize_whitespace(x)]
    blocks: List[Dict] = []
    cur: List[str] = []

    def flush() -> None:
        nonlocal cur
        if cur:
            body = "\n".join(cur)
            blocks.append({
                "id": _stable_id(default_type, body),
                "text": body,
                "difficulty": estimate_difficulty(body),
            })
            cur = []

    for line in lines:
        if start_pattern.search(line) and cur:
            flush()
        if start_pattern.search(line) or cur:
            cur.append(line)
    flush()
    return blocks


def extract_examples(chapter_text: str) -> List[Dict]:
    """抽取例题和例题解析。"""
    examples = _collect_prefixed_blocks(chapter_text, EXAMPLE_START_RE, "example")
    if examples:
        return examples
    return [
        {"id": _stable_id("example", b["text"]), "text": b["text"], "difficulty": estimate_difficulty(b["text"])}
        for b in iter_typed_blocks(chapter_text)
        if b["content_type"] == "example"
    ]


def extract_exercises(chapter_text: str) -> List[Dict]:
    """抽取习题。"""
    exercises = _collect_prefixed_blocks(chapter_text, EXERCISE_START_RE, "exercise")
    if exercises:
        return exercises
    candidates: List[Dict] = []
    for line in str(chapter_text or "").splitlines():
        text = normalize_whitespace(line)
        if re.match(r"^\s*(?:\d+[).、]|[（(]\d+[）)]|[A-D][.、])\s*[^。]{4,}", text):
            candidates.append({
                "id": _stable_id("exercise", text),
                "text": text,
                "question_type": estimate_question_type(text),
                "difficulty": estimate_difficulty(text),
            })
    return candidates


def _candidate_name_from_definition(body: str) -> str:
    body = normalize_whitespace(body)
    for sep in ("是指", "是", "称为", "叫做", "，", ",", "。"):
        if sep in body:
            left = body.split(sep, 1)[0]
            if 2 <= len(left) <= 30:
                return left.strip(" ：:，,。")
    return body[:30].strip(" ：:，,。")


def extract_knowledge_points(chapter_text: str) -> List[Dict]:
    """从章节文本中抽取知识点。"""
    text = chapter_text or ""
    points: List[Dict] = []
    seen = set()

    for section in detect_sections(text):
        name = canonical_knowledge_name(re.sub(r"^[0-9.一二三四五六七八九十、.．§\s]+", "", section["section_name"]).strip())
        if 2 <= len(name) <= 40 and name not in {"正文", "小结", "习题"}:
            seen.add(name)
            points.append({
                "kp_id": _stable_id("kp", name),
                "name": name,
                "definition": "",
                "source": "section_heading",
                "difficulty": estimate_difficulty(section.get("text", "")),
                "tags": tag_text(section.get("text", "")),
            })

    for match in DEFINITION_RE.finditer(text):
        body = normalize_whitespace(match.group("body"))
        name = canonical_knowledge_name(_candidate_name_from_definition(body))
        if len(name) < 2 or name in seen:
            continue
        seen.add(name)
        points.append({
            "kp_id": _stable_id("kp", name + body),
            "name": name,
            "definition": body,
            "source": "definition",
            "difficulty": estimate_difficulty(body),
            "tags": tag_text(body),
        })

    for match in NAME_BY_IS_RE.finditer(text):
        name = canonical_knowledge_name(normalize_whitespace(match.group("name")))
        if len(name) < 2 or name in seen:
            continue
        seen.add(name)
        sentence = normalize_whitespace(match.group(0))
        points.append({
            "kp_id": _stable_id("kp", sentence),
            "name": name,
            "definition": sentence,
            "source": "sentence",
            "difficulty": estimate_difficulty(sentence),
            "tags": tag_text(sentence),
        })

    formulas = extract_formulas(text)
    examples = extract_examples(text)
    exercises = extract_exercises(text)
    for point in points:
        point["formulas"] = [f["text"] for f in formulas[:5]]
        point["examples"] = [e["text"] for e in examples[:3]]
        point["exercises"] = [e["text"] for e in exercises[:3]]
        point["question_types"] = sorted({estimate_question_type(e["text"]) for e in exercises[:5]})
        point["confusable_with"] = [k for k, variants in SYNONYM_GROUPS.items() if k != point["name"] and any(v in text for v in variants[:1])][:3]
        point["prerequisites"] = infer_prerequisites(point["name"], text)
        point["applications"] = infer_applications(text)
    return points


def infer_prerequisites(name: str, text: str) -> List[str]:
    rules = {
        "定积分": ["函数", "极限"],
        "不定积分": ["导数", "微分"],
        "导数": ["函数", "极限"],
        "极限": ["函数"],
    }
    return rules.get(name, [x for x in ("函数", "方程", "集合") if x in text][:2])


def infer_applications(text: str) -> List[str]:
    candidates = []
    for word in ("面积", "体积", "最值", "变化率", "概率", "物理应用", "经济应用", "建模"):
        if word in text:
            candidates.append(word)
    return candidates


def estimate_difficulty(text_block: str) -> str:
    """初步判断知识点或题目的难度。"""
    text = text_block or ""
    score = 0
    score += min(len(text) // 350, 3)
    score += min(len(extract_formulas(text)), 3)
    if re.search(r"(证明|推导|综合|应用|最值|极限|积分|导数|矩阵|递推|概率密度|偏导)", text):
        score += 2
    if re.search(r"(选择|填空|判断|基础|概念)", text):
        score -= 1
    if score <= 1:
        return "基础"
    if score <= 4:
        return "中等"
    return "困难"


def estimate_question_type(text: str) -> str:
    if re.search(r"选择题|^[A-D][.、]|A[.、].*B[.、]", text):
        return "选择题"
    if re.search(r"填空题|_{2,}|（\s*）|\(\s*\)", text):
        return "填空题"
    if re.search(r"证明|说明理由", text):
        return "证明题"
    if re.search(r"计算|求|解方程|积分|导数", text):
        return "计算题"
    return "综合题"


def tag_text(text: str) -> List[str]:
    tags: List[str] = []
    keyword_tags = {
        "定义": "概念",
        "概念": "概念",
        "定理": "定理",
        "性质": "性质",
        "公式": "公式",
        "例": "例题",
        "习题": "习题",
        "证明": "证明",
        "极限": "极限",
        "函数": "函数",
        "导数": "导数",
        "积分": "积分",
        "矩阵": "线性代数",
        "概率": "概率统计",
    }
    for key, tag in keyword_tags.items():
        if key in text and tag not in tags:
            tags.append(tag)
    if extract_formulas(text) and "公式" not in tags:
        tags.append("公式")
    return tags or [classify_block_type(text)]


def tag_knowledge_points(chunks: Sequence[Dict]) -> List[Dict]:
    """为 chunk 添加知识点标签。"""
    tagged: List[Dict] = []
    for chunk in chunks:
        item = dict(chunk)
        points = extract_knowledge_points(item.get("text", ""))
        tags = tag_text(item.get("text", ""))
        names = [p["name"] for p in points[:5]]
        item["knowledge_points"] = names or item.get("knowledge_points") or tags
        item["difficulty"] = item.get("difficulty") or estimate_difficulty(item.get("text", ""))
        item["tags"] = sorted(set(tags + item.get("knowledge_points", [])))
        tagged.append(item)
    return tagged


def summarize_knowledge_for_chapter(chapter: Dict) -> Dict:
    text = chapter.get("text", "")
    return {
        "chapter_id": chapter.get("chapter_id"),
        "chapter_name": chapter.get("chapter_name"),
        "knowledge_points": extract_knowledge_points(text),
        "formulas": extract_formulas(text),
        "examples": extract_examples(text),
        "exercises": extract_exercises(text),
    }


__all__ = [
    "extract_knowledge_points",
    "extract_formulas",
    "extract_examples",
    "extract_exercises",
    "estimate_difficulty",
    "tag_knowledge_points",
    "estimate_question_type",
    "summarize_knowledge_for_chapter",
    "canonical_knowledge_name",
]
