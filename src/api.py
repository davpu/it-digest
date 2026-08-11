"""HTTP API layer (work in progress).

FastAPI over the same database as the MCP server: GET /digest/latest and
GET /articles with optional source/days filters. Pydantic response models,
DB connection via dependency injection.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

import storage
import llm

app = FastAPI(title="it-digest API")

DB_PATH = "digest.db"


class ArticleOut(BaseModel):
    id: int
    title: str
    url: str
    published_at: str | None
    source_name: str


class DigestOut(BaseModel):
    generated_at: str
    days: int
    markdown: str


def get_db():
    """Per-request DB connection (FastAPI dependency with teardown)."""
    raise NotImplementedError


@app.get("/articles", response_model=list[ArticleOut])
async def list_articles(
    source: str | None = None,
    days: int = 7,
    db: sqlite3.Connection = Depends(get_db),
) -> list[ArticleOut]:
    """Articles from the last `days` days, optionally filtered by source name."""
    raise NotImplementedError


@app.get("/digest/latest", response_model=DigestOut)
async def get_latest_digest(
    days: int = 7,
    db: sqlite3.Connection = Depends(get_db),
) -> DigestOut:
    """Build and return the digest for the last `days` days."""
    raise NotImplementedError


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
