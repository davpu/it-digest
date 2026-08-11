# News auto-digest POC

A small personal "IT digest": RSS aggregator with optional LLM summarization,
exposed as an **MCP server** for Claude Code / Claude Desktop (plus a FastAPI
HTTP layer). Built as a hobby project "delve into Python", focused on asyncio, raw SQL, the Anthropic API and the Model
Context Protocol.

# README CONTENTS:
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Design decisions](#design-decisions)
- [Getting started](#getting-started)
- [Development](#development)
- [Configuration](#configuration)
- [Repo structure](#repo-structure)

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

## Getting started

You will need two tools installed:

- [uv](https://docs.astral.sh/uv/getting-started/installation/) - Python
  package manager (also installs Python itself if you have none)
- [Claude Code](https://code.claude.com/docs) - the MCP host you will talk to

You do not "run" this app directly - you clone it, register it as an MCP
server and then talk to it through Claude. In your terminal:

```bash
git clone https://github.com/davpu/it-digest
cd it-digest
uv sync
claude mcp add it-digest -- uv run --directory "$(pwd)" python src/mcp_server.py
```

The registration is scoped to the directory you run `claude mcp add` from -
start your Claude Code sessions there (`cd it-digest && claude`) to see the
server.

Then just ask, in plain language:

- *"fetch the latest articles and give me an overview of today's AI news"*
- *"did we have anything about Kubernetes lately?"*

or use the built-in prompt template as a one-click action:
`/mcp__it-digest__daily_digest` (arguments: `topic`, `days`).

Phase 2 (`make_digest`, module `llm.py`) needs `ANTHROPIC_API_KEY` in `.env`
(see `.env.example`).

## Development

Each module doubles as a smoke test when run directly:

```bash
uv run python src/ingest.py      # feed fetching
uv run python src/storage.py     # SQLite layer
```

## Configuration

Everything model- or content-facing lives outside the code:

- `feeds.txt` - **what to digest from**: one feed URL per line; while empty,
  the app runs on bundled defaults (`DEFAULT_FEEDS` in `src/ingest.py`)
- `prompts/interests.md` - default relevance profile for the LLM
  classification step (phase 2)
- **what to digest**: the `daily_digest` prompt template and the
  `get_articles_for_digest` tool both take an optional `topic`, so the same
  archive can produce an AI digest, a security digest, or anything else

## Repo structure

- `src/` - the code (5 modules, see diagram)
- `prompts/` - model-facing text kept out of code

The MCP server also exposes a `daily_digest(topic, days)` prompt template
(MCP prompts primitive), so hosts can offer the whole flow as a one-click
action.
