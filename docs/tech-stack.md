# Tech Stack

Every entry below is something actually imported/used in this repo right
now — not an aspirational list.

## Backend
- **Python 3.11**, **FastAPI** + **uvicorn** — every service
- **SQLAlchemy 2.0** + **psycopg2** — ORM/driver for PostgreSQL
  (`incident-service`, `result-service`, `notification-service`, `auth-service`)
- **Pydantic v2** — request/response schemas
- **PyJWT** — internal service-to-service JWT (`shared/auth.py`)
- Firebase ID token verification **without the Admin SDK** — hand-rolled
  against Google's public certs (`shared/firebase_auth.py`), specifically
  so the gateway needs no service-account JSON, just a public project ID
- **httpx** — async reverse-proxying in `api-gateway`
- **websockets** — the gateway's WebSocket relay to `incident-service`
- **docker** (Docker SDK for Python) — `remediation-service`'s Docker executor
- **kubernetes** (official Python client) — `remediation-service`'s K8s
  executor, `load_incluster_config()` / `load_kube_config()` with mock-mode
  fallback
- **scikit-learn**, **pandas** — `aiops-engine`'s anomaly detection
- **prometheus-fastapi-instrumentator** — every service exposes `/metrics`
  for Prometheus scraping

## Frontend
- **React 18** + **Vite**
- **Firebase Auth (JS SDK)** — email/password login, ID tokens attached to
  every request via an axios interceptor
- **axios**
- **chart.js** + **react-chartjs-2** — metrics history charts
- Native **WebSocket** — live incident feed (Firebase token passed as
  `?token=` query param, since browsers can't set custom headers on a
  WebSocket handshake)
- Plain CSS with a token-based design system (`index.css` — CSS custom
  properties for color/spacing, no CSS framework)

## Data & messaging
- **PostgreSQL 15** — incidents, actions, metric snapshots, audit logs,
  notifications, legacy inference results
- **Redis 7** — inference-service's queue/cache layer

## Observability
- **Prometheus** — metrics store, scrapes every service + cAdvisor + node-exporter
- **cAdvisor** — real per-container CPU/memory/network metrics (this is
  what `rca.py`'s threshold detector actually reads, not synthetic data)
- **node-exporter** — real host disk/filesystem metrics
- **Grafana** — dashboards (provisioned via `observability/grafana/provisioning`)
- **Loki** + **Promtail** — log aggregation

## Containerization & orchestration
- **Docker** + **Docker Compose** (two compose files: dev and hardened/prod)
- **Kubernetes** via **Kustomize** (`infra/kubernetes/base` +
  `region-a`/`region-b` overlays) — no Helm, deliberately: nine services and
  two stateful dependencies don't need a templating engine on top of
  Kustomize's patch model
- **nginx** — the production edge/reverse-proxy (`infra/nginx/`)

## Infrastructure as code
- **Terraform** (`infra/terraform`) — optional cloud provisioning layer,
  not required to run anything above

## Auth
- **Firebase Authentication** — the only user-facing auth path (email/password)
- Internal JWT (`shared/auth.py`, HS256) — service-to-service trust after
  the gateway translates a verified Firebase token
- `X-Internal-Api-Key` header — alternative internal-only auth for
  service-to-service calls that don't go through a human's token at all
  (e.g. `aiops-engine` → `incident-service`)

## Why these choices, not others
- **Kustomize over Helm**: this is a 9-service testbed, not a chart meant
  for third-party reuse — Helm's templating overhead isn't earning its
  keep here.
- **Hand-rolled Firebase verification over firebase-admin**: avoids needing
  a service-account JSON secret just to verify tokens; verification-only
  needs nothing more than the public signing certs.
- **No message queue (Kafka/RabbitMQ)**: service-to-service calls are
  synchronous HTTP + a Postgres-backed event table
  (`incident_events`) for the timeline — genuinely not enough throughput
  here yet to justify async messaging infrastructure.
