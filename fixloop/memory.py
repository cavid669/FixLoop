from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


DB_DIR = Path.home() / ".fixloop"
DB_PATH = DB_DIR / "fixloop.db"


@dataclass
class MemoryHit:
    id: int
    created_at: str
    score: float
    stderr_excerpt: str
    diff_excerpt: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _ensure_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Base table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            cmd TEXT NOT NULL,
            file_path TEXT NOT NULL,
            stderr TEXT NOT NULL,
            stderr_hash TEXT NOT NULL,
            diff TEXT NOT NULL,
            new_file_hash TEXT NOT NULL
        );
        """
    )

    # Try create FTS5 index (optional but preferred)
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS fixes_fts
            USING fts5(
                stderr,
                diff,
                content='fixes',
                content_rowid='id'
            );
            """
        )
        # Triggers to keep FTS in sync
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS fixes_ai AFTER INSERT ON fixes BEGIN
                INSERT INTO fixes_fts(rowid, stderr, diff) VALUES (new.id, new.stderr, new.diff);
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS fixes_ad AFTER DELETE ON fixes BEGIN
                INSERT INTO fixes_fts(fixes_fts, rowid, stderr, diff) VALUES('delete', old.id, old.stderr, old.diff);
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS fixes_au AFTER UPDATE ON fixes BEGIN
                INSERT INTO fixes_fts(fixes_fts, rowid, stderr, diff) VALUES('delete', old.id, old.stderr, old.diff);
                INSERT INTO fixes_fts(rowid, stderr, diff) VALUES (new.id, new.stderr, new.diff);
            END;
            """
        )
        conn.commit()
    except sqlite3.OperationalError:
        # FTS5 not available; that's okay. We'll do fallback.
        pass

    return conn


def save_fix(cmd: str, file_path: str, stderr: str, diff: str, new_file_content: str) -> None:
    """
    Save a successful fix to the local SQLite knowledge base.
    """
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    stderr = (stderr or "").strip()
    diff = (diff or "").strip()

    if not stderr or not diff:
        return

    stderr_hash = _sha256(stderr[:4000])
    new_hash = _sha256(new_file_content[:8000])

    conn = _ensure_db()
    try:
        conn.execute(
            """
            INSERT INTO fixes(created_at, cmd, file_path, stderr, stderr_hash, diff, new_file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (created_at, cmd, file_path, stderr[:20000], stderr_hash, diff[:20000], new_hash),
        )
        conn.commit()
    finally:
        conn.close()


def _fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM fixes_fts LIMIT 1;")
        return True
    except sqlite3.OperationalError:
        return False


def search_similar(stderr: str, limit: int = 3) -> List[MemoryHit]:
    """
    Search the knowledge base for similar errors.
    Returns top hits with small excerpts to feed into the AI prompt.
    """
    stderr = (stderr or "").strip()
    if not stderr:
        return []

    conn = _ensure_db()
    try:
        hits: List[MemoryHit] = []

        if _fts_available(conn):
            # Use FTS5 + bm25 ranking (lower is better)
            rows = conn.execute(
                """
                SELECT f.id, f.created_at,
                       bm25(fixes_fts) AS score,
                       substr(f.stderr, 1, 600) AS stderr_excerpt,
                       substr(f.diff, 1, 600) AS diff_excerpt
                FROM fixes_fts
                JOIN fixes f ON f.id = fixes_fts.rowid
                WHERE fixes_fts MATCH ?
                ORDER BY score ASC
                LIMIT ?;
                """,
                (_fts_query(stderr), limit),
            ).fetchall()

            for r in rows:
                hits.append(
                    MemoryHit(
                        id=int(r["id"]),
                        created_at=str(r["created_at"]),
                        score=float(r["score"]),
                        stderr_excerpt=str(r["stderr_excerpt"]),
                        diff_excerpt=str(r["diff_excerpt"]),
                    )
                )
            return hits

        # Fallback: hash-prefix similarity (cheap, works everywhere)
        target = _sha256(stderr[:4000])
        rows = conn.execute(
            """
            SELECT id, created_at, stderr, diff
            FROM fixes
            ORDER BY id DESC
            LIMIT 200;
            """
        ).fetchall()

        # simple score: count matching prefix chars between hashes
        def score_hash(a: str, b: str) -> float:
            n = 0
            for x, y in zip(a, b):
                if x == y:
                    n += 1
                else:
                    break
            return float(n)

        scored = []
        for r in rows:
            s = score_hash(target, str(r["stderr"]).encode("utf-8", errors="ignore").hex()[:64])
            scored.append((s, r))

        scored.sort(key=lambda t: t[0], reverse=True)
        for s, r in scored[:limit]:
            hits.append(
                MemoryHit(
                    id=int(r["id"]),
                    created_at=str(r["created_at"]),
                    score=float(s),
                    stderr_excerpt=str(r["stderr"])[:600],
                    diff_excerpt=str(r["diff"])[:600],
                )
            )
        return hits

    finally:
        conn.close()


def _fts_query(stderr: str) -> str:
    """
    Build a conservative FTS query.
    We take key tokens, remove noise, and join with OR.
    """
    tokens = []
    for raw in stderr.replace("\r", "\n").split():
        t = raw.strip().strip("()[]{}:,;\"'")
        if len(t) < 4:
            continue
        if t.lower() in {"traceback", "error", "exception", "line", "file"}:
            continue
        tokens.append(t)

    # Keep it short
    tokens = tokens[:12] if tokens else ["TypeError", "ValueError"]

    # OR query
    # Example: token1 OR token2 OR token3
    return " OR ".join(tokens)
