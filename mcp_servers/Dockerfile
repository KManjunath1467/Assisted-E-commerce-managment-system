# ── Stage 1: dependency resolver ────────────────────────────────────────
FROM python:3.13-slim AS deps
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ───────────────────────────────────────────────────
FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=deps /app/.venv ./.venv
COPY . .
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001
CMD ["python", "server.py"]
