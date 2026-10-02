# Production edge: builds the React app for real (not `vite dev`) and
# serves it from nginx, which also reverse-proxies API/WebSocket calls to
# the gateway. This is the "single public entry point" from Phase 2 --
# used only by docker-compose.prod.yml, the dev docker-compose.yml is
# untouched and keeps using the existing frontend dev-server container.
FROM node:22-alpine AS build
WORKDIR /app
COPY src/frontend/package*.json ./
RUN npm install

# Baked in at build time since Vite inlines env vars into the bundle --
# point this at wherever this nginx container is actually reachable from
# (e.g. https://aiops.yourdomain.com/gateway).
ARG VITE_API_URL=/gateway
ENV VITE_API_URL=${VITE_API_URL}

COPY src/frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
