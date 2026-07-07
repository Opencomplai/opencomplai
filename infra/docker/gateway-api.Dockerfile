# syntax=docker/dockerfile:1
FROM node:20-alpine AS builder

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9 --activate

COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./

WORKDIR /app/services/gateway-api
COPY services/gateway-api/package.json ./

RUN pnpm install --frozen-lockfile

COPY services/gateway-api/tsconfig.json ./tsconfig.json
COPY services/gateway-api/src ./src

RUN pnpm build && CI=true pnpm prune --prod

# ---------------------------------------------------------------------------
FROM node:20-alpine AS runtime

WORKDIR /app/services/gateway-api

RUN apk add --no-cache curl && \
    addgroup -g 1001 -S opencomplai && \
    adduser -u 1001 -S opencomplai -G opencomplai

COPY --from=builder --chown=1001:1001 /app/services/gateway-api/dist ./dist
COPY --from=builder --chown=1001:1001 /app/services/gateway-api/node_modules ./node_modules
COPY --from=builder --chown=1001:1001 /app/node_modules /app/node_modules

USER 1001

EXPOSE 8080

CMD ["node", "dist/server.js"]
