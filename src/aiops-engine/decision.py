"""
Decision Engine
================
An extensible rule table mapping a root cause (as produced by rca.py) to a
remediation action. "Extensible" means: adding a new cause->action mapping
is a one-line call to `register_rule`, no branching logic to touch.

Severity is derived alongside the action so the incident record can be
opened with an accurate severity rather than a hardcoded default.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    action: str
    severity: str
    target_type: str  # "docker" or "kubernetes"


_RULES: dict[str, Decision] = {}


def register_rule(cause: str, action: str, severity: str = "MEDIUM", target_type: str = "docker"):
    _RULES[cause] = Decision(action=action, severity=severity, target_type=target_type)


# Default rule set, per the platform spec.
# Default rule set, per the platform spec. HIGH_LATENCY/QUEUE_BACKLOG map
# to a Docker restart by default rather than a K8s scale -- the K8s executor
# hasn't been validated against a real cluster yet, and
# remediation-service refuses Kubernetes actions unless
# ENABLE_KUBERNETES_REMEDIATION=true (see remediation-service/config.py).
# Once that's been tested for real, flip these back to
# target_type="kubernetes" to get autoscaling behavior instead of a restart.
register_rule("HIGH_CPU", "restart_container", severity="HIGH", target_type="docker")
register_rule("HIGH_MEMORY", "restart_container", severity="HIGH", target_type="docker")
register_rule("HIGH_ERRORS", "restart_container", severity="HIGH", target_type="docker")
register_rule("CRASH_LOOP", "restart_container", severity="CRITICAL", target_type="docker")
register_rule("HIGH_LATENCY", "restart_container", severity="MEDIUM", target_type="docker")
register_rule("QUEUE_BACKLOG", "restart_container", severity="MEDIUM", target_type="docker")
register_rule("DISK_FULL", "alert_operator", severity="CRITICAL", target_type="docker")

_UNKNOWN = Decision(action="human_approval", severity="MEDIUM", target_type="docker")


# Priority order used when a single anomaly maps to multiple simultaneous
# causes -- pick the most severe/urgent action to act on this cycle. Any
# cause not listed here falls to the end (lowest priority).
_PRIORITY = [
    "CRASH_LOOP",
    "DISK_FULL",
    "HIGH_MEMORY",
    "HIGH_CPU",
    "HIGH_ERRORS",
    "HIGH_LATENCY",
    "QUEUE_BACKLOG",
]


def decide(causes: list[str]) -> tuple[str, Decision]:
    """Given one or more simultaneous root causes, pick the primary cause to
    act on and return (cause, decision). Unknown causes fall back to a
    human-approval decision rather than guessing."""
    if not causes:
        return "UNKNOWN", _UNKNOWN

    ranked = sorted(causes, key=lambda c: _PRIORITY.index(c) if c in _PRIORITY else len(_PRIORITY))
    primary = ranked[0]
    return primary, _RULES.get(primary, _UNKNOWN)
