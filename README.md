# Sentinexis

An autonomous remediation platform: detects anomalies from real
infrastructure metrics, diagnoses a root cause, decides on a remediation
action, executes it against Docker or Kubernetes, verifies recovery, and
shows the whole lifecycle on a live dashboard.

```
Detect  ->  Diagnose (RCA)  ->  Decide  ->  Remediate  ->  Verify  ->  Resolve
```



## Documentation

| Doc | What's in it |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Component diagram, sequence diagram, data model, why the system is shaped this way |
| [`docs/tech-stack.md`](docs/tech-stack.md) | Every technology actually used, and why |


## Quickstart

```bash
docker compose up -d --build
```
Open http://localhost:3000, log in with Firebase, and watch the Chaos
Engineering panel trigger real self-healing. Full instructions,
including a from-scratch Kubernetes deployment, are in
[`docs/how-to-run.md`](docs/how-to-run.md).

## Services

api-gateway · auth-service · inference-service · result-service ·
incident-service · remediation-service · notification-service ·
aiops-engine · frontend — plus PostgreSQL, Redis, Prometheus, cAdvisor,
node-exporter, Grafana, Loki. Full breakdown in
[`docs/architecture.md`](docs/architecture.md).

## Status

Working autonomous remediation platform, real Docker + Kubernetes
execution, real Prometheus/cAdvisor-backed metrics. Not yet a completed
research instrument — see the gap doc above for exactly what's missing
before the research hypotheses can be tested.
