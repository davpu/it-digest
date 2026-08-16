"""LLM pipeline (work in progress).

Classify and rank articles by relevance (cheap model, runs per article),
then summarize the top-N into a markdown digest (larger model, runs once).
Structured output via Pydantic. Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

# Load ANTHROPIC_API_KEY (and any other config) from .env in the repo root,
# so it doesn't have to be exported in the shell - see .env.example.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Interests used in the classification prompt. Edit prompts/interests.md,
# no code change needed.
INTERESTS = (Path(__file__).resolve().parent.parent / "prompts" / "interests.md").read_text()

MODEL_CLASSIFY = "claude-haiku-4-5"
MODEL_SUMMARIZE = "claude-opus-5"


class ArticleClassification(BaseModel):
    relevant: bool
    topic: str
    interest_score: int  # 1-5


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def classify_article(client: anthropic.Anthropic, title: str, summary: str | None) -> ArticleClassification:
    """Classify one article against INTERESTS: relevance, topic, score 1-5."""
    raise NotImplementedError


def rank_articles(client: anthropic.Anthropic, articles: list) -> list[tuple]:
    """Classify all articles, drop irrelevant ones and return the rest as
    (article, classification) pairs sorted by interest score, descending."""
    raise NotImplementedError


def summarize_article(client: anthropic.Anthropic, title: str, summary: str | None, url: str) -> str:
    """Write a short (2-4 sentences) digest summary of one article."""
    raise NotImplementedError


def build_digest(client: anthropic.Anthropic, articles: list, top_n: int = 5) -> str:
    """Compose the final markdown digest from the top-N ranked articles."""
    raise NotImplementedError


def _main() -> None:
    client = _client()
    articles: list = []  # plug in ingest.ingest(...) results to test
    if not articles:
        print("No articles to test with - feed in ingest.ingest(...) results.")
        return
    digest = build_digest(client, articles, top_n=5)
    print(digest)


if __name__ == "__main__":
    _main()
