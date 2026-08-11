"""SQLite storage layer.

Schema (sources, articles), dedup by article URL (UNIQUE + INSERT OR IGNORE)
and the queries used by the MCP/HTTP layers. Raw SQL by design, no ORM;
every query is parametrized.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER NOT NULL REFERENCES sources(id),
    title        TEXT NOT NULL,
    url          TEXT NOT NULL UNIQUE,
    published_at TEXT,
    summary      TEXT,
    fetched_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
"""

def init_db(db_path: str = "digest.db") -> sqlite3.Connection:
    """Open (or create) the DB and ensure the schema exists; safe to call repeatedly."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn

def get_or_create_source(conn: sqlite3.Connection, name: str, url: str) -> int:
    """Return the id of the source with the given `url`, creating it if needed (idempotent)."""
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources (name, url) VALUES (?, ?)", (name, url)
        )
    row = conn.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()
    return row[0]

def save_articles(conn: sqlite3.Connection, source_id: int, articles: list) -> int:
    """Store articles for a source, deduped by URL; return the number actually inserted."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with conn:
        for article in articles:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO articles
                    (source_id, title, url, published_at, summary, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    article.title,
                    article.url,
                    article.published_at,
                    article.summary,
                    now,
                )
            )
            inserted += cursor.rowcount
    return inserted

def articles_since(conn: sqlite3.Connection, days: int) -> list[sqlite3.Row]:
    """Return articles fetched in the last `days` days, newest first."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = conn.execute(
        "SELECT * FROM articles WHERE fetched_at >= ? ORDER BY fetched_at DESC",
        (cutoff,),
    )
    return cursor.fetchall()

def articles_per_source(conn: sqlite3.Connection, min_count: int = 0) -> list[sqlite3.Row]:
    """Return (source_name, article_count) per source, descending by count.
    `min_count` filters out small sources (HAVING)."""
    cursor = conn.execute(
        """
        SELECT sources.name AS source_name, COUNT(*) AS article_count
        FROM articles
        JOIN sources ON sources.id = articles.source_id
        GROUP BY sources.name
        HAVING COUNT(*) >= ?
        ORDER BY article_count DESC
        """,
        (min_count,),
    )
    return cursor.fetchall()

def search_articles(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    """Case-insensitive substring search in title or summary."""
    pattern = f"%{query}%"
    cursor = conn.execute(
        """
        SELECT * FROM articles
        WHERE title LIKE ? OR summary LIKE ?
        ORDER BY fetched_at DESC
        """,
        (pattern, pattern),
    )
    return cursor.fetchall()


def _main() -> None:
    conn = init_db()
    conn.row_factory = sqlite3.Row

    source_id = get_or_create_source(conn, "Hacker News", "https://hnrss.org/frontpage")
    print(f"source_id = {source_id}")

    @dataclass
    class _TestArticle:
        title: str
        url: str
        published_at: str | None
        summary: str | None

    test_articles = [
        _TestArticle("Python 3.13 news", "https://example.com/py313", None, "what is new"),
        _TestArticle("MCP servers in practice", "https://example.com/mcp", None, None),
    ]
    print("1st insert:", save_articles(conn, source_id, test_articles), "(new rows)")
    print("2nd insert:", save_articles(conn, source_id, test_articles), "(dedup -> 0)")

    print("Articles from the last 7 days:", len(articles_since(conn, days=7)))
    print(
        "Articles per source:",
        [(r["source_name"], r["article_count"]) for r in articles_per_source(conn)],
    )
    print("Search 'python':", len(search_articles(conn, "python")))


if __name__ == "__main__":
    _main()