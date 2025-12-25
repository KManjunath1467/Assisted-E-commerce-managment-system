# ── Stage 1: dependency resolver ────────────────────────────────────────
FROM python:3.13-slim AS deps
RUN pip install --no-cache-dir uv
WORKDIR /app

# Copy both pyproject.toml + lock files so uv can resolve the path dependency
COPY backend/pyproject.toml backend/uv.lock ./backend/
COPY mcp_servers/pyproject.toml ./mcp_servers/
COPY mcp_servers/domains/ ./mcp_servers/domains/

WORKDIR /app/backend
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ───────────────────────────────────────────────────
FROM python:3.13-slim AS runtime
WORKDIR /app/backend
COPY --from=deps /app/backend/.venv ./.venv
COPY --from=deps /app/mcp_servers /app/mcp_servers
COPY backend/ .
ENV PATH="/app/backend/.venv/bin:$PATH"
RUN chmod +x entrypoint.sh

EXPOSE 8000
CMD ["./entrypoint.sh"]
