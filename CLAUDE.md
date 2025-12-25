# CLAUDE.md

AI operations platform using LangGraph multi-agent orchestration with human approval workflows.

**Stack:** Next.js 16, React 19, Tailwind CSS 4, Bun · FastAPI, Python, uv · LangGraph, LangChain · PostgreSQL, Qdrant · Docker Compose

---

## Priorities

1. Correctness
2. Consistency with existing architecture
3. Simplicity
4. Readability
5. Performance

When priorities conflict, higher numbers yield to lower numbers. Never trade reliability for speed — prefer explicit transactions, typed contracts, and safe defaults over shortcuts.

---

## Code Decisions

**Use existing repo patterns first.** Before writing anything new, check for shared utilities, service layers, reusable components, or internal wrappers that already solve the problem.

**Decision order:**

1. Existing repo solution
2. Existing approved dependency
3. Small adapter around a dependency
4. New custom implementation

**Write custom code only when:** requirements are highly specific, a library adds excessive complexity, or security/compliance requires internal control.

---

## Architecture

### Agent Graph (`backend/agents/graph.py`)

LangGraph state machine. Flow:

```
START → router → orchestrator → [sales | inventory | marketing | customer_support] (fan-out)
                                              ↓ (fan-in)
                                          aggregator → reflector ──(needs more data)──→ orchestrator
                                                            ↓
                                               hitl (if action_requested) → interrupt()
                                                            ↓
                                                    final_response → END
```

State is persisted via `AsyncPostgresSaver` (falls back to `MemorySaver` in dev — if graph state behaves unexpectedly locally, this is why).

### Declarative Agents (`backend/agents/configs/*.yml`)

Each agent is a YAML file with:

- `system_prompt` — agent instructions
- `user_prompt_template` — Python `string.Template` with `$variable` substitution
- `tools` — whitelist of MCP tool names the agent may call
- `structured_output` — optional Pydantic schema name
- `max_iterations` — LangChain recursion limit

`Agent.run()` in `factory.py` has four modes — choose based on what the agent needs:

| Mode                       | When to use                                                            |
| -------------------------- | ---------------------------------------------------------------------- |
| Structured only (no tools) | Single LLM call, typed output, no tool access needed                   |
| Tools + structured         | Run tool loop first, then force structured output on full conversation |
| Tool-calling               | Full LangChain agent with tool discretion                              |
| Plain LLM                  | No tools, no schema (e.g. `final_response`)                            |

Agents are lazily created and cached per-process in `nodes.py::_agent_cache`. Cache clears on MCP registry reinit (triggered at startup or when `MCPClientRegistry` is re-initialized).

### MCP Tools (`mcp_servers/`)

Separate Python package (`mcp-operations`) running as a FastMCP server on port 8001 (HTTP streamable, internal Docker only — not exposed to host).

Tools by domain:

- `sales/` — `get_daily_sales_metrics`, `compare_sales_periods`, `detect_revenue_anomalies`
- `inventory/` — `get_inventory_snapshot`, `get_stockout_impact`
- `marketing/` — `get_campaign_status`
- `customer_support/` — `get_customer_support_snapshot`
- `memory/` — `search_past_incidents` (Qdrant vector search)

`MCPClientRegistry` (`backend/agents/mcp_registry.py`) connects at startup, loads tools, and filters by the `USE_MCP_TOOLS` env var (comma-separated tool names; empty = all tools enabled).

**Adding a new MCP tool:**

1. Add to `mcp_servers/domains/<domain>/tools.py`
2. Register in `mcp_servers/server.py`
3. Update `domains/tool_registry.py` in **both** `backend/` and `mcp_servers/`
4. Add the tool name to the relevant agent config YAML under `tools`

### HITL — Human-in-the-Loop

When `action_requested=True` or `reflection.action_required=True`, `hitl_node`:

1. Persists an incident + pending action rows to Postgres
2. Calls `interrupt()` to pause the graph
3. Returns action rows to the frontend via the streaming response

The frontend `HitlActionCard` shows approve/reject. Approval hits `POST /api/v1/actions/{id}/approve`, which resumes the graph via `graph.ainvoke` with the interrupt resolved.

### Frontend (`frontend/`)

Next.js 16 / React 19 / Tailwind CSS 4.

Key files:

- `hooks/use-chat.ts` — SSE streaming from `/api/v1/query`
- `lib/api.ts` — typed API client
- `components/chat/` — chat UI and HITL action card

**SSE stream format** (`/api/v1/query`): the frontend consumes newline-delimited JSON events. Any backend change to this endpoint must preserve the existing event shape — breaking this will silently break the UI. Check `use-chat.ts` before touching the query endpoint.

> See `frontend/AGENTS.md` — Next.js 16 has breaking changes from older versions. Read `node_modules/next/dist/docs/` before editing frontend code.

### Databases

- **PostgreSQL** (host port 5431): application DB — threads, incidents, actions, e-commerce data. Migrations via Alembic (`backend/db/migrations/`). Do not hand-edit migration files; generate them with `alembic revision --autogenerate`.
- **Qdrant** (port 6333): vector store for memory/past incidents, embedded with `sentence-transformers`.

### LLM Provider

Azure OpenAI via DIAL proxy. Config from `DIAL_API_KEY`, `DIAL_ENDPOINT`, `DIAL_API_VERSION`, `DIAL_DEPLOYMENT` env vars. LLM is a singleton created by `factory.py::_get_llm()` (LRU-cached).

---

## Common Workflows

### Adding a new agent

1. Create `backend/agents/configs/<name>.yml` with `system_prompt`, `tools`, and optionally `structured_output`
2. Add a node function in `backend/agents/nodes.py` using `_agent_cache`
3. Wire the node into the graph in `graph.py`
4. Add domain tools to `tool_registry.py` if the agent needs new MCP tools

### Adding a new API endpoint

1. Add route in `backend/api/routes/`
2. Use existing FastAPI dependency patterns for DB sessions and auth
3. Raise `HTTPException` for user-facing errors; log unexpected exceptions before re-raising
4. Add contract tests in `tests/test_contracts.py`

### Adding a DB model + migration

1. Define model in `backend/db/models/`
2. Run `uv run alembic revision --autogenerate -m "description"`
3. Review the generated migration before committing — autogenerate misses some cases (e.g. custom types, constraints)
4. Apply with `uv run alembic upgrade head`

---

## Error Handling

- **User-facing errors:** raise `HTTPException` with an appropriate status code
- **Unexpected errors:** log with context, then re-raise — do not silently swallow
- **Agent errors:** surface via the graph's state, not bare exceptions; let the reflector handle recoverable failures

---

## Testing

| File                      | What goes here                                                |
| ------------------------- | ------------------------------------------------------------- |
| `tests/test_contracts.py` | Schema and API contract tests — no external deps, always fast |
| `tests/test_graph.py`     | Graph integration tests — requires live MCP server + DB       |
| `tests/test_evals.py`     | DeepEval LLM-judge tests — slow, run deliberately             |

New MCP tools need a domain test in `mcp_servers/tests/`. New API endpoints need a contract test. Graph-level behavior changes need a graph test. Mock external services (LLM, Qdrant) in unit tests; use real services only in integration tests.

---

## Running the System

```bash
cp .env.example .env
# Required: DIAL_API_KEY, DIAL_ENDPOINT, DIAL_API_VERSION, DIAL_DEPLOYMENT
# Required: LANGFUSE_* vars, CLICKHOUSE_PASSWORD, MINIO_ROOT_PASSWORD

docker compose up --build          # Full stack
SEED_DB=true docker compose up     # Seed DB on first run
```

Services:

- Frontend: http://localhost:3001
- Backend API: http://localhost:8000
- Langfuse: http://localhost:3000 (`admin@local.dev` / `LANGFUSE_INIT_USER_PASSWORD`)
- MCP server: internal only (`http://mcp-operations:8001`)

**Do not modify Langfuse stack configs** (`langfuse`, `clickhouse`, `redis`, `minio` services in `docker-compose.yml`) unless explicitly asked.

---

## Dev Commands

**Backend** (from `backend/`):

```bash
uv run pytest                          # All tests
uv run pytest tests/test_contracts.py  # Contract tests only (fast, no deps)
uv run ruff check . && uv run ruff format .
uv run alembic upgrade head
uv run uvicorn main:app --reload --port 8000  # Local (needs postgres + qdrant + mcp-server)
```

**MCP server** (from `mcp_servers/`):

```bash
uv run pytest
uv run python -m server   # Start on port 8001
```

**Frontend** (from `frontend/`):

```bash
bun install && bun dev     # Dev server on port 3001
bun run test:run           # Tests (no watch)
```
