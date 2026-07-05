"""课程知识图谱底层数据生成。"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Sequence, Set, Tuple

from rapidfuzz import fuzz

from ..knowledge.extractor import extract_formulas
from ..retrieval.rag import build_citation
from ..storage.sqlite import CourseDB


def _node_id(prefix: str, *parts: str) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return f"{prefix}_{hashlib.md5(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"


def _summary(text: str, limit: int = 120) -> str:
    text = " ".join(str(text or "").split())
    return text[:limit] + ("..." if len(text) > limit else "")


def build_graph_nodes(course_id: str, db_path: str | None = None) -> List[Dict]:
    """生成章节、知识点、公式、例题、习题、易错点节点。"""
    db = CourseDB(db_path)
    fragments = db.get_fragments(course_id=course_id)
    points = db.get_knowledge_points(course_id)
    nodes: Dict[str, Dict] = {}

    for frag in fragments:
        chapter_name = frag.get("chapter_name") or "正文"
        chapter_id = frag.get("chapter_id") or _node_id("chapter", course_id, chapter_name)
        nodes.setdefault(chapter_id, {
            "node_id": chapter_id,
            "type": "chapter",
            "node_type": "chapter",
            "name": chapter_name,
            "source_doc": frag.get("doc_name") or frag.get("file_name"),
            "chapter": chapter_name,
            "page": frag.get("page_start"),
            "confidence": 0.95,
            "chapter_name": chapter_name,
            "difficulty": "",
            "summary": "",
            "source_refs": [build_citation(frag)],
        })

        for formula in extract_formulas(frag.get("text", ""))[:3]:
            fid = formula["formula_id"]
            nodes.setdefault(fid, {
                "node_id": fid,
                "type": "formula",
                "node_type": "formula",
                "name": formula["text"][:60],
                "source_doc": frag.get("doc_name") or frag.get("file_name"),
                "chapter": chapter_name,
                "page": frag.get("page_start"),
                "confidence": 0.80,
                "chapter_name": chapter_name,
                "difficulty": frag.get("difficulty"),
                "summary": formula["text"],
                "source_refs": [build_citation(frag)],
            })

        if frag.get("has_example"):
            eid = _node_id("example", frag.get("chunk_id"), frag.get("text", "")[:80])
            nodes.setdefault(eid, {
                "node_id": eid,
                "type": "example",
                "node_type": "example",
                "name": _summary(frag.get("text", ""), 40),
                "source_doc": frag.get("doc_name") or frag.get("file_name"),
                "chapter": chapter_name,
                "page": frag.get("page_start"),
                "confidence": 0.75,
                "chapter_name": chapter_name,
                "difficulty": frag.get("difficulty"),
                "summary": _summary(frag.get("text", "")),
                "source_refs": [build_citation(frag)],
            })

        if frag.get("has_exercise"):
            exid = _node_id("exercise", frag.get("chunk_id"), frag.get("text", "")[:80])
            nodes.setdefault(exid, {
                "node_id": exid,
                "type": "exercise",
                "node_type": "exercise",
                "name": _summary(frag.get("text", ""), 40),
                "source_doc": frag.get("doc_name") or frag.get("file_name"),
                "chapter": chapter_name,
                "page": frag.get("page_start"),
                "confidence": 0.75,
                "chapter_name": chapter_name,
                "difficulty": frag.get("difficulty"),
                "summary": _summary(frag.get("text", "")),
                "source_refs": [build_citation(frag)],
            })

        if "易错" in frag.get("text", "") or "注意" in frag.get("text", ""):
            mid = _node_id("mistake", frag.get("chunk_id"), frag.get("text", "")[:80])
            nodes.setdefault(mid, {
                "node_id": mid,
                "type": "mistake",
                "node_type": "mistake",
                "name": _summary(frag.get("text", ""), 40),
                "source_doc": frag.get("doc_name") or frag.get("file_name"),
                "chapter": chapter_name,
                "page": frag.get("page_start"),
                "confidence": 0.65,
                "chapter_name": chapter_name,
                "difficulty": frag.get("difficulty"),
                "summary": _summary(frag.get("text", "")),
                "source_refs": [build_citation(frag)],
            })

    for point in points:
        kid = point.get("kp_id") or _node_id("kp", point.get("name"), point.get("chapter_name"))
        nodes.setdefault(kid, {
            "node_id": kid,
            "type": "knowledge_point",
            "node_type": "knowledge_point",
            "name": point.get("name"),
            "source_doc": point.get("document_id"),
            "chapter": point.get("chapter_name"),
            "page": (point.get("source_refs") or [{}])[0].get("page_start") if point.get("source_refs") else None,
            "confidence": 0.72,
            "chapter_name": point.get("chapter_name"),
            "difficulty": point.get("difficulty"),
            "summary": point.get("definition") or point.get("name"),
            "source_refs": point.get("source_refs", []),
        })
    return list(nodes.values())


def _add_edge(edges: Dict[Tuple[str, str, str], Dict], source: str, target: str, relation_type: str, weight: float, reason: str) -> None:
    if not source or not target or source == target:
        return
    key = (source, target, relation_type)
    edges[key] = {
        "source": source,
        "target": target,
        "relation": relation_type,
        "relation_type": relation_type,
        "weight": float(weight),
        "evidence_text": reason,
        "confidence": float(weight),
        "reason": reason,
    }


def build_graph_edges(course_id: str, db_path: str | None = None) -> List[Dict]:
    """生成包含、前置、相似、应用、常见错误等关系。"""
    db = CourseDB(db_path)
    fragments = db.get_fragments(course_id=course_id)
    points = db.get_knowledge_points(course_id)
    nodes = build_graph_nodes(course_id, db_path)
    node_by_type: Dict[str, List[Dict]] = {}
    for node in nodes:
        node_by_type.setdefault(node["node_type"], []).append(node)

    edges: Dict[Tuple[str, str, str], Dict] = {}
    chapter_by_name = {n["name"]: n for n in node_by_type.get("chapter", [])}

    for point in points:
        chapter_node = chapter_by_name.get(point.get("chapter_name"))
        if chapter_node:
            _add_edge(edges, point.get("kp_id"), chapter_node["node_id"], "belongs_to", 1.0, "知识点属于该章节")

    kp_by_name = {p.get("name"): p for p in points}
    for point in points:
        for prereq in point.get("prerequisites", []):
            target = kp_by_name.get(prereq)
            if target:
                _add_edge(edges, target.get("kp_id"), point.get("kp_id"), "prerequisite", 0.72, f"{prereq} 是 {point.get('name')} 的前置知识")
        for item in point.get("confusable_with", []):
            target = kp_by_name.get(item)
            if target:
                _add_edge(edges, point.get("kp_id"), target.get("kp_id"), "confusable_with", 0.62, f"{point.get('name')} 与 {item} 易混")

    for frag in fragments:
        chapter = chapter_by_name.get(frag.get("chapter_name"))
        if not chapter:
            continue
        text = frag.get("text", "")
        for node_type, relation, reason in (
            ("formula", "formula_for", "公式出现在该章节片段中"),
            ("example", "example_of", "例题应用章节知识"),
            ("exercise", "used_in", "习题考查章节知识"),
            ("mistake", "confusable_with", "片段包含注意或易错提示"),
        ):
            for node in node_by_type.get(node_type, []):
                if node.get("chapter_name") == frag.get("chapter_name") and (
                    node.get("summary", "")[:20] in text or node_type in {"example", "exercise", "mistake"}
                ):
                    _add_edge(edges, chapter["node_id"], node["node_id"], relation, 0.8, reason)

    ordered_chapters = node_by_type.get("chapter", [])
    for i in range(len(ordered_chapters) - 1):
        _add_edge(
            edges,
            ordered_chapters[i]["node_id"],
            ordered_chapters[i + 1]["node_id"],
            "prerequisite",
            0.45,
            "按教材顺序推断前后置关系",
        )

    kp_nodes = node_by_type.get("knowledge_point", [])
    for i, left in enumerate(kp_nodes):
        for right in kp_nodes[i + 1:]:
            score = fuzz.token_set_ratio(left.get("name", ""), right.get("name", ""))
            if score >= 72:
                _add_edge(edges, left["node_id"], right["node_id"], "same_level", score / 100, "名称或标签相似")
    return list(edges.values())


def export_graph_json(course_id: str, db_path: str | None = None) -> Dict:
    """导出前端可用的图谱 JSON。"""
    nodes = build_graph_nodes(course_id, db_path)
    edges = build_graph_edges(course_id, db_path)
    return {
        "course_id": course_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


__all__ = [
    "build_graph_nodes",
    "build_graph_edges",
    "export_graph_json",
]
