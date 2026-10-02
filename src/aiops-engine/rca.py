"""
Root Cause Analysis (RCA) Engine
=================================

Pulls real metrics from Prometheus for a given service and evaluates a set
of threshold rules against them. Multiple simultaneous root causes are
supported (e.g. a service can be both HIGH_CPU and HIGH_LATENCY at once) --
the caller (main.py / decision engine) decides how to prioritize.

Metric queries are written against generic cAdvisor / node-exporter style
metric names so this works against a standard Prometheus + cAdvisor setup.
If a given metric series isn't being scraped in a particular environment,
`fetch_scalar` simply returns None and that rule is skipped rather than
raising -- RCA degrades gracefully instead of crashing the loop.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import requests

from shared.logger import setup_logger

logger = setup_logger("aiops-engine.rca")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


@dataclass(frozen=True)
class Thresholds:
    cpu_percent: float = float(os.getenv("RCA_CPU_THRESHOLD", "90"))
    memory_percent: float = float(os.getenv("RCA_MEMORY_THRESHOLD", "95"))
    disk_percent: float = float(os.getenv("RCA_DISK_THRESHOLD", "90"))
    latency_ms: float = float(os.getenv("RCA_LATENCY_THRESHOLD_MS", "3000"))
    error_rate_percent: float = float(os.getenv("RCA_ERROR_RATE_THRESHOLD", "15"))
    container_restarts: float = float(os.getenv("RCA_RESTART_THRESHOLD", "3"))
    queue_length: float = float(os.getenv("RCA_QUEUE_THRESHOLD", "100"))


THRESHOLDS = Thresholds()

# PromQL templates, parameterised by container/service name.
QUERIES = {
    "cpu_percent": 'sum(rate(container_cpu_usage_seconds_total{{name="{svc}"}}[2m])) * 100',
    "memory_percent": (
        '(container_memory_usage_bytes{{name="{svc}"}} '
        '/ container_spec_memory_limit_bytes{{name="{svc}"}}) * 100'
    ),
    "disk_percent": (
        '(node_filesystem_size_bytes - node_filesystem_avail_bytes) '
        '/ node_filesystem_size_bytes * 100'
    ),
    "network_bytes": 'sum(rate(container_network_transmit_bytes_total{{name="{svc}"}}[2m]))',
    "latency_ms": (
        'rate(inference_latency_seconds_sum[2m]) '
        '/ rate(inference_latency_seconds_count[2m]) * 1000'
    ),
    "error_rate_percent": 'rate(inference_errors_total[2m]) * 100',
    "http_requests_per_sec": 'sum(rate(http_requests_total{{service="{svc}"}}[2m]))',
    "container_restarts": 'kube_pod_container_status_restarts_total{{container="{svc}"}}',
    "queue_length": "queue_depth",
}


def fetch_scalar(promql: str) -> Optional[float]:
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql}, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return None
        result = data["data"]["result"]
        if not result:
            return None
        return float(result[0]["value"][1])
    except Exception as e:
        logger.debug(f"RCA metric fetch failed for query '{promql}': {e}")
        return None


def collect_service_metrics(service_name: str) -> dict:
    """Collect the full metric set for a service. Missing series come back as None."""
    metrics = {}
    for key, template in QUERIES.items():
        try:
            query = template.format(svc=service_name)
        except (KeyError, IndexError):
            query = template
        metrics[key] = fetch_scalar(query)
    return metrics


def analyze(metrics: dict) -> list[str]:
    """Evaluate threshold rules against collected metrics. Returns every
    root cause whose condition is met -- can be more than one."""
    causes = []

    def over(value, threshold):
        return value is not None and value > threshold

    if over(metrics.get("cpu_percent"), THRESHOLDS.cpu_percent):
        causes.append("HIGH_CPU")
    if over(metrics.get("memory_percent"), THRESHOLDS.memory_percent):
        causes.append("HIGH_MEMORY")
    if over(metrics.get("disk_percent"), THRESHOLDS.disk_percent):
        causes.append("DISK_FULL")
    if over(metrics.get("latency_ms"), THRESHOLDS.latency_ms):
        causes.append("HIGH_LATENCY")
    if over(metrics.get("error_rate_percent"), THRESHOLDS.error_rate_percent):
        causes.append("HIGH_ERRORS")
    if over(metrics.get("container_restarts"), THRESHOLDS.container_restarts):
        causes.append("CRASH_LOOP")
    if over(metrics.get("queue_length"), THRESHOLDS.queue_length):
        causes.append("QUEUE_BACKLOG")

    if not causes:
        return []
    return causes
