# ── Stage 1: install dependencies ───────────────────────────────────────
FROM oven/bun:1 AS deps
WORKDIR /app
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

# ── Stage 2: build ─────────────────────────────────────────────────────
FROM oven/bun:1 AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN bun run next build

# ── Stage 3: runtime ───────────────────────────────────────────────────
FROM oven/bun:1-slim AS runtime
WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3001

EXPOSE 3001
CMD ["bun", "run", "server.js"]
