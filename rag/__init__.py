"""课程资料解析 + RAG + 知识图谱数据底座。

子包结构：
  processing/   文本清洗、章节结构识别、分块、分片
  knowledge/    知识点、公式、例题抽取与标注
  storage/      SQLite 课程库 + ChromaDB 向量存储
  parsing/      PDF / Word / PPT / 图片 / OCR 全链路解析
  retrieval/    Embedding、向量检索、混合召回、重排
  graph/        知识图谱节点/边生成与导出
  pipeline/     文档入库流水线与 IndexManager
  reporting/    解析报告生成与旧版兼容导出
  utils/        LLM 客户端、学习规划、模型下载工具
  tests/        单元/集成测试

顶层 __init__ 保持全量公开 API，外部代码 `from rag import X` 无需改动。
"""

# ── 处理层 ──────────────────────────────────────────────────────
from .processing.chunking import (
    build_chunk_metadata,
    sentence_splitter,
    split_by_structure,
    split_pages_by_structure,
)
from .processing.cleaners import (
    basic_clean,
    clean_basic_text,
    clean_document_pages,
    clean_math_text,
    clean_ocr_text,
    clean_text,
    clean_textbook_noise,
    clean_textbook_text,
    compute_text_quality,
    normalize_math_text,
)
from .processing.structure import (
    build_course_outline,
    classify_block_type,
    detect_chapters,
    detect_sections,
    match_chapter_by_query,
)

# ── 配置（仍在根目录）─────────────────────────────────────────────
from .config import EmbeddingConfig, ExtractionConfig, RetrieverConfig, SplitterConfig, VectorStoreConfig

# ── 存储层 ──────────────────────────────────────────────────────
from .storage.course_index import (
    create_or_load_collection,
    delete_document_vectors,
    get_embedding,
    index_fragments,
    load_collection,
    rebuild_course_index,
    save_fragments_to_vector_store,
)
from .storage.sqlite import CourseDB, save_fragments_to_db
from .storage.vector_store import VectorStore

# ── 解析层 ──────────────────────────────────────────────────────
from .parsing.document_parser import (
    detect_file_type,
    detect_scanned_pdf,
    extract_docx_text,
    extract_image_text,
    extract_pdf_text,
    extract_pptx_text,
    extract_scanned_pdf_ocr,
    parse_document as parse_document_text,
    parse_document_pages,
    parse_document_result,
)

# ── 检索层 ──────────────────────────────────────────────────────
from .retrieval.embeddings import ChromaEmbeddingAdapter, EmbeddingProvider
from .retrieval.retriever import Retriever, RetrievalResult
from .retrieval.rag import (
    build_citation,
    deduplicate_fragments,
    hybrid_search,
    keyword_search,
    rerank_results,
    retrieve,
    retrieve_for_exam,
    retrieve_for_explanation,
    retrieve_for_plan,
    vector_search,
)

# ── 知识图谱 ─────────────────────────────────────────────────────
from .graph.graph import build_graph_edges, build_graph_nodes, export_graph_json

# ── 流水线 ──────────────────────────────────────────────────────
from .pipeline.index_manager import IndexManager
from .pipeline.pipeline import (
    delete_document,
    index_document,
    parse_document,
    rebuild_course,
    reparse_document,
)

# ── 知识抽取 ─────────────────────────────────────────────────────
from .knowledge.extractor import (
    canonical_knowledge_name,
    estimate_difficulty,
    extract_examples,
    extract_exercises,
    extract_formulas,
    extract_knowledge_points,
    tag_knowledge_points,
)

# ── 报告 ────────────────────────────────────────────────────────
from .reporting.reporting import generate_parse_report

# ── 数据模型（仍在根目录）────────────────────────────────────────
from .models import CleanStats, PageParseResult, RetrievalHit

__all__ = [
    "parse_document",
    "parse_document_text",
    "parse_document_result",
    "parse_document_pages",
    "detect_file_type",
    "extract_pdf_text",
    "detect_scanned_pdf",
    "extract_scanned_pdf_ocr",
    "extract_docx_text",
    "extract_pptx_text",
    "extract_image_text",
    "clean_text",
    "clean_basic_text",
    "basic_clean",
    "clean_ocr_text",
    "clean_textbook_noise",
    "clean_textbook_text",
    "clean_math_text",
    "clean_document_pages",
    "compute_text_quality",
    "normalize_math_text",
    "detect_chapters",
    "detect_sections",
    "classify_block_type",
    "build_course_outline",
    "match_chapter_by_query",
    "extract_knowledge_points",
    "extract_formulas",
    "extract_examples",
    "extract_exercises",
    "estimate_difficulty",
    "tag_knowledge_points",
    "canonical_knowledge_name",
    "split_by_structure",
    "split_pages_by_structure",
    "sentence_splitter",
    "build_chunk_metadata",
    "save_fragments_to_db",
    "get_embedding",
    "create_or_load_collection",
    "load_collection",
    "index_fragments",
    "save_fragments_to_vector_store",
    "delete_document_vectors",
    "rebuild_course_index",
    "retrieve",
    "keyword_search",
    "vector_search",
    "hybrid_search",
    "rerank_results",
    "deduplicate_fragments",
    "build_citation",
    "retrieve_for_plan",
    "retrieve_for_explanation",
    "retrieve_for_exam",
    "build_graph_nodes",
    "build_graph_edges",
    "export_graph_json",
    "generate_parse_report",
    "index_document",
    "reparse_document",
    "delete_document",
    "rebuild_course",
    "CourseDB",
    "ExtractionConfig",
    "SplitterConfig",
    "EmbeddingConfig",
    "VectorStoreConfig",
    "RetrieverConfig",
    "EmbeddingProvider",
    "ChromaEmbeddingAdapter",
    "VectorStore",
    "IndexManager",
    "Retriever",
    "RetrievalResult",
    "CleanStats",
    "PageParseResult",
    "RetrievalHit",
]
