# it-digest

A small personal "IT digest": RSS aggregator with optional LLM summarization,
exposed as an **MCP server** for Claude Code / Claude Desktop (plus a FastAPI
HTTP layer). Built as a learning project - a TypeScript/Node developer's road
into Python, focused on asyncio, raw SQL, the Anthropic API and the Model
Context Protocol.

## What it does

Register the server in Claude Code and ask *"fetch the latest articles and
give me an overview of today's AI news"*. The model calls the `fetch_latest`
and `get_articles_for_digest` tools on its own and writes the digest from the
source material:

> **Today's AI news (Aug 11, 2026)**
>
> *Local and edge inference - today's strongest theme*
> - H3-metal (391 pts) - antirez wrote native MiniMax-H3 inference for Apple
>   Silicon in plain C. The biggest AI story of the day on HN.
> - Needle 2 (472 pts) - a 14 MB agentic LLM: tool calls and structured
>   extraction on phones and Raspberry Pi 5 (~500 tok/s).
>
> *Business and society*
> - As AI eats the web (693 pts, 744 comments) - how AI answers drain the
>   web...

## Architecture

```
                    ┌─────────────────────────┐
  RSS/Atom feeds ──▶│  ingest.py              │
  (httpx async,     │  httpx.AsyncClient      │
   N sources        │  + feedparser (sync!)   │
   in parallel)     │  → list[Article]        │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  storage.py             │
                    │  SQLite, raw SQL        │
                    │  articles, sources      │
                    │  dedup via UNIQUE(url)  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  llm.py                 │
                    │  Anthropic API:         │
                    │  classify (Haiku)       │
                    │  → rank → summarize     │
                    │  (Opus), structured out │
                    └────────────┬────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                                ▼
    ┌─────────────────────────┐     ┌─────────────────────────┐
    │  mcp_server.py          │     │  api.py                 │
    │  MCPServer, stdio       │     │  FastAPI, Pydantic      │
    │  tools: fetch_latest,   │     │  GET /digest/latest     │
    │  search_archive,        │     │  GET /articles          │
    │  make_digest            │     │                         │
    └─────────────────────────┘     └─────────────────────────┘
         ▲
         │ stdio transport
    Claude Code / Claude Desktop (MCP host)
```

Both end modules are thin layers over the same functions - an MCP tool and an
HTTP endpoint do the same thing over a different transport. An "MCP server" is
not magic; it is another way to call a function you already have.

## Design decisions

- **Two phases of intelligence.** Phase 1 MCP tools (`fetch_latest`,
  `search_archive`, `get_articles_for_digest`) return data only - the host
  model does the synthesis, so the server needs no API key. Phase 2
  (`make_digest`) runs its own pipeline against the Anthropic API: a cheap
  model (Haiku) classifies every article, a stronger one (Opus) only
  summarizes the top N. With MCP you have to decide on which side the LLM
  call runs - both variants live here side by side on purpose.
- **SQLite + raw SQL, no ORM.** A local single-user tool: the DB is one file,
  dedup is `UNIQUE(url)` + `INSERT OR IGNORE`, every query is parametrized.
  On a bigger schema I would reach for SQLAlchemy/SQLModel for the same
  reasons I use Drizzle in TypeScript.
- **feedparser runs via `asyncio.to_thread`.** No blocking calls inside async
  code - either the library has an async variant (httpx), or it goes to a
  worker thread.
- **One dead feed never kills the run.** `fetch_feed` returns `None` instead
  of raising; a failing source is skipped and the rest proceed.

## Running it

```bash
uv sync
uv run python src/ingest.py      # test feed fetching
uv run python src/storage.py     # test the SQLite layer

# register the MCP server in Claude Code:
claude mcp add it-digest -- uv run --directory /path/to/it-digest python src/mcp_server.py
```

Phase 2 (`make_digest`, module `llm.py`) needs `ANTHROPIC_API_KEY` in `.env`
(see `.env.example`).

## Repo structure

- `src/` - the code (5 modules, see diagram)
- `prompts/` - model-facing text kept out of code: `interests.md` drives the
  classification step, editable without touching Python

The MCP server also exposes a `daily_digest` prompt template (MCP prompts
primitive), so hosts can offer the whole flow as a one-click action.

Feeds are configured in `ingest.py` (`FEED_URLS`).
