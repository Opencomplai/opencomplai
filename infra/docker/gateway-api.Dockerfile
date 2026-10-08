# syntax=docker/dockerfile:1
# Base image is pinned by digest. To refresh it, run
# `docker buildx imagetools inspect node:24-alpine` and use the index digest in both FROM lines.
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS builder

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./

WORKDIR /app/services/gateway-api
COPY services/gateway-api/package.json ./

RUN pnpm install --frozen-lockfile

COPY services/gateway-api/tsconfig.json ./tsconfig.json
COPY services/gateway-api/src ./src

RUN pnpm build && CI=true pnpm prune --prod

# ---------------------------------------------------------------------------
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS runtime

WORKDIR /app/services/gateway-api

RUN apk upgrade --no-cache && \
    apk add --no-cache curl && \
    rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
           /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
           /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-* && \
    addgroup -g 1001 -S opencomplai && \
    adduser -u 1001 -S opencomplai -G opencomplai

COPY --from=builder --chown=1001:1001 /app/services/gateway-api/dist ./dist
COPY --from=builder --chown=1001:1001 /app/services/gateway-api/node_modules ./node_modules
COPY --from=builder --chown=1001:1001 /app/node_modules /app/node_modules

USER 1001

EXPOSE 8080

CMD ["node", "dist/server.js"]
