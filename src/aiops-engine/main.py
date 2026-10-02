import os
import time
import requests
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime
from shared.logger import setup_logger

import decision
import rca

logger = setup_logger("aiops-engine")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/aiops")
INCIDENT_SERVICE_URL = os.getenv("INCIDENT_SERVICE_URL", "http://incident-service:8003")
REMEDIATION_SERVICE_URL = os.getenv("REMEDIATION_SERVICE_URL", "http://remediation-service:8004")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "change-this-internal-key")

# Services the RCA engine actively polls each cycle, independent of the
# existing ML-based latency detector below. Configurable so new services
# can be added to monitoring without a code change.
MONITORED_SERVICES = os.getenv(
    "MONITORED_SERVICES", "inference-service,result-service,api-gateway,auth-service"
).split(",")

COOLDOWN_SECONDS = 60
MAX_ESCALATION_LEVEL = 3
REMEDIATION_STATE = {}  # service_name -> {"last_time": 0, "level": 0}

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class IncidentLog(Base):
    """Kept for backward compatibility with anything already reading this
    table. The Incident Management Service (incident-service) is now the
    system of record for the full lifecycle; this remains a lightweight
    audit trail of "an anomaly fired and X was attempted"."""

    __tablename__ = "incident_logs"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String)
    anomaly_type = Column(String)
    action_taken = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"DB Init Error: {e}")


def fetch_metrics(query: str, duration: str = "1h") -> pd.DataFrame:
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        data = response.json()
        if data.get("status") == "success":
            results = data["data"]["result"]
            if not results:
                return pd.DataFrame()
            metrics = []
            for res in results:
                metric = res["metric"]
                val = res["value"]
                metrics.append({
                    "timestamp": val[0],
                    "value": float(val[1]),
                    **metric
                })
            return pd.DataFrame(metrics)
    except Exception as e:
        logger.error(f"Error fetching metrics from Prometheus: {e}")
    return pd.DataFrame()


def detect_anomalies(df: pd.DataFrame):
    if df.empty or "value" not in df.columns:
        return []
    if len(df) < 5:
        return []

    model = IsolationForest(contamination=0.1, random_state=42)
    df["anomaly"] = model.fit_predict(df[["value"]])
    anomalies = df[df["anomaly"] == -1]
    return anomalies.to_dict(orient="records")


# ---------------------------------------------------------------------------
# incident-service / remediation-service HTTP clients
# ---------------------------------------------------------------------------
_HEADERS = {"X-Internal-Api-Key": INTERNAL_API_KEY}


def open_incident(service_name: str, details: str, severity: str, root_cause: str, recommended_action: str,
                   metrics: dict = None, anomaly_score: float = None):
    payload = {
        "service_name": service_name,
        "severity": severity,
        "anomaly_score": anomaly_score,
        "metrics": metrics,
        "root_cause": root_cause,
        "recommended_action": recommended_action,
        "recovery_status": "DIAGNOSING",
        "source": "aiops-engine",
        "details": details,
    }
    try:
        resp = requests.post(f"{INCIDENT_SERVICE_URL}/incidents", json=payload, headers=_HEADERS, timeout=5)
        resp.raise_for_status()
        incident = resp.json()
        logger.info(f"Opened incident {incident.get('incident_uid')} for {service_name} (cause={root_cause})")
        return incident
    except Exception as e:
        logger.error(f"Failed to open incident via incident-service: {e}")
        return None


def update_incident_status(incident_id: int, status: str):
    try:
        resp = requests.patch(
            f"{INCIDENT_SERVICE_URL}/incidents/{incident_id}",
            json={"recovery_status": status},
            headers=_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to update incident {incident_id} status to {status}: {e}")


def request_remediation(incident_id: int, service_name: str, action: str, target_type: str):
    """Hand execution off to remediation-service (Docker/K8s SDK owner).
    remediation-service runs the action, verifies recovery, and updates the
    incident itself -- aiops-engine's job ends at the handoff."""
    try:
        resp = requests.post(
            f"{REMEDIATION_SERVICE_URL}/remediate",
            json={
                "incident_id": incident_id,
                "service_name": service_name,
                "action": action,
                "target_type": target_type,
            },
            headers=_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        logger.info(f"Remediation requested for incident {incident_id}: {resp.json()}")
    except Exception as e:
        logger.error(f"Failed to request remediation for incident {incident_id}: {e}")
        update_incident_status(incident_id, "FAILED")


# ---------------------------------------------------------------------------
# Anomaly handling: RCA -> Decision Engine -> Remediation handoff
# ---------------------------------------------------------------------------
def handle_anomaly(service_name: str, details: str, causes: list, metrics: dict = None, anomaly_score: float = None):
    now = time.time()
    state = REMEDIATION_STATE.get(service_name, {"last_time": 0, "level": 0})

    if now - state["last_time"] > 180 and state["level"] > 0:
        logger.info(f"System recovered. Resetting escalation level for {service_name}.")
        state["level"] = 0

    if now - state["last_time"] < COOLDOWN_SECONDS:
        logger.info(
            f"Cooldown active for {service_name}. Skipping remediation. "
            f"Wait {int(COOLDOWN_SECONDS - (now - state['last_time']))}s."
        )
        return

    state["level"] = min(state["level"] + 1, MAX_ESCALATION_LEVEL)
    state["last_time"] = now
    REMEDIATION_STATE[service_name] = state

    primary_cause, dec = decision.decide(causes)

    # Safety net: if we've escalated repeatedly without recovering, hand off
    # to a human regardless of what the decision engine would otherwise try.
    if state["level"] >= MAX_ESCALATION_LEVEL:
        primary_cause = primary_cause if primary_cause != "UNKNOWN" else "REPEATED_FAILURE"
        dec = decision.Decision(action="human_approval", severity="CRITICAL", target_type=dec.target_type)

    logger.warning(
        f"🚨 ANOMALY on {service_name}: {details} | causes={causes} | "
        f"root_cause={primary_cause} -> action={dec.action} (level {state['level']})"
    )

    incident = open_incident(
        service_name=service_name,
        details=details,
        severity=dec.severity,
        root_cause=primary_cause,
        recommended_action=dec.action,
        metrics=metrics,
        anomaly_score=anomaly_score,
    )

    action_taken = dec.action
    if incident:
        request_remediation(incident["id"], service_name, dec.action, dec.target_type)
    else:
        logger.warning(f"No incident record for {service_name}; skipping remediation handoff this cycle.")

    # Preserve the original local audit log regardless of incident-service /
    # remediation-service availability.
    try:
        db = SessionLocal()
        incident_log = IncidentLog(service_name=service_name, anomaly_type=primary_cause, action_taken=action_taken)
        db.add(incident_log)
        db.commit()
    except Exception as e:
        logger.error(f"DB log error: {e}")
    finally:
        if "db" in locals():
            db.close()


def report_metric_snapshot(service_name: str, metrics: dict):
    try:
        resp = requests.post(
            f"{INCIDENT_SERVICE_URL}/metrics",
            json={"service_name": service_name, **{k: v for k, v in metrics.items() if k != "network_bytes"}},
            headers=_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.debug(f"Failed to report metric snapshot for {service_name}: {e}")


def run_loop():
    logger.info("AIOps Engine started polling cycle")
    while True:
        try:
            # --- Existing ML-based detection (unchanged) ---------------
            df = fetch_metrics('rate(inference_latency_seconds_sum[1m]) / rate(inference_latency_seconds_count[1m])')
            anomalies = detect_anomalies(df)
            if anomalies:
                handle_anomaly(
                    "inference-service",
                    "Isolation Forest ML detected latency anomalies.",
                    causes=["HIGH_LATENCY"],
                )
            else:
                logger.debug("No ML anomalies detected in this cycle.")

            df_err = fetch_metrics('rate(inference_errors_total[1m])')
            if not df_err.empty:
                max_err = df_err["value"].max()
                if max_err > 0.05:
                    handle_anomaly(
                        "inference-service",
                        f"Rule-based detection: error rate {max_err}",
                        causes=["HIGH_ERRORS"],
                    )

            # --- Phase 2/3: RCA + Decision Engine sweep over monitored services
            for service_name in MONITORED_SERVICES:
                service_name = service_name.strip()
                if not service_name:
                    continue
                metrics = rca.collect_service_metrics(service_name)
                report_metric_snapshot(service_name, metrics)
                causes = rca.analyze(metrics)
                if causes:
                    handle_anomaly(
                        service_name,
                        f"RCA rule engine detected {', '.join(causes)} on {service_name}",
                        causes=causes,
                        metrics=metrics,
                    )

        except Exception as e:
            logger.error(f"Error in AIOps loop: {e}")

        time.sleep(15)


if __name__ == "__main__":
    time.sleep(10)
    run_loop()
