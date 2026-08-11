"""MCP server exposing the digest pipeline as tools.

Runs on stdio transport; register with an MCP host, e.g.:
claude mcp add it-digest -- uv run --directory <repo> python src/mcp_server.py
"""

from __future__ import annotations

import sqlite3

from mcp.server import MCPServer

import ingest
import storage

mcp = MCPServer("it-digest")

DB_PATH = "digest.db"


@mcp.tool()
async def fetch_latest() -> str:
    """Fetch the latest articles from all configured RSS feeds and store
    them (duplicates are skipped). Use when the user wants to refresh the
    archive or asks about the newest articles."""
    articles = await ingest.ingest(ingest.FEED_URLS)
    db_conn = storage.init_db(DB_PATH)

    try:
        by_source: dict[str, list] = {}

        for article in articles:
            by_source.setdefault(article.source_url, []).append(article)

        total_inserted = 0
        for source_url, source_articles in by_source.items():
            source_id = storage.get_or_create_source(db_conn, source_url, source_url)
            total_inserted += storage.save_articles(db_conn, source_id, source_articles)
    finally:
        db_conn.close()

    return f"Added {total_inserted} new articles from {len(by_source)} sources."

def db_connect() -> sqlite3.Connection:
    db_conn = storage.init_db(DB_PATH)
    db_conn.row_factory = sqlite3.Row

    return db_conn

@mcp.tool()
async def search_archive(query: str) -> str:
    """Search stored articles by keyword (matches title or summary).
    Use when the user asks about a specific topic from the archive."""
    db_conn = db_connect()

    try:
        rows = storage.search_articles(db_conn, query)
    finally:
        db_conn.close()

    if not rows:
        return "Nothing found."

    return "\n".join(f"- {row['title']} ({row['url']})" for row in rows)

@mcp.tool()
async def get_articles_for_digest(days: int = 7) -> str:
    """Return raw article data (title, URL, source, summary) from the last
    `days` days as a markdown list. Use when you (the host model) should
    write the digest yourself - this tool only provides the source material."""
    db_connection = db_connect()

    try:
        articles = storage.articles_since(db_connection, days)
        source_names = {
            row["id"]: row["name"] for row in db_connection.execute("SELECT id, name FROM sources")
        }
    finally:
        db_connection.close()

    if not articles:
        day_or_days_string = "days" if days != 1 else "day"
        return f"No new articles in {days} {day_or_days_string}."

    lines = [f"# Articles from the last {days} days ({len(articles)})", ""]
    for row in articles:
        source_name = source_names.get(row["source_id"], "?")
        lines.append(f"- [{row['title']}]({row['url']}) - {source_name}")

        if row["summary"]:
            lines.append(f"  {row['summary']}")

    return "\n".join(lines)

@mcp.tool()
async def make_digest(days: int = 7) -> str:
    """Build a ready-made markdown digest of the most relevant articles
    from the last `days` days using the server's own LLM pipeline.
    Not implemented yet - use get_articles_for_digest instead."""
    db_connection = db_connect()

    try:
        articles = storage.articles_since(db_connection, days)
    finally:
        db_connection.close()

    if not articles:
        return "Nothing to digest."

    raise NotImplementedError



@mcp.prompt()
def daily_digest(days: int = 1) -> str:
    """Reusable prompt: refresh the archive and write a themed digest."""
    return (
        f"Fetch the latest articles, then load the archive from the last {days} "
        "day(s) via get_articles_for_digest and write a digest: group articles "
        "by theme, keep bullets short, link every title, and end with a one-line "
        "note about what was left out."
    )


if __name__ == "__main__":
    mcp.run()
