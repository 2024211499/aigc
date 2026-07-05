"""SQLite 课程知识库底层存储。"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence

from ..exceptions import StorageError

DEFAULT_DB_PATH = os.getenv("COURSE_KB_DB_PATH", "./course_kb.sqlite3")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(value) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _loads(value, default=None):
    if value in (None, ""):
        return [] if default is None else default
    try:
        return json.loads(value)
    except Exception:
        return [] if default is None else default


class CourseDB:
    """轻量关系型数据库，用于课程、文档、页、片段、知识点与报告。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.init_schema()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS courses (
                    course_id TEXT PRIMARY KEY,
                    course_name TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    course_id TEXT,
                    file_name TEXT,
                    file_type TEXT,
                    source_path TEXT,
                    doc_md5 TEXT,
                    page_count INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0,
                    status TEXT,
                    error_json TEXT,
                    parse_report_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT,
                    page_no INTEGER,
                    text TEXT,
                    raw_text TEXT,
                    cleaned_text TEXT,
                    method TEXT,
                    extraction_method TEXT,
                    ocr_backend TEXT,
                    ocr_confidence REAL,
                    is_scanned_page INTEGER DEFAULT 0,
                    failure_reason TEXT,
                    quality_stats_json TEXT,
                    char_count INTEGER DEFAULT 0,
                    is_ocr INTEGER DEFAULT 0,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS fragments (
                    chunk_id TEXT PRIMARY KEY,
                    course_id TEXT,
                    document_id TEXT,
                    doc_id TEXT,
                    file_name TEXT,
                    doc_name TEXT,
                    course_name TEXT,
                    chapter_id TEXT,
                    chapter_name TEXT,
                    chapter TEXT,
                    section_name TEXT,
                    section TEXT,
                    subsection TEXT,
                    page_start INTEGER,
                    page_end INTEGER,
                    content_type TEXT,
                    chunk_type TEXT,
                    knowledge_points_json TEXT,
                    difficulty TEXT,
                    source_path TEXT,
                    source_refs_json TEXT,
                    created_at TEXT,
                    text TEXT,
                    embedding_id TEXT,
                    embedding_json TEXT,
                    is_ocr INTEGER DEFAULT 0,
                    has_formula INTEGER DEFAULT 0,
                    has_example INTEGER DEFAULT 0,
                    has_exercise INTEGER DEFAULT 0,
                    metadata_json TEXT
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS fragments_fts USING fts5(
                    chunk_id UNINDEXED,
                    course_id UNINDEXED,
                    document_id UNINDEXED,
                    chapter,
                    section,
                    chunk_type,
                    text,
                    tokenize='unicode61'
                );

                CREATE TABLE IF NOT EXISTS knowledge_points (
                    kp_id TEXT PRIMARY KEY,
                    course_id TEXT,
                    document_id TEXT,
                    chapter_id TEXT,
                    chapter_name TEXT,
                    name TEXT,
                    definition TEXT,
                    formulas_json TEXT,
                    examples_json TEXT,
                    exercises_json TEXT,
                    question_types_json TEXT,
                    prerequisites_json TEXT,
                    applications_json TEXT,
                    confusable_json TEXT,
                    tags_json TEXT,
                    difficulty TEXT,
                    source_refs_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_documents_course ON documents(course_id);
                CREATE INDEX IF NOT EXISTS idx_pages_document ON pages(document_id);
                CREATE INDEX IF NOT EXISTS idx_fragments_course ON fragments(course_id);
                CREATE INDEX IF NOT EXISTS idx_fragments_document ON fragments(document_id);
                CREATE INDEX IF NOT EXISTS idx_fragments_chapter ON fragments(course_id, chapter_name);
                CREATE INDEX IF NOT EXISTS idx_kp_course ON knowledge_points(course_id);
                """
            )
            self.migrate_schema(conn)

    def migrate_schema(self, conn: Optional[sqlite3.Connection] = None) -> None:
        owns_conn = conn is None
        conn = conn or sqlite3.connect(self.db_path)
        try:
            page_columns = {
                "extraction_method": "TEXT",
                "ocr_backend": "TEXT",
                "ocr_confidence": "REAL",
                "is_scanned_page": "INTEGER DEFAULT 0",
                "failure_reason": "TEXT",
                "quality_stats_json": "TEXT",
                "raw_text": "TEXT",
                "cleaned_text": "TEXT",
            }
            fragment_columns = {
                "doc_id": "TEXT",
                "doc_name": "TEXT",
                "chapter": "TEXT",
                "section": "TEXT",
                "subsection": "TEXT",
                "chunk_type": "TEXT",
                "source_refs_json": "TEXT",
            }
            kp_columns = {
                "question_types_json": "TEXT",
                "prerequisites_json": "TEXT",
                "applications_json": "TEXT",
                "confusable_json": "TEXT",
            }
            self._ensure_columns(conn, "pages", page_columns)
            self._ensure_columns(conn, "fragments", fragment_columns)
            self._ensure_columns(conn, "knowledge_points", kp_columns)
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS fragments_fts USING fts5(
                    chunk_id UNINDEXED,
                    course_id UNINDEXED,
                    document_id UNINDEXED,
                    chapter,
                    section,
                    chunk_type,
                    text,
                    tokenize='unicode61'
                )
                """
            )
        finally:
            if owns_conn:
                conn.close()

    @staticmethod
    def _ensure_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, spec in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")

    def save_course(self, course_id: str, course_name: Optional[str] = None) -> None:
        ts = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO courses(course_id, course_name, created_at, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(course_id) DO UPDATE SET
                    course_name=COALESCE(excluded.course_name, courses.course_name),
                    updated_at=excluded.updated_at
                """,
                (course_id, course_name or course_id, ts, ts),
            )

    def save_document(self, doc: Dict) -> None:
        ts = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO documents(
                    document_id, course_id, file_name, file_type, source_path, doc_md5,
                    page_count, char_count, status, error_json, parse_report_json, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    course_id=excluded.course_id,
                    file_name=excluded.file_name,
                    file_type=excluded.file_type,
                    source_path=excluded.source_path,
                    doc_md5=excluded.doc_md5,
                    page_count=excluded.page_count,
                    char_count=excluded.char_count,
                    status=excluded.status,
                    error_json=excluded.error_json,
                    parse_report_json=excluded.parse_report_json,
                    updated_at=excluded.updated_at
                """,
                (
                    doc["document_id"],
                    doc.get("course_id"),
                    doc.get("file_name"),
                    doc.get("file_type"),
                    doc.get("source_path"),
                    doc.get("doc_md5"),
                    int(doc.get("page_count") or 0),
                    int(doc.get("char_count") or 0),
                    doc.get("status", "parsed"),
                    _json(doc.get("errors", [])),
                    _json(doc.get("parse_report", {})),
                    doc.get("created_at", ts),
                    ts,
                ),
            )

    def update_document_report(self, document_id: str, report: Dict, status: Optional[str] = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE documents SET parse_report_json=?, status=COALESCE(?, status), updated_at=? WHERE document_id=?",
                (_json(report), status, now_iso(), document_id),
            )

    def save_pages(self, document_id: str, pages: Sequence[Dict], failed_pages: Optional[Sequence[Dict]] = None) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM pages WHERE document_id=?", (document_id,))
            for page in pages:
                conn.execute(
                    """
                    INSERT INTO pages(
                        document_id, page_no, text, raw_text, cleaned_text, method, extraction_method, ocr_backend, ocr_confidence,
                        is_scanned_page, failure_reason, quality_stats_json, char_count, is_ocr, error
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        page.get("page_number", page.get("page")),
                        page.get("text", ""),
                        page.get("raw_text", page.get("text", "")),
                        page.get("cleaned_text", page.get("text", "")),
                        page.get("method", page.get("extraction_method", "")),
                        page.get("extraction_method", page.get("method", "")),
                        page.get("ocr_backend", ""),
                        page.get("ocr_confidence"),
                        1 if page.get("is_scanned_page") else 0,
                        page.get("failure_reason", page.get("error", "")),
                        _json(page.get("quality_stats", {})),
                        int(page.get("char_count") or len(page.get("text", ""))),
                        1 if page.get("is_ocr") or page.get("is_ocr_text") else 0,
                        page.get("error"),
                    ),
                )
            for page in failed_pages or []:
                conn.execute(
                    """
                    INSERT INTO pages(
                        document_id, page_no, text, raw_text, cleaned_text, method, extraction_method, ocr_backend, ocr_confidence,
                        is_scanned_page, failure_reason, quality_stats_json, char_count, is_ocr, error
                    )
                    VALUES(?, ?, '', '', '', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        document_id,
                        page.get("page_number", page.get("page")),
                        page.get("method", page.get("extraction_method", "")),
                        page.get("extraction_method", page.get("method", "")),
                        page.get("ocr_backend", ""),
                        page.get("ocr_confidence"),
                        1 if page.get("is_scanned_page") else 0,
                        page.get("failure_reason", page.get("error", "解析失败")),
                        _json(page.get("quality_stats", {})),
                        1 if "ocr" in str(page.get("method", page.get("extraction_method", ""))).lower() else 0,
                        page.get("error", page.get("failure_reason", "解析失败")),
                    ),
                )

    def get_pages(self, document_id: str) -> List[Dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT page_no, text, method, extraction_method, ocr_backend, ocr_confidence, is_scanned_page,
                       failure_reason, quality_stats_json, char_count, is_ocr, error, raw_text, cleaned_text
                FROM pages WHERE document_id=? ORDER BY COALESCE(page_no, id), id
                """,
                (document_id,),
            ).fetchall()
        return [
            {
                "page": row["page_no"],
                "page_number": row["page_no"],
                "text": row["text"],
                "raw_text": row["raw_text"],
                "cleaned_text": row["cleaned_text"] or row["text"],
                "method": row["method"],
                "extraction_method": row["extraction_method"] or row["method"],
                "ocr_backend": row["ocr_backend"],
                "ocr_confidence": row["ocr_confidence"],
                "is_scanned_page": bool(row["is_scanned_page"]),
                "failure_reason": row["failure_reason"] or row["error"],
                "quality_stats": _loads(row["quality_stats_json"], {}),
                "char_count": row["char_count"],
                "is_ocr": bool(row["is_ocr"]),
                "is_ocr_text": bool(row["is_ocr"]),
                "error": row["error"],
            }
            for row in rows
        ]

    def save_fragments(self, fragments: Sequence[Dict]) -> int:
        if not fragments:
            return 0
        document_ids = sorted({f.get("document_id") for f in fragments if f.get("document_id")})
        with self.connect() as conn:
            for document_id in document_ids:
                conn.execute("DELETE FROM fragments WHERE document_id=?", (document_id,))
                conn.execute("DELETE FROM fragments_fts WHERE document_id=?", (document_id,))
            for f in fragments:
                meta = {k: v for k, v in f.items() if k not in {"text", "embedding_json", "embedding"}}
                doc_id = f.get("doc_id") or f.get("document_id")
                doc_name = f.get("doc_name") or f.get("file_name")
                chapter = f.get("chapter") or f.get("chapter_name")
                section = f.get("section") or f.get("section_name")
                chunk_type = f.get("chunk_type") or f.get("content_type")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fragments(
                        chunk_id, course_id, document_id, doc_id, file_name, doc_name, course_name, chapter_id,
                        chapter_name, chapter, section_name, section, subsection, page_start, page_end,
                        content_type, chunk_type, knowledge_points_json, difficulty, source_path, source_refs_json,
                        created_at, text, embedding_id, embedding_json, is_ocr, has_formula, has_example,
                        has_exercise, metadata_json
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.get("chunk_id"),
                        f.get("course_id"),
                        f.get("document_id"),
                        doc_id,
                        f.get("file_name"),
                        doc_name,
                        f.get("course_name"),
                        f.get("chapter_id"),
                        f.get("chapter_name"),
                        chapter,
                        f.get("section_name"),
                        section,
                        f.get("subsection", ""),
                        f.get("page_start"),
                        f.get("page_end"),
                        f.get("content_type"),
                        chunk_type,
                        _json(f.get("knowledge_points", [])),
                        f.get("difficulty"),
                        f.get("source_path"),
                        _json(f.get("source_refs", [])),
                        f.get("created_at") or now_iso(),
                        f.get("text", ""),
                        f.get("embedding_id", ""),
                        _json(f.get("embedding_json") or f.get("embedding") or []),
                        1 if f.get("is_ocr") or f.get("is_ocr_text") else 0,
                        1 if f.get("has_formula") else 0,
                        1 if f.get("has_example") else 0,
                        1 if f.get("has_exercise") else 0,
                        _json(meta),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO fragments_fts(chunk_id, course_id, document_id, chapter, section, chunk_type, text)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.get("chunk_id"),
                        f.get("course_id"),
                        f.get("document_id"),
                        chapter or "",
                        section or "",
                        chunk_type or "",
                        f.get("text", ""),
                    ),
                )
        return len(fragments)

    def update_fragment_embeddings(self, embeddings_by_id: Dict[str, List[float]]) -> None:
        with self.connect() as conn:
            for chunk_id, vector in embeddings_by_id.items():
                conn.execute(
                    "UPDATE fragments SET embedding_id=?, embedding_json=? WHERE chunk_id=?",
                    (f"emb_{chunk_id}", _json(vector), chunk_id),
                )

    def get_fragments(
        self,
        course_id: Optional[str] = None,
        filters: Optional[Dict] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        clauses: List[str] = []
        params: List = []
        if course_id:
            clauses.append("course_id=?")
            params.append(course_id)
        filters = filters or {}
        mapping = {
            "document_id": "document_id",
            "chapter_name": "chapter_name",
            "section_name": "section_name",
            "section": "section",
            "content_type": "content_type",
            "chunk_type": "chunk_type",
            "difficulty": "difficulty",
            "file_name": "file_name",
            "doc_id": "doc_id",
            "doc_name": "doc_name",
        }
        for key, col in mapping.items():
            if key not in filters or filters[key] in (None, ""):
                continue
            value = filters[key]
            if isinstance(value, (list, tuple, set)):
                marks = ",".join("?" for _ in value)
                clauses.append(f"{col} IN ({marks})")
                params.extend(list(value))
            else:
                clauses.append(f"{col}=?")
                params.append(value)
        if "page_start" in filters:
            clauses.append("page_start>=?")
            params.append(filters["page_start"])
        if "page_end" in filters:
            clauses.append("page_end<=?")
            params.append(filters["page_end"])

        sql = "SELECT * FROM fragments"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY document_id, page_start, rowid"
        if limit:
            sql += f" LIMIT {int(limit)}"

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._fragment_from_row(row) for row in rows]

    def get_fragment_by_id(self, chunk_id: str) -> Optional[Dict]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM fragments WHERE chunk_id=?", (chunk_id,)).fetchone()
        return self._fragment_from_row(row) if row else None

    @staticmethod
    def _fragment_from_row(row) -> Dict:
        item = dict(row)
        item["knowledge_points"] = _loads(item.pop("knowledge_points_json", "[]"))
        item["embedding"] = _loads(item.pop("embedding_json", "[]"))
        item["source_refs"] = _loads(item.pop("source_refs_json", "[]"))
        item["is_ocr"] = bool(item["is_ocr"])
        item["is_ocr_text"] = bool(item["is_ocr"])
        item["has_formula"] = bool(item["has_formula"])
        item["has_example"] = bool(item["has_example"])
        item["has_exercise"] = bool(item["has_exercise"])
        meta = _loads(item.pop("metadata_json", "{}"), {})
        if isinstance(meta, dict):
            for key, value in meta.items():
                item.setdefault(key, value)
        return item

    def keyword_search_fts(self, course_id: Optional[str], query: str, filters: Optional[Dict] = None, limit: int = 20) -> List[Dict]:
        filters = filters or {}
        clauses = ["fragments_fts MATCH ?"]
        params: List = [query]
        if course_id:
            clauses.append("fragments_fts.course_id=?")
            params.append(course_id)
        if filters.get("document_id") or filters.get("doc_id"):
            clauses.append("fragments_fts.document_id=?")
            params.append(filters.get("document_id") or filters.get("doc_id"))
        if filters.get("chapter_name") or filters.get("chapter"):
            clauses.append("fragments_fts.chapter=?")
            params.append(filters.get("chapter_name") or filters.get("chapter"))
        if filters.get("section_name") or filters.get("section"):
            clauses.append("fragments_fts.section=?")
            params.append(filters.get("section_name") or filters.get("section"))
        if filters.get("content_type") or filters.get("chunk_type"):
            clauses.append("fragments_fts.chunk_type=?")
            params.append(filters.get("content_type") or filters.get("chunk_type"))
        sql = f"""
            SELECT fragments.chunk_id, bm25(fragments_fts) AS rank
            FROM fragments_fts
            JOIN fragments ON fragments.chunk_id = fragments_fts.chunk_id
            WHERE {' AND '.join(clauses)}
            ORDER BY rank
            LIMIT ?
        """
        params.append(limit)
        try:
            with self.connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            raise StorageError(f"FTS 查询失败，请确认 schema 已迁移: {exc}") from exc
        hits = []
        for row in rows:
            frag = self.get_fragment_by_id(row["chunk_id"])
            if frag:
                frag["keyword_score"] = 1.0 / (1.0 + abs(float(row["rank"])))
                hits.append(frag)
        return hits

    def keyword_search_like(self, course_id: Optional[str], query: str, filters: Optional[Dict] = None, limit: int = 20) -> List[Dict]:
        filters = dict(filters or {})
        tokens = [x for x in query.split() if x] or [query]
        clauses = ["(" + " OR ".join("text LIKE ?" for _ in tokens) + ")"]
        params: List = [f"%{token}%" for token in tokens]
        if course_id:
            clauses.append("course_id=?")
            params.append(course_id)
        for key, col in {
            "document_id": "document_id",
            "doc_id": "doc_id",
            "chapter_name": "chapter",
            "chapter": "chapter",
            "section_name": "section",
            "section": "section",
            "content_type": "chunk_type",
            "chunk_type": "chunk_type",
        }.items():
            if key in filters and filters[key]:
                clauses.append(f"{col}=?")
                params.append(filters[key])
        sql = f"SELECT chunk_id FROM fragments WHERE {' AND '.join(clauses)} ORDER BY page_start LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        hits = []
        for row in rows:
            frag = self.get_fragment_by_id(row["chunk_id"])
            if frag:
                frag["keyword_score"] = 0.5
                hits.append(frag)
        return hits

    def save_knowledge_points(self, course_id: str, document_id: str, chapter: Dict, points: Sequence[Dict]) -> int:
        if not points:
            return 0
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM knowledge_points WHERE document_id=? AND chapter_id=?",
                (document_id, chapter.get("chapter_id")),
            )
            for p in points:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO knowledge_points(
                        kp_id, course_id, document_id, chapter_id, chapter_name, name, definition,
                        formulas_json, examples_json, exercises_json, question_types_json, prerequisites_json,
                        applications_json, confusable_json, tags_json, difficulty, source_refs_json
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p.get("kp_id"),
                        course_id,
                        document_id,
                        chapter.get("chapter_id"),
                        chapter.get("chapter_name"),
                        p.get("name"),
                        p.get("definition", ""),
                        _json(p.get("formulas", [])),
                        _json(p.get("examples", [])),
                        _json(p.get("exercises", [])),
                        _json(p.get("question_types", [])),
                        _json(p.get("prerequisites", [])),
                        _json(p.get("applications", [])),
                        _json(p.get("confusable_with", [])),
                        _json(p.get("tags", [])),
                        p.get("difficulty", "中等"),
                        _json([{
                            "document_id": document_id,
                            "chapter_name": chapter.get("chapter_name"),
                            "page_start": chapter.get("page_start"),
                            "page_end": chapter.get("page_end"),
                        }]),
                    ),
                )
        return len(points)

    def get_knowledge_points(self, course_id: str, document_id: Optional[str] = None) -> List[Dict]:
        params: List = [course_id]
        sql = "SELECT * FROM knowledge_points WHERE course_id=?"
        if document_id:
            sql += " AND document_id=?"
            params.append(document_id)
        sql += " ORDER BY chapter_id, name"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in (
                "formulas_json", "examples_json", "exercises_json", "question_types_json",
                "prerequisites_json", "applications_json", "confusable_json", "tags_json", "source_refs_json"
            ):
                item[key.replace("_json", "")] = _loads(item.pop(key), [])
            item["confusable_with"] = item.pop("confusable", [])
            result.append(item)
        return result

    def get_documents(self, course_id: Optional[str] = None) -> List[Dict]:
        sql = "SELECT * FROM documents"
        params: List = []
        if course_id:
            sql += " WHERE course_id=?"
            params.append(course_id)
        sql += " ORDER BY updated_at DESC"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        docs = []
        for row in rows:
            item = dict(row)
            item["errors"] = _loads(item.pop("error_json", "[]"))
            item["parse_report"] = _loads(item.pop("parse_report_json", "{}"), {})
            docs.append(item)
        return docs

    def get_document(self, document_id: str) -> Optional[Dict]:
        docs = [d for d in self.get_documents() if d["document_id"] == document_id]
        return docs[0] if docs else None

    def get_chapter_names(self, course_id: str) -> List[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT chapter_name FROM fragments WHERE course_id=? AND chapter_name IS NOT NULL ORDER BY chapter_name",
                (course_id,),
            ).fetchall()
        return [row["chapter_name"] for row in rows if row["chapter_name"]]

    def delete_document(self, document_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM pages WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM fragments WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM fragments_fts WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM knowledge_points WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM documents WHERE document_id=?", (document_id,))


def save_fragments_to_db(fragments: Sequence[Dict], db_path: Optional[str] = None) -> int:
    """保存文本片段到关系型数据库。"""
    return CourseDB(db_path).save_fragments(fragments)


__all__ = [
    "CourseDB",
    "DEFAULT_DB_PATH",
    "save_fragments_to_db",
    "now_iso",
]
