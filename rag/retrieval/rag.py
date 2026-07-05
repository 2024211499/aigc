"""增强 RAG 检索、混合召回与引用溯源。"""

from __future__ import annotations

import math
import re
import logging
import os
from typing import Dict, List, Optional, Sequence

from rapidfuzz import fuzz

from ..config import EmbeddingConfig
from ..storage.course_index import get_embedding, load_collection
from ..exceptions import EmbeddingError, StorageError
from ..knowledge.extractor import tag_text
from ..models import RetrievalHit
from ..storage.sqlite import CourseDB
from ..processing.structure import match_chapter_by_query

logger = logging.getLogger(__name__)

def _tokens(text: str) -> List[str]:
    text = (text or "").lower()
    words = re.findall(r"[A-Za-z0-9_]+", text)
    chars = re.findall(r"[一-鿿]", text)
    bigrams = ["".join(chars[i:i + 2]) for i in range(max(0, len(chars) - 1))]
    return words + chars + bigrams


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(float(a[i]) * float(b[i]) for i in range(n))
    na = math.sqrt(sum(float(x) * float(x) for x in a[:n])) or 1.0
    nb = math.sqrt(sum(float(x) * float(x) for x in b[:n])) or 1.0
    return dot / (na * nb)


def _apply_post_filters(fragments: List[Dict], filters: Optional[Dict]) -> List[Dict]:
    if not filters:
        return fragments
    out = []
    knowledge_query = filters.get("knowledge_point") or filters.get("knowledge_points")
    for frag in fragments:
        if knowledge_query:
            names = frag.get("knowledge_points") or []
            text = " ".join(map(str, names)) + " " + frag.get("text", "")
            if fuzz.partial_ratio(str(knowledge_query), text) < 60:
                continue
        if filters.get("has_formula") is not None and bool(frag.get("has_formula")) != bool(filters["has_formula"]):
            continue
        if filters.get("has_example") is not None and bool(frag.get("has_example")) != bool(filters["has_example"]):
            continue
        if filters.get("has_exercise") is not None and bool(frag.get("has_exercise")) != bool(filters["has_exercise"]):
            continue
        if filters.get("exclude_low_quality_ocr"):
            quality = frag.get("source_quality_score", 1.0)
            try:
                quality = float(quality)
            except Exception:
                quality = 1.0
            if bool(frag.get("is_ocr") or frag.get("is_ocr_text")) and quality < float(filters.get("min_quality_score", 0.55)):
                continue
        out.append(frag)
    return out


def _base_filters(filters: Optional[Dict]) -> Dict:
    allowed = {
        "document_id",
        "doc_id",
        "chapter_name",
        "chapter",
        "section_name",
        "section",
        "content_type",
        "chunk_type",
        "difficulty",
        "file_name",
        "doc_name",
        "page_start",
        "page_end",
        "is_ocr_text",
    }
    return {k: v for k, v in (filters or {}).items() if k in allowed}


def _fts_query(query: str) -> str:
    terms = re.findall(r"[一-鿿A-Za-z0-9_]+", query or "")
    if not terms:
        return ""
    return " OR ".join(terms[:12])


def keyword_search(
    course_id: str,
    query: str,
    filters: Optional[Dict] = None,
    top_k: int = 20,
    *,
    db_path: Optional[str] = None,
) -> List[Dict]:
    """关键词检索：SQLite FTS5 first, SQL LIKE fallback."""
    db = CourseDB(db_path)
    fts = _fts_query(query)
    hits: List[Dict] = []
    if fts:
        try:
            hits = db.keyword_search_fts(course_id, fts, _base_filters(filters), limit=top_k)
        except StorageError as exc:
            logger.warning("FTS 检索失败，回退 LIKE: %s", exc)
    if not hits and query:
        hits = db.keyword_search_like(course_id, query, _base_filters(filters), limit=top_k)
    hits = _apply_post_filters(hits, filters)
    for hit in hits:
        hit["score"] = float(hit.get("keyword_score", 0.0))
        if query and query in hit.get("text", ""):
            hit["score"] += 1.0
        hit["score"] += 0.2 * sum(1 for token in _tokens(query) if token and token in hit.get("text", ""))
        hit["keyword_score"] = hit["score"]
        hit["retrieval_source"] = "keyword"
        hit["retrieval_method"] = "fts5" if fts else "like"
        hit["why_matched"] = f"关键词匹配: {query}"
        hit["citation"] = build_citation(hit)
    return hits[:top_k]


def _chroma_where(filters: Optional[Dict]) -> Optional[Dict]:
    filters = _base_filters(filters)
    clauses = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            clauses.append({key: {"$in": list(value)}})
        else:
            clauses.append({key: value})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def vector_search(
    course_id: str,
    query: str,
    filters: Optional[Dict] = None,
    top_k: int = 5,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
) -> List[Dict]:
    """向量检索，优先 Chroma，失败时回退 SQLite 内保存的向量。"""
    if not course_id:
        return []
    db = CourseDB(db_path)
    if not any(f.get("embedding") for f in db.get_fragments(course_id=course_id, filters=_base_filters(filters), limit=1)):
        return []
    try:
        query_vector = get_embedding([query], config=EmbeddingConfig(debug_fallback=False))[0]
    except EmbeddingError as exc:
        logger.warning("向量查询 embedding 失败，跳过向量召回: %s", exc)
        return []

    try:
        collection = load_collection(course_id, persist_dir)
        result = collection.query(
            query_embeddings=[query_vector],
            n_results=max(top_k, 20),
            where=_chroma_where(filters),
            include=["documents", "metadatas", "distances"],
        )
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits: List[Dict] = []
        for idx, doc_text in enumerate(docs):
            meta = metas[idx] or {}
            chunk_id = meta.get("chunk_id")
            frag = db.get_fragment_by_id(chunk_id) if chunk_id else None
            item = frag or dict(meta)
            item["text"] = item.get("text") or doc_text
            item["distance"] = float(distances[idx])
            item["vector_score"] = 1.0 - float(distances[idx])
            item["score"] = item["vector_score"]
            item["retrieval_source"] = "vector"
            item["retrieval_method"] = "chroma"
            item["why_matched"] = "向量相似度匹配"
            item["citation"] = build_citation(item)
            hits.append(item)
        return _apply_post_filters(hits, filters)[:top_k]
    except Exception as exc:
        logger.info("Chroma 向量检索不可用，尝试 SQLite 向量回退: %s", exc)
        fragments = db.get_fragments(course_id=course_id, filters=_base_filters(filters))
        fragments = _apply_post_filters(fragments, filters)
        hits = []
        for frag in fragments:
            emb = frag.get("embedding") or []
            if not emb:
                continue
            score = _cosine(query_vector, emb)
            item = dict(frag)
            item["vector_score"] = score
            item["score"] = score
            item["retrieval_source"] = "vector_sqlite"
            item["retrieval_method"] = "sqlite_vector"
            item["why_matched"] = "SQLite 缓存向量相似度匹配"
            item["citation"] = build_citation(item)
            hits.append(item)
        return sorted(hits, key=lambda x: x["score"], reverse=True)[:top_k]


def hybrid_search(
    course_id: str,
    query: str,
    filters: Optional[Dict] = None,
    top_k: int = 5,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
) -> List[Dict]:
    """关键词 + 向量混合检索。"""
    keyword_hits = keyword_search(course_id, query, filters, top_k=max(top_k * 3, 20), db_path=db_path)
    vector_hits = vector_search(course_id, query, filters, top_k=max(top_k * 3, 20), db_path=db_path, persist_dir=persist_dir)

    merged: Dict[str, Dict] = {}
    max_kw = max([h.get("keyword_score", 0.0) for h in keyword_hits] or [1.0]) or 1.0
    max_vec = max([h.get("vector_score", 0.0) for h in vector_hits] or [1.0]) or 1.0

    for hit in keyword_hits:
        item = merged.setdefault(hit["chunk_id"], dict(hit))
        item["keyword_score"] = hit.get("keyword_score", 0.0) / max_kw
    for hit in vector_hits:
        item = merged.setdefault(hit["chunk_id"], dict(hit))
        item["vector_score"] = hit.get("vector_score", 0.0) / max_vec
        item["distance"] = hit.get("distance")

    candidates: List[Dict] = []
    for item in merged.values():
        kw = item.get("keyword_score", 0.0)
        vec = item.get("vector_score", 0.0)
        item["score"] = 0.45 * kw + 0.55 * vec
        item["retrieval_source"] = "hybrid"
        item["retrieval_method"] = "hybrid"
        item["why_matched"] = _merge_why(item)
        item["citation"] = build_citation(item)
        candidates.append(item)
    return rerank_results(query, deduplicate_fragments(candidates))[:top_k]


def rerank_results(query: str, candidates: Sequence[Dict]) -> List[Dict]:
    """对候选片段重新排序，使用轻量规则评分，可替换为 bge-reranker。"""
    try:
        from .reranker import rerank

        if os.getenv("ENABLE_RERANKER", "").lower() in {"1", "true", "yes"}:
            reranked = rerank(query, [dict(x) for x in candidates], len(candidates))
            if reranked and any(isinstance(x, dict) and "rerank_score" in x for x in reranked):
                return list(reranked)
    except Exception as exc:
        logger.debug("可选 reranker 不可用，使用轻量规则: %s", exc)
    q_tags = set(tag_text(query))
    reranked = []
    for item in candidates:
        text = item.get("text", "")
        bonus = 0.0
        if query and query in text:
            bonus += 0.25
        if item.get("chapter_name") and fuzz.partial_ratio(query, item["chapter_name"]) >= 75:
            bonus += 0.15
        tags = set(item.get("knowledge_points") or []) | set(tag_text(text))
        if q_tags & tags:
            bonus += 0.1
        item = dict(item)
        item["rerank_score"] = float(item.get("score", 0.0)) + bonus
        reranked.append(item)
    return sorted(reranked, key=lambda x: x["rerank_score"], reverse=True)


def _merge_why(item: Dict) -> str:
    reasons = []
    if item.get("keyword_score"):
        reasons.append("关键词")
    if item.get("vector_score"):
        reasons.append("向量")
    return "+".join(reasons) + "召回" if reasons else "规则排序"


def deduplicate_fragments(fragments: Sequence[Dict]) -> List[Dict]:
    """去除重复片段。"""
    seen = set()
    result: List[Dict] = []
    for frag in fragments:
        key = frag.get("chunk_id") or (frag.get("document_id"), frag.get("page_start"), frag.get("text", "")[:80])
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(frag))
    return result


def build_citation(fragment: Dict) -> str:
    """生成引用信息，例如"高等数学 第一章 第 12-15 页"。"""
    course = fragment.get("course_name") or fragment.get("course_id") or "课程资料"
    chapter = fragment.get("chapter") or fragment.get("chapter_name") or "正文"
    file_name = fragment.get("doc_name") or fragment.get("file_name") or ""
    page_start = fragment.get("page_start")
    page_end = fragment.get("page_end")
    if page_start and page_end and page_start != page_end:
        page = f"第 {page_start}-{page_end} 页"
    elif page_start:
        page = f"第 {page_start} 页"
    else:
        page = "页码未知"
    return " ".join(x for x in [course, chapter, page, file_name] if x)


def _to_hit_dict(item: Dict) -> Dict:
    hit = RetrievalHit(
        text=item.get("text", ""),
        score=float(item.get("rerank_score", item.get("score", 0.0)) or 0.0),
        source=item.get("source_path", ""),
        doc_name=item.get("doc_name") or item.get("file_name", ""),
        chapter=item.get("chapter") or item.get("chapter_name", ""),
        section=item.get("section") or item.get("section_name", ""),
        page_start=item.get("page_start"),
        page_end=item.get("page_end"),
        chunk_type=item.get("chunk_type") or item.get("content_type", ""),
        retrieval_method=item.get("retrieval_method", item.get("retrieval_source", "")),
        why_matched=item.get("why_matched", ""),
        citation=item.get("citation") or build_citation(item),
        chunk_id=item.get("chunk_id", ""),
        doc_id=item.get("doc_id") or item.get("document_id", ""),
        course_id=item.get("course_id", ""),
        vector_score=float(item.get("vector_score", 0.0) or 0.0),
        keyword_score=float(item.get("keyword_score", 0.0) or 0.0),
        rerank_score=float(item.get("rerank_score", item.get("score", 0.0)) or 0.0),
        source_quality_score=float(item.get("source_quality_score", 1.0) or 1.0),
    ).to_dict()
    # Keep rich metadata for downstream callers without changing the stable top-level fields.
    hit.update({
        "knowledge_points": item.get("knowledge_points", []),
        "source_refs": item.get("source_refs", []),
        "retrieval_source": item.get("retrieval_source", item.get("retrieval_method", "")),
    })
    return hit


def build_context(results: Sequence[Dict], max_chars: int = 4000) -> Dict:
    """拼接 RAG 上下文，并保留引用列表。"""
    parts: List[str] = []
    citations: List[str] = []
    total = 0
    for idx, hit in enumerate(results, start=1):
        text = hit.get("text", "")
        citation = hit.get("citation") or build_citation(hit)
        block = f"[{idx}] {text}\n来源：{citation}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        citations.append(citation)
        total += len(block)
    return {
        "context": "\n\n".join(parts),
        "citations": citations,
        "insufficient_evidence": len(parts) == 0,
    }


def retrieve(
    query_or_course_id: Optional[str] = None,
    course_id: Optional[str] = None,
    chapter: Optional[str] = None,
    section: Optional[str] = None,
    query: Optional[str] = None,
    top_k: int = 5,
    filters: Optional[Dict] = None,
    *,
    db_path: Optional[str] = None,
    persist_dir: Optional[str] = None,
) -> List[Dict]:
    """统一检索入口。"""
    if query is None:
        query = query_or_course_id or ""
    elif course_id is None and query_or_course_id:
        # Backward compatibility: retrieve("course_id", query="...")
        course_id = query_or_course_id
    filters = dict(filters or {})
    if section and "section" not in filters and "section_name" not in filters:
        filters["section"] = section
    if chapter and "chapter_name" not in filters and "chapter" not in filters and course_id:
        matched = match_chapter_by_query(course_id, chapter, db_path=db_path)
        if matched and matched["score"] >= 55:
            filters["chapter_name"] = matched["chapter_name"]
    query = query or chapter or ""
    if not query:
        return [_to_hit_dict(x) for x in CourseDB(db_path).get_fragments(course_id=course_id, filters=_base_filters(filters), limit=top_k)]
    results = hybrid_search(course_id, query, filters, top_k, db_path=db_path, persist_dir=persist_dir)
    if not results and filters:
        relaxed = dict(filters)
        for key in ("section", "section_name", "chapter", "chapter_name"):
            relaxed.pop(key, None)
        results = hybrid_search(course_id, query, relaxed, top_k, db_path=db_path, persist_dir=persist_dir)
        for result in results:
            result["why_matched"] = (result.get("why_matched", "") + "; 放宽章节/小节过滤").strip("; ")
    return [_to_hit_dict(x) for x in results[:top_k]]


def retrieve_for_plan(course_id: str, chapter_name: str, **kwargs) -> Dict:
    """专门为学习计划生成准备上下文。"""
    hits = retrieve(course_id, chapter=chapter_name, query=f"{chapter_name} 重点 难点 小结", top_k=8, **kwargs)
    return build_context(hits, max_chars=5000)


def retrieve_for_explanation(course_id: str, knowledge_point: str, **kwargs) -> Dict:
    """专门为知识点讲解准备上下文。"""
    hits = retrieve(
        course_id,
        query=f"{knowledge_point} 定义 公式 例题",
        filters={"knowledge_point": knowledge_point},
        top_k=6,
        **kwargs,
    )
    return build_context(hits, max_chars=4500)


def retrieve_for_exam(course_id: str, chapters: Sequence[str], question_types: Optional[Sequence[str]] = None, **kwargs) -> Dict:
    """专门为组卷准备上下文。"""
    all_hits: List[Dict] = []
    filters = {"has_exercise": True}
    for chapter in chapters:
        all_hits.extend(retrieve(course_id, chapter=chapter, query=f"{chapter} 习题 例题", filters=filters, top_k=5, **kwargs))
    if question_types:
        joined = " ".join(question_types)
        all_hits = [h for h in all_hits if fuzz.partial_ratio(joined, h.get("text", "")) >= 30]
    return build_context(deduplicate_fragments(all_hits), max_chars=6000)


__all__ = [
    "retrieve",
    "keyword_search",
    "vector_search",
    "hybrid_search",
    "rerank_results",
    "deduplicate_fragments",
    "build_citation",
    "build_context",
    "retrieve_for_plan",
    "retrieve_for_explanation",
    "retrieve_for_exam",
]
