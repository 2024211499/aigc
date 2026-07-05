"""解析报告生成。"""

from __future__ import annotations

from typing import Dict, Optional

from ..knowledge.extractor import extract_examples, extract_exercises, extract_formulas
from ..storage.sqlite import CourseDB
from ..processing.structure import detect_chapters


def generate_parse_report(document_id: str, db_path: Optional[str] = None) -> Dict:
    """返回上传后前端可展示的解析报告。"""
    db = CourseDB(db_path)
    doc = db.get_document(document_id)
    if not doc:
        return {
            "document_id": document_id,
            "status": "missing",
            "exception": "文档不存在",
        }

    pages = db.get_pages(document_id)
    good_pages = [p for p in pages if p.get("text")]
    failed_pages = [p for p in pages if p.get("error")]
    ocr_pages = [p for p in good_pages if p.get("is_ocr") or "ocr" in str(p.get("method", "")).lower()]
    direct_pages = [p for p in good_pages if p.get("extraction_method") == "direct"]
    scanned_pages = [p for p in pages if p.get("is_scanned_page")]
    low_quality_pages = [
        p for p in pages
        if (p.get("quality_stats") or {}).get("quality_score", 1.0) < 0.55 or p.get("failure_reason")
    ]
    text = "\n\n".join(p.get("text", "") for p in good_pages)
    chapters = detect_chapters(good_pages)
    fragments = db.get_fragments(course_id=doc["course_id"], filters={"document_id": document_id})
    formulas = extract_formulas(text)
    examples = extract_examples(text)
    exercises = extract_exercises(text)
    vector_count = sum(1 for f in fragments if f.get("embedding"))

    report = {
        "document_id": document_id,
        "course_id": doc.get("course_id"),
        "file_name": doc.get("file_name"),
        "file_type": doc.get("file_type"),
        "total_pages": doc.get("page_count") or len(pages),
        "success_pages": len(good_pages),
        "direct_pages": len(direct_pages),
        "ocr_pages": len(ocr_pages),
        "failed_pages": len(failed_pages),
        "scanned_pages": len(scanned_pages),
        "failed_page_details": [
            {"page": p.get("page"), "method": p.get("method"), "error": p.get("error")}
            for p in failed_pages
        ],
        "total_chars": len(text),
        "average_chars_per_page": len(text) / max(len(pages), 1),
        "low_quality_pages": len(low_quality_pages),
        "failure_reasons": [
            {"page": p.get("page"), "reason": p.get("failure_reason") or p.get("error")}
            for p in pages if p.get("failure_reason") or p.get("error")
        ],
        "elapsed_time": (doc.get("parse_report") or {}).get("elapsed_time", 0),
        "chapter_count": len(chapters),
        "section_count": sum(len(c.get("sections", [])) for c in chapters),
        "knowledge_point_count": len(db.get_knowledge_points(doc["course_id"], document_id=document_id)),
        "formula_count": len(formulas),
        "example_count": len(examples),
        "exercise_count": len(exercises),
        "chunk_count": len(fragments),
        "vector_count": vector_count,
        "index_success": bool(fragments) and vector_count == len(fragments),
        "status": doc.get("status"),
        "exceptions": doc.get("errors", []),
    }
    db.update_document_report(document_id, report)
    return report


__all__ = ["generate_parse_report"]
