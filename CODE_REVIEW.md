# Full Codebase Review — E-commerce Operations Assistant

---

## Executive Summary

| Metric | Score |
|---|---|
| **Overall Code Quality** | **6.5 / 10** |
| **Risk Score** | **7 / 10** (high — several production-breaking issues) |
| **Maintainability** | **6 / 10** |

**Main Concerns:**
1. **Production data destruction** — `entrypoint.sh` unconditionally wipes all tables on every container restart
2. **Hardcoded secrets** in `.env.example` mirrored as docker-compose fallback defaults
3. **SSE parser is fundamentally broken** — drops multi-line events, loses final event on disconnect
4. **No error boundaries** in the frontend — any runtime throw shows a blank white screen
5. **Race conditions** in the frontend hook (`useChat`) allow double-submission
6. **No AbortController** anywhere — memory leaks on unmount during SSE streaming
7. **Stale caching** — LLM singleton and agent cache never invalidate on MCP registry reconnect

**Highest ROI Improvements:**
1. Guard the seed script behind an env var (5 min fix, prevents production data loss)
2. Add `error.tsx` to Next.js app (10 min, prevents blank screen on errors)
3. Fix SSE parser or replace with `eventsource-parser` library (30 min)
4. Add AbortController to `postQueryStream` and `useChat` (20 min)
5. Parameterize CORS origins and secrets via environment variables (15 min)

---

## Findings

### [Severity: Critical]

**1. Seed script destroys production data on every container start**
- File(s): `backend/entrypoint.sh:8`, `backend/scripts/seed_data.py`
- Problem: `python -m scripts.seed_data` runs unconditionally after migrations. The seed function DELETEs all rows from every table before inserting mock data. Every container restart (crash, deploy, scale-up) wipes production data.
- Why it matters: Complete data loss in production. Unrecoverable without backups.
- Recommended fix: Remove the seed line from `entrypoint.sh`. Guard with `SEED_DB=true` env var if needed for dev.

**2. Hardcoded default secrets in `.env.example` used as compose fallbacks**
- File(s): `.env.example:29-35`, `docker-compose.yml` (all `${VAR:-default}` patterns)
- Problem: `LANGFUSE_NEXTAUTH_SECRET=supersecret`, `LANGFUSE_ENCRYPTION_KEY=b7321df1...`, `LANGFUSE_INIT_USER_PASSWORD=admin1234`, `CLICKHOUSE_PASSWORD=clickhousepassword` are shipped as defaults. The compose file uses `:-` fallback syntax, silently using these values if no env var is set.
- Why it matters: Any deployment that forgets to override these runs with publicly known secrets. Attacker can forge Langfuse sessions, access ClickHouse.
- Recommended fix: Replace `.env.example` values with `CHANGE_ME` placeholders. Remove `:-fallback` for security-sensitive vars so compose fails fast.

**3. Langfuse `NEXTAUTH_URL` hardcoded to localhost**
- File(s): `docker-compose.yml:159,207`
- Problem: `NEXTAUTH_URL: http://localhost:3000` is hardcoded for `langfuse-web` and `langfuse-worker`. Non-local deployments break OAuth/SSO flows.
- Why it matters: Langfuse observability stack is unusable outside localhost.
- Recommended fix: Parameterize as `${LANGFUSE_URL:-http://localhost:3000}`.

**4. Frontend `NEXT_PUBLIC_API_URL` baked at build time as localhost**
- File(s): `docker-compose.yml:131`, `frontend/Dockerfile`
- Problem: `NEXT_PUBLIC_API_URL=http://localhost:8000` is baked into the JS bundle at build time. The Dockerfile has no `ARG` to override it. Non-local deployments cannot reach the backend.
- Why it matters: Frontend is non-functional in any non-local environment.
- Recommended fix: Add `ARG NEXT_PUBLIC_API_URL` to the Dockerfile builder stage. Pass via `--build-arg` or compose `build.args`.

---

### [Severity: High]

**5. SSE parser drops events and loses data**
- File(s): `frontend/lib/api.ts:82-104`
- Problem: Line-by-line SSE parsing doesn't handle multi-line `data:` fields, blank-line event delimiters, or buffer remnants on stream end. Final event discarded if stream ends without trailing `\n`.
- Why it matters: Messages lost mid-stream; incomplete reports shown to users.
- Recommended fix: Replace with proper SSE event-block parser (split on `\n\n`) or use `eventsource-parser` library.

**6. Non-null assertion `response.report!` crashes on null**
- File(s): `frontend/hooks/use-chat.ts:91`
- Problem: `response.report!` on `complete` event. If backend sends `complete` with null report (protocol mismatch, error path), this crashes.
- Why it matters: Runtime crash, blank screen (no error boundary).
- Recommended fix: Add guard: `if (!response.report) return;` before constructing `ReportMessage`.

**7. `useChat.sendMessage` double-submission race condition**
- File(s): `frontend/hooks/use-chat.ts:34-145`
- Problem: `isLoading` in `useCallback` deps + React batched state updates allows two concurrent SSE streams if `sendMessage` called twice rapidly.
- Why it matters: Two streaming placeholders, corrupted message state.
- Recommended fix: Use a `useRef` guard set synchronously before the first `await`.

**8. HITL polling can overlap; no request cancellation**
- File(s): `frontend/components/chat/hitl-action-card.tsx:157-188`
- Problem: `setInterval(poll, 4000)` with serial `getAction` calls inside `poll`. If a poll takes >4s, two polls run concurrently. No `AbortController` on cleanup.
- Why it matters: Memory leaks, redundant API calls, stale state.
- Recommended fix: Add in-flight guard ref, use `Promise.all` for parallel fetches, add `AbortController`.

**9. No `AbortController` / request cancellation anywhere**
- File(s): `frontend/lib/api.ts` (all fetch calls), `frontend/hooks/use-chat.ts`
- Problem: No `AbortSignal` on any fetch. `postQueryStream` doesn't cancel on component unmount. ReadableStream reader leaks.
- Why it matters: Memory leaks on navigation during streaming; state updates on unmounted components.
- Recommended fix: Thread `AbortController` through all API calls. Abort in `useEffect` cleanup.

**10. No React Error Boundary**
- File(s): `frontend/app/layout.tsx`
- Problem: No `error.tsx` in Next.js app directory. No client-side ErrorBoundary. Any runtime throw shows blank white screen.
- Why it matters: Single thrown error kills the entire UI with no recovery.
- Recommended fix: Add `app/error.tsx` (Next.js built-in) and wrap `ChatInterface` in a client ErrorBoundary.

**11. Error handling silently swallowed in actions/incidents pages**
- File(s): `frontend/app/actions/page.tsx:172-192`, `frontend/app/incidents/page.tsx:43-55`
- Problem: `handleAction` catches all errors silently (no user feedback for non-409). `handleResolve` has no catch block at all.
- Why it matters: Users get no indication operations failed; may retry repeatedly.
- Recommended fix: Add error state, show toast/inline error for failures.

**12. Misleading enum re-exports — brittle import chain**
- File(s): `backend/core/enums.py:3-5`, `backend/db/models.py:24`, `backend/db/pg_store.py:13`, `backend/agents/rules.py:17`, `backend/scripts/seed_data.py:22`
- Problem: `core/enums.py` docstring claims to re-export `CampaignStatus`, `Channel`, `Severity` from `domains.common` — but it doesn't. Five files import these from `core.enums` and rely on a transitive import via the `mcp_operations` editable install.
- Why it matters: Any deployment without `mcp_servers/` fails all imports at module load time.
- Recommended fix: Explicitly re-export: `from domains.common import CampaignStatus, Channel, Severity` in `core/enums.py`.

**13. Global LLM singleton shared across concurrent requests**
- File(s): `backend/agents/factory.py:115-123`
- Problem: `@lru_cache(maxsize=1)` on `_get_llm()` creates a process-global singleton. `AzureChatOpenAI` holds an internal `httpx.AsyncClient`. Concurrent graph runs share the same client, risking connection pool contention.
- Why it matters: Subtle coroutine-safety issues under load; test isolation leaks.
- Recommended fix: Construct LLM per-Agent or use thread-safe factory pattern.

**14. Agent cache holds stale MCP tool references**
- File(s): `backend/agents/nodes.py:29-31`
- Problem: `@cache` on `_get_agent` caches agents permanently. If MCP registry reconnects, cached agents still hold old tool objects.
- Why it matters: After MCP recovery, agents invoke dead tool references.
- Recommended fix: Clear agent cache when MCP registry reinitializes, or use factory-per-call.

**15. `type: ignore` hides None/datetime confusion in rejection path**
- File(s): `backend/db/pg_store.py:257`
- Problem: `now = None  # type: ignore[assignment]` on rejection path. `now` typed as `datetime` but set to `None`.
- Why it matters: Future code reading `now` as datetime will crash.
- Recommended fix: Use separate `executed_at: datetime | None` variable.

**16. Invalid UUID in campaign targets raises misleading 409**
- File(s): `backend/db/pg_store.py:296,308`
- Problem: `uuid.UUID(campaign_id)` on unvalidated targets. Mock data uses `"camp-1"` (not a UUID). `ValueError` propagates as 409 Conflict.
- Why it matters: Action approval silently fails with wrong error code.
- Recommended fix: Wrap in try/except, log warning, continue to next target.

**17. CORS origins hardcoded — no production config**
- File(s): `backend/main.py:98-104`
- Problem: Origins hardcoded to `localhost:3001` and `localhost:3000`. No env var override. Production frontend blocked by CORS.
- Why it matters: API unusable from any non-localhost frontend.
- Recommended fix: Add `CORS_ORIGINS` to Settings, parse from env var.

**18. Hardcoded `TODAY = date(2026, 4, 9)` makes seed data stale**
- File(s): `backend/scripts/seed_data.py:26`
- Problem: All date constants are hardcoded. Running seed later produces data so far in the past that "yesterday" queries return nothing.
- Why it matters: Dev/test environment silently breaks over time.
- Recommended fix: Use `date.today()` dynamically.

**19. Inventory repository off-by-one: end date exclusive**
- File(s): `mcp_servers/domains/inventory/repository.py:55`
- Problem: `date < end` (exclusive) vs sales repo's `date <= end` (inclusive). Inventory excludes the target date's sales from velocity calculations.
- Why it matters: Wrong lost-revenue and velocity metrics.
- Recommended fix: Change to `<= end`.

**20. `order_count` counts rows, not unique orders**
- File(s): `mcp_servers/domains/sales/tools.py:38,167-196`
- Problem: `order_count = len(rows)` counts per-product/region rows, not unique orders. Anomaly detection compares row counts across periods.
- Why it matters: Metrics are misleading; anomaly thresholds may fire incorrectly.
- Recommended fix: Document clearly or aggregate by real order ID.

---

### [Severity: Medium]

**21. `incident_id` not stored in state before `interrupt()`**
- File(s): `backend/agents/nodes.py:253-254`
- Problem: After `interrupt()`, the `return {"incident_id": incident_id}` is unreachable on first pass. `final_response_node` may create a duplicate incident.
- Recommended fix: Set `incident_id` in state before calling `interrupt()`.

**22. Duplicate tool-calling code branches in Agent.run()**
- File(s): `backend/agents/factory.py:191-228`
- Problem: Near-identical code for tools-with-structured-output and tools-without. ~12 lines duplicated.
- Recommended fix: Refactor into single tool loop, conditional structured-output pass.

**23. Thread upsert race condition (SELECT then INSERT)**
- File(s): `backend/db/pg_store.py:493-502`
- Problem: Non-atomic check-then-insert. Concurrent requests with same thread_id cause PK conflict, silently swallowed.
- Recommended fix: Use PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`.

**24. Thread persistence skipped on client disconnect**
- File(s): `backend/api/routers/query.py:260-267`
- Problem: `persist_thread_messages` called after terminal SSE event. Client disconnect cancels the generator before persistence.
- Recommended fix: Persist in `try/finally` block.

**25. Qdrant vector store singleton not thread-safe; blocking embeddings**
- File(s): `backend/db/qdrant_store.py:19-28`
- Problem: Non-atomic singleton init. `FastEmbedEmbeddings` does synchronous CPU work on the event loop.
- Recommended fix: Use `asyncio.Lock()` for init. Offload embedding to thread pool.

**26. `SentenceTransformer` model loaded synchronously in async context**
- File(s): `mcp_servers/domains/memory/tools.py:26-27,47`
- Problem: First-call model load (~130MB download) and every `model.encode()` blocks the event loop.
- Recommended fix: Pre-load at startup. Use `run_in_executor` for encode calls.

**27. Bare `except Exception` swallows all memory search errors**
- File(s): `mcp_servers/domains/memory/tools.py:80-82`
- Problem: Model download failures, encoding errors, Qdrant schema mismatches all silently return empty results.
- Recommended fix: Only catch connectivity exceptions. Let unexpected errors propagate.

**28. No input validation on date parameters in MCP tools**
- File(s): All `mcp_servers/domains/*/tools.py`
- Problem: `date.fromisoformat(d)` with no try/except. LLM passing `"April 8th"` raises raw ValueError.
- Recommended fix: Wrap in try/except with descriptive error message.

**29. `channel_roas` keyed by raw string but accessed by enum value**
- File(s): `mcp_servers/domains/marketing/tools.py:63,83-86`
- Problem: Dict keys are raw DB strings, lookup uses `Channel.value`. Mismatch on unknown channels.
- Recommended fix: Normalize keys to enum values when building the dict.

**30. `days_back=0` produces meaningless comparison**
- File(s): `mcp_servers/domains/sales/tools.py:121`
- Problem: `days_back=0` sets `days_count=1` but creates a backwards date range where `prior_start > prior_end`.
- Recommended fix: Validate `days_back >= 1`, raise ValueError.

**31. `date.today()` ignores server timezone**
- File(s): `mcp_servers/domains/inventory/tools.py:21`, `mcp_servers/domains/marketing/tools.py:27`
- Problem: `date.today()` returns server local date. In UTC containers, this can be off by one business day.
- Recommended fix: Use `datetime.now(UTC).date()`.

**32. Every tool call creates new repository; N connections per tool invocation**
- File(s): All `mcp_servers/domains/*/tools.py` and `*/repository.py`
- Problem: Each repository method acquires/releases its own session. 3-4 connections per tool call.
- Recommended fix: Pass a shared session into repository methods.

**33. `_parse_date` duplicated in all 4 domain tools**
- File(s): `sales/tools.py:17`, `inventory/tools.py:11`, `marketing/tools.py:17`, `customer_support/tools.py:10`
- Recommended fix: Move to `domains/common.py`.

**34. `products`/`sales` tables re-declared in each repository**
- File(s): All 4 `*/repository.py` files
- Problem: Each creates its own `MetaData()` and re-declares identical table objects.
- Recommended fix: Single `db_tables.py` with shared table definitions.

**35. `rebuildMessages` generates new random IDs each call**
- File(s): `frontend/components/chat/chat-interface.tsx:28-75`
- Problem: `newId()` for historical messages. React remounts all components, destroying HITL polling state.
- Recommended fix: Use `item.id` from thread history.

**36. Tests only test mock, not actual hook**
- File(s): `frontend/__tests__/hooks/use-chat.test.ts`
- Problem: Tests call `mockApproveAction` directly, never render `useChat`. Zero coverage of actual hook logic.
- Recommended fix: Use `renderHook` from `@testing-library/react`.

**37. `theme` undefined on first render causes wrong toggle direction**
- File(s): `frontend/components/theme-toggle.tsx:7-8`
- Recommended fix: Use `resolvedTheme` from `useTheme()` instead of `theme`.

**38. Actions page polling continues when tab is hidden**
- File(s): `frontend/app/actions/page.tsx:157-170`
- Recommended fix: Add `visibilitychange` listener to pause polling.

**39. No tests for memory/Qdrant domain in MCP server**
- File(s): `mcp_servers/tests/` (no `test_memory.py`)
- Recommended fix: Add test file with mocked Qdrant client.

**40. MCP client HTTP transport not properly closed on shutdown**
- File(s): `backend/agents/mcp_registry.py:132-136`
- Problem: `self._client = None` drops reference without calling `aclose()`. Leaks connections.
- Recommended fix: Call `await self._client.aclose()` before nulling.

**41. Docker images using `latest` tag**
- File(s): `docker-compose.yml:29`
- Problem: `qdrant/qdrant:latest` and `clickhouse/clickhouse-server:latest` are mutable.
- Recommended fix: Pin to specific versions.

---

### [Severity: Low]

**42.** `retry_count` incremented past `MAX_RETRIES` in early-exit path (`backend/agents/nodes.py:180-192`)
**43.** Operator precedence unclear in incident-save condition (`backend/agents/nodes.py:335`)
**44.** Post-commit query with potentially stale objects (`backend/db/pg_store.py:466-468`)
**45.** `resolution_summary` buried in JSONB instead of dedicated column (`backend/db/pg_store.py:379`)
**46.** Empty query string accepted without validation (`backend/schemas/query.py:6`)
**47.** `onupdate` rendered redundant by manual `updated_at` sets (`backend/db/models.py:72-77`)
**48.** `asyncio.run()` inside pytest-asyncio session fixtures (`backend/tests/conftest.py:33-49`)
**49.** Missing initial state keys in test graph invocation (`backend/tests/test_graph.py:25-39`)
**50.** `threads`/`thread_messages` not cleared on re-seed (`backend/scripts/seed_data.py:287-293`)
**51.** Reflector YAML `issues` format contradicts Pydantic schema (`backend/agents/configs/reflector.yml:61-69`)
**52.** Cleanup not in `finally` block in lifespan (`backend/main.py:67-88`)
**53.** Root logger handlers replaced destructively (`backend/core/logging.py:24`)
**54.** `conversation_history` slicing assumes strict alternating pattern (`backend/agents/nodes.py:261-266`)
**55.** `_query_tokens` filter removes short product IDs (`backend/agents/rules.py:37`)
**56.** API datetime fields typed as raw strings (`backend/api/schemas.py:43-44`)
**57.** `SalesAnalysis.anomalies` field is never populated (dead field) (`mcp_servers/domains/sales/schemas.py:33`)
**58.** `.env` parser in conftest doesn't strip quotes (`mcp_servers/conftest.py:21`)
**59.** Unknown channel/status silently mapped to defaults (`mcp_servers/domains/marketing/tools.py:44-52`)
**60.** Lazy globals with no shutdown hook in MCP server (`mcp_servers/db.py:6-7`)
**61.** `TimeRange.end` is `23:59:59` not true end-of-day (`mcp_servers/domains/sales/tools.py:26`)
**62.** `postQuery` (non-streaming) is dead code (`frontend/lib/api.ts:113-127`)
**63.** "Approved" label shown for rejected actions with `executed_at` (`frontend/app/actions/page.tsx:123-131`)
**64.** `primary_cause: string | string[]` overly broad union (`frontend/lib/types.ts:173`)
**65.** Array index as React key for recommendations (`frontend/components/chat/report-card.tsx:52`)
**66.** `Clock` icon used as spinner instead of `Loader2` (multiple files)
**67.** Relative timestamps in sidebar never refresh (`frontend/components/chat/sidebar.tsx:14-24`)
**68.** `ThreadMessageItem.content` typed as `Record<string, unknown>` with unsafe casts (`frontend/lib/types.ts:347`)
**69.** Duplicate header/tab navigation UI with no shared component (`frontend/app/actions/page.tsx`, `incidents/page.tsx`)
**70.** No `.dockerignore` for MCP server — `.venv` included in image (`mcp_servers/Dockerfile`)
**71.** No frontend linting in pre-commit hooks (`.pre-commit-config.yaml`)
**72.** `project_requirements.md` gitignored (`.gitignore:1-2`)
**73.** Bun-specific package.json fields undocumented (`frontend/package.json:37-43`)
**74.** `disableTransitionOnChange={false}` is redundant default (`frontend/app/layout.tsx:39`)
**75.** Thread fetch errors silently ignored in sidebar (`frontend/hooks/use-threads.ts:16-18`)
**76.** Weak test assertions in MCP server tests (`mcp_servers/tests/test_sales.py:55-57`, `test_inventory.py:30-32`)
**77.** `React.ComponentProps` used without importing React (`frontend/components/ui/skeleton.tsx:3`)

---

## Refactor Opportunities

### Code Reduction
| Area | Current | After | Savings |
|---|---|---|---|
| `_parse_date` duplication | 4 copies across MCP tools | 1 in `common.py` | ~12 lines |
| Table declarations in repositories | 4 independent `MetaData()` + table defs | 1 shared `db_tables.py` | ~60 lines |
| Agent `run()` duplicate branches | 2 near-identical tool-calling paths | 1 unified path + conditional | ~15 lines |
| Header/Tab UI in pages | 2 copy-paste blocks | Shared `<PageHeader>` + `<FilterTabs>` | ~60 lines |

### Reusable Abstractions
- **Shared session pattern** for MCP repositories — pass session into repository instead of acquiring per-method
- **`ApiClient` class** in frontend with built-in `AbortController`, retry, and error handling
- **`usePolling` hook** — extract polling logic from `hitl-action-card.tsx` and `actions/page.tsx`

### Libraries Worth Adopting
- **`eventsource-parser`** (npm) — replace hand-rolled SSE parser
- **`zod`** — runtime validation for `ThreadMessageItem.content` instead of unsafe casts
- **`react-error-boundary`** — standardized error boundary with retry

---

## Dead Code / Cleanup List

| Item | Location | Action |
|---|---|---|
| `postQuery` function | `frontend/lib/api.ts:113-127` | Remove (unused non-streaming fallback) |
| `SalesAnalysis.anomalies` field | `mcp_servers/domains/sales/schemas.py:33` | Remove (never populated) |
| `disableTransitionOnChange={false}` | `frontend/app/layout.tsx:39` | Remove (default value) |
| `threadId` in `useChat` return | `frontend/hooks/use-chat.ts:210` | Remove (duplicate of `activeThreadId`) |
| `stockout_missed_views` | `mcp_servers/domains/inventory/schemas.py:34` | Rename to `stockout_impacted_products` |
| Backend `README.md` | `backend/README.md` | Either populate or remove (empty file) |
| `tool_registry.py` comment | `mcp_servers/domains/tool_registry.py:35` | Fix (says `list[Anomaly]`, actual is `list[dict]`) |
| `core/enums.py` docstring | `backend/core/enums.py:3-5` | Fix or make real re-exports |

---

## Quick Wins (Do First)

These can each be done in under 30 minutes and have the highest impact:

1. **Remove seed from `entrypoint.sh`** or guard with `SEED_DB=true` — prevents data destruction
2. **Add `app/error.tsx`** — prevents blank screen on any runtime error
3. **Add guard before `response.report!`** in `use-chat.ts:91` — prevents crash
4. **Replace `Clock` with `Loader2`** in 3 files — fix broken spinner animation
5. **Use `resolvedTheme`** in theme toggle — fix first-render toggle direction
6. **Add `min_length=1`** to Query schema — prevent empty queries
7. **Fix inventory repository `< end`** to `<= end` — fix off-by-one
8. **Replace `.env.example` secrets** with `CHANGE_ME` placeholders
9. **Add `useRef` guard** in `sendMessage` — prevent double-submission
10. **Add `CORS_ORIGINS`** to backend Settings — enable production deployment

---

## Strategic Improvements (Do Next)

These require more planning but significantly improve the codebase:

1. **Replace SSE parser** — adopt `eventsource-parser` or rewrite with proper event-block parsing. Add reconnection with `Last-Event-ID`.
2. **Add AbortController throughout** — thread signals through all API calls, clean up in `useEffect` returns.
3. **Shared repository session pattern** — pass session into MCP repository methods to reduce connection churn from N to 1 per tool call.
4. **Centralize MCP table declarations** — single `db_tables.py` replacing 4 independent `MetaData()` instances.
5. **Extract shared frontend components** — `<PageHeader>`, `<FilterTabs>`, `usePolling` hook.
6. **Add runtime validation** — `zod` for `ThreadMessageItem.content` parsing instead of unsafe casts.
7. **Proper test coverage** — replace mock-only frontend tests with `renderHook`, add memory domain tests, add isolated unit tests for MCP tool business logic.
8. **CI/CD pipeline** — add GitHub Actions or equivalent for lint, type-check, test on both backend and frontend.
9. **Docker hardening** — pin image versions, add `.dockerignore` files, parameterize all URLs and secrets.
10. **Cache invalidation** — tie `_get_agent` and `_get_llm` caches to MCP registry lifecycle.

---

## Final Verdict

**The codebase is competent but fragile.** The architecture (LangGraph multi-agent, MCP tools, HITL, SSE streaming) is ambitious and well-designed at the conceptual level. The code is generally clean, well-organized, and follows reasonable patterns.

However, it has the hallmarks of a project that was built quickly with the "happy path" tested but edge cases and production concerns deferred:

- **Critical production risks** — the seed script alone would destroy all data on first deploy. The hardcoded secrets and localhost URLs mean the first production deployment will fail in multiple ways.
- **Frontend reliability** — no error boundaries, broken SSE parser, race conditions in the primary hook, no request cancellation. The chat interface will work well in demos but fail under real-world conditions (slow networks, tab switching, rapid interactions).
- **Backend resilience** — global singletons with no invalidation, non-atomic DB operations, blocking sync code on the event loop. Works under light load but will show problems at scale.
- **Testing is thin** — tests exist but many test mocks rather than real logic. Coverage appears sufficient only because integration tests hit the happy path.

The codebase is **not production-ready** but is a solid foundation. With the quick wins above (2-3 hours of work), the critical risks can be eliminated. The strategic improvements (1-2 weeks) would bring it to production quality.

---

## Prioritized Fix Roadmap

### Phase 1: Stop the Bleeding (Day 1)
- [ ] Guard seed script with env var
- [ ] Replace hardcoded secrets in `.env.example`
- [ ] Add `app/error.tsx`
- [ ] Fix `response.report!` null guard
- [ ] Fix inventory off-by-one
- [ ] Fix CORS to use env vars

### Phase 2: Stabilize (Week 1)
- [ ] Replace SSE parser
- [ ] Add AbortController to all API calls
- [ ] Fix `sendMessage` double-submission
- [ ] Fix thread upsert to use ON CONFLICT
- [ ] Fix `rebuildMessages` to use stable IDs
- [ ] Add `try/finally` for thread persistence
- [ ] Fix MCP client cleanup on shutdown
- [ ] Fix all silent error swallowing (actions page, incidents page, memory tool)

### Phase 3: Harden (Week 2)
- [ ] Shared repository session pattern
- [ ] Centralize table declarations
- [ ] Add input validation to all MCP tools
- [ ] Pin Docker image versions
- [ ] Add `.dockerignore` files
- [ ] Parameterize all URLs in docker-compose
- [ ] Pre-load SentenceTransformer at startup
- [ ] Move embedding to thread pool

### Phase 4: Polish (Week 3+)
- [ ] Rewrite frontend tests with `renderHook`
- [ ] Add memory domain tests
- [ ] Extract shared UI components
- [ ] Add CI/CD pipeline
- [ ] Add frontend pre-commit hooks
- [ ] Runtime validation with zod
- [ ] Cache invalidation for agents/LLM

---

## Files Needing Immediate Review

1. `backend/entrypoint.sh` — data destruction
2. `.env.example` — hardcoded secrets
3. `docker-compose.yml` — hardcoded URLs, unpinned images, secret fallbacks
4. `frontend/lib/api.ts` — broken SSE parser
5. `frontend/hooks/use-chat.ts` — race conditions, null dereference
6. `frontend/components/chat/hitl-action-card.tsx` — polling issues
7. `backend/db/pg_store.py` — type ignore, UUID validation, thread race
8. `mcp_servers/domains/inventory/repository.py` — off-by-one
9. `mcp_servers/domains/memory/tools.py` — exception swallowing, blocking I/O
10. `backend/agents/nodes.py` — stale cache, unreachable code after interrupt

---

## Suspicious Code Patterns

| Pattern | Location | Assessment |
|---|---|---|
| `# type: ignore[assignment]` setting `now = None` | `backend/db/pg_store.py:257` | Looks like a quick fix to satisfy type checker |
| `strict=False` on message history zip | `backend/agents/nodes.py:262` | Suppresses a real alignment check |
| Mock-only tests that test the mock | `frontend/__tests__/hooks/use-chat.test.ts` | Appears AI-generated — tests the mock return values, not actual logic |
| `eslint-disable` without explanation | `frontend/components/chat/hitl-action-card.tsx:188` | Linting bypass without justification |
| Copy-paste header UI across pages | `actions/page.tsx`, `incidents/page.tsx` | Classic copy-paste-modify pattern |
| Silent `Channel.DISPLAY` fallback | `mcp_servers/domains/marketing/tools.py:44-47` | Cargo-culted error handling that hides data problems |
| `postQuery` dead function kept "as fallback" | `frontend/lib/api.ts:113-127` | Leftover from development iteration |
