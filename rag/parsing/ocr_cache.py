"""SQLite-backed OCR cache."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Optional


class OCRCache:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.db_path = os.path.join(cache_dir, "ocr_cache.sqlite3")
        self.init_schema()

    def init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ocr_cache (
                    cache_key TEXT PRIMARY KEY,
                    doc_md5 TEXT,
                    page_number INTEGER,
                    backend TEXT,
                    dpi INTEGER,
                    lang TEXT,
                    preprocess_version TEXT,
                    text TEXT,
                    confidence REAL,
                    failure_reason TEXT,
                    elapsed_ms INTEGER,
                    created_at TEXT
                )
                """
            )

    @staticmethod
    def make_key(
        *,
        doc_md5: str,
        page_number: int,
        backend: str,
        dpi: int,
        lang: str,
        preprocess_version: str,
        preprocess_config_hash: str = "",
    ) -> str:
        raw = json.dumps(
            {
                "doc_md5": doc_md5,
                "page_number": page_number,
                "backend": backend,
                "dpi": dpi,
                "lang": lang,
                "preprocess_version": preprocess_version,
                "preprocess_config_hash": preprocess_config_hash or preprocess_version,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM ocr_cache WHERE cache_key=?", (cache_key,)).fetchone()
        return dict(row) if row else None

    def put(
        self,
        *,
        cache_key: str,
        doc_md5: str,
        page_number: int,
        backend: str,
        dpi: int,
        lang: str,
        preprocess_version: str,
        text: str,
        confidence: Optional[float],
        failure_reason: str = "",
        elapsed_ms: int = 0,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ocr_cache(
                    cache_key, doc_md5, page_number, backend, dpi, lang, preprocess_version,
                    text, confidence, failure_reason, elapsed_ms, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    doc_md5,
                    page_number,
                    backend,
                    dpi,
                    lang,
                    preprocess_version,
                    text,
                    confidence,
                    failure_reason,
                    elapsed_ms,
                    datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                ),
            )
