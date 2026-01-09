from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List


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

    # Try create FTS5 index (optional)
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
        # FTS5 not available - OK
        pass

    return conn


def _fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM fixes_fts LIMIT 1;")
        return True
    except sqlite3.OperationalError:
        return False


def _fts_query(stderr: str) -> str:
    """
    Build a safe FTS query for Windows:
    - drop drive-letter paths (C:\\...)
    - drop tokens containing slashes/backslashes
    - keep only [A-Za-z0-9_]
    - quote tokens to avoid FTS syntax issues
    """
    import re

    raw_tokens = stderr.replace("\r", "\n").split()
    tokens: List[str] = []

    for raw in raw_tokens:
        t = raw.strip()

        # Drop obvious Windows paths / drive letters
        if re.match(r"^[A-Za-z]:\\", t) or "\\" in t or "/" in t:
            continue

        # Keep only word-like parts
        t2 = re.sub(r"[^A-Za-z0-9_]", "", t)
        if len(t2) < 4:
            continue

        low = t2.lower()
        if low in {"traceback", "error", "exception", "line", "file", "most", "recent", "call", "last"}:
            continue

        tokens.append(t2)

    if not tokens:
        tokens = ["TypeError", "ValueError"]

    tokens = tokens[:10]
    return " OR ".join([f'"{tok}"' for tok in tokens])


def save_fix(cmd: str, file_path: str, stderr: str, diff: str, new_file_content: str) -> None:
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


def search_similar(stderr: str, limit: int = 3) -> List[MemoryHit]:
    stderr = (stderr or "").strip()
    if not stderr:
        return []

    conn = _ensure_db()
    try:
        hits: List[MemoryHit] = []

        if _fts_available(conn):
            try:
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

            except sqlite3.OperationalError:
                # If FTS query parsing fails, fallback safely
                pass

        # Fallback: LIKE search (works everywhere)
        # Use a small needle: last line or key phrase
        lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
        needle = lines[-1] if lines else stderr
        needle = needle[:120]

        rows = conn.execute(
            """
            SELECT id, created_at, stderr, diff
            FROM fixes
            WHERE stderr LIKE ?
            ORDER BY id DESC
            LIMIT ?;
            """,
            (f"%{needle}%", limit),
        ).fetchall()

        for r in rows:
            hits.append(
                MemoryHit(
                    id=int(r["id"]),
                    created_at=str(r["created_at"]),
                    score=0.0,
                    stderr_excerpt=str(r["stderr"])[:600],
                    diff_excerpt=str(r["diff"])[:600],
                )
            )

        return hits

    finally:
        conn.close()
