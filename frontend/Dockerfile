# ---- Stage 1: Dependencies ----
# Using a specific alpine version for better reproducibility
FROM node:20.12-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Only copy lockfiles to leverage Docker layer caching
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# ---- Stage 2: Build ----
FROM node:20.12-alpine AS builder
WORKDIR /app

# Bring over dependencies from the deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Set production build-time variables
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
# Note: Public API URL is baked in at build time in Next.js
ENV NEXT_PUBLIC_API_URL=http://api:8000

RUN npm run build

# ---- Stage 3: Production Runner ----
FROM node:20.12-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Security: Production hardening with a non-root user[cite: 7]
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Optimization: Only copy the essential standalone build artifacts[cite: 8]
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# Next.js standalone mode generates a server.js file[cite: 8]
CMD ["node", "server.js"]