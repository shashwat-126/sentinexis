"""
Kubernetes remediation executor -- uses the official kubernetes Python
client, never kubectl shell-outs. Falls back to mock mode (same pattern
aiops-engine already used) when no cluster config is reachable, e.g. when
running the whole stack locally via docker-compose without a cluster.
"""
from __future__ import annotations

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from shared.logger import setup_logger

logger = setup_logger("remediation-service.k8s_executor")

_apps_v1 = None
_core_v1 = None
_loaded = False


def _load_config() -> bool:
    global _loaded
    if _loaded:
        return True
    try:
        config.load_incluster_config()
        _loaded = True
    except config.ConfigException:
        try:
            config.load_kube_config()
            _loaded = True
        except Exception:
            logger.warning("No Kubernetes config found. K8s remediation actions will run in mock mode.")
            _loaded = False
    return _loaded


def _clients():
    global _apps_v1, _core_v1
    if not _load_config():
        return None, None
    if _apps_v1 is None:
        _apps_v1 = client.AppsV1Api()
    if _core_v1 is None:
        _core_v1 = client.CoreV1Api()
    return _apps_v1, _core_v1


NAMESPACE_DEFAULT = "default"


def restart_deployment(name: str, namespace: str = NAMESPACE_DEFAULT) -> dict:
    """Equivalent of `kubectl rollout restart deployment/<name>`: patch the
    pod template with a restart timestamp annotation so the Deployment
    controller performs a normal rolling restart (respects maxUnavailable,
    no downtime for multi-replica deployments). Scaling to 0 then back to 1
    -- what this used to do -- causes an outage and loses replica count;
    that approach is gone."""
    apps_v1, _ = _clients()
    if not apps_v1:
        logger.info(f"[MOCK] restart_deployment({name})")
        return {"mode": "mock", "action": "restart_deployment", "target": name, "result": "simulated"}
    try:
        import datetime as _dt

        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": _dt.datetime.utcnow().isoformat() + "Z"
                        }
                    }
                }
            }
        }
        apps_v1.patch_namespaced_deployment(name, namespace, body)
        return {"mode": "live", "action": "restart_deployment", "target": name, "result": "rolling_restart_triggered"}
    except ApiException as e:
        logger.error(f"restart_deployment({name}) failed: {e}")
        return {"mode": "live", "action": "restart_deployment", "target": name, "result": "error", "error": str(e)}


def scale_deployment(name: str, replicas: int, namespace: str = NAMESPACE_DEFAULT) -> dict:
    apps_v1, _ = _clients()
    if not apps_v1:
        logger.info(f"[MOCK] scale_deployment({name}, {replicas})")
        return {"mode": "mock", "action": "scale_deployment", "target": name, "result": "simulated"}
    try:
        apps_v1.patch_namespaced_deployment_scale(name, namespace, {"spec": {"replicas": replicas}})
        return {"mode": "live", "action": "scale_deployment", "target": name, "result": f"scaled_to_{replicas}"}
    except ApiException as e:
        logger.error(f"scale_deployment({name}) failed: {e}")
        return {"mode": "live", "action": "scale_deployment", "target": name, "result": "error", "error": str(e)}


def rollback_deployment(name: str, namespace: str = NAMESPACE_DEFAULT) -> dict:
    """Roll back to the previous ReplicaSet revision -- what `kubectl
    rollout undo` actually does. The old code here patched
    `spec.rollbackTo`, which was removed from the Deployment API in
    `apps/v1` (it only ever existed in the long-deprecated
    `extensions/v1beta1`); that call would have silently no-op'd or errored
    on any modern cluster. This finds the Deployment's ReplicaSets via its
    label selector, picks the one with the second-highest
    `deployment.kubernetes.io/revision` annotation (the revision just
    before the current one), and patches the Deployment's pod template to
    match it."""
    apps_v1, _ = _clients()
    if not apps_v1:
        logger.info(f"[MOCK] rollback_deployment({name})")
        return {"mode": "mock", "action": "rollback_deployment", "target": name, "result": "simulated"}
    try:
        deployment = apps_v1.read_namespaced_deployment(name, namespace)
        match_labels = deployment.spec.selector.match_labels or {}
        selector = ",".join(f"{k}={v}" for k, v in match_labels.items())

        replica_sets = apps_v1.list_namespaced_replica_set(namespace, label_selector=selector).items
        if not replica_sets:
            return {
                "mode": "live", "action": "rollback_deployment", "target": name,
                "result": "error", "error": "No ReplicaSet history found for this deployment",
            }

        def revision(rs) -> int:
            ann = rs.metadata.annotations or {}
            return int(ann.get("deployment.kubernetes.io/revision", "0"))

        replica_sets.sort(key=revision, reverse=True)
        if len(replica_sets) < 2:
            return {
                "mode": "live", "action": "rollback_deployment", "target": name,
                "result": "error", "error": "Only one revision in history -- nothing to roll back to",
            }

        previous_rs = replica_sets[1]  # [0] is current, [1] is the one before it
        body = {"spec": {"template": previous_rs.spec.template.to_dict()}}
        apps_v1.patch_namespaced_deployment(name, namespace, body)
        return {
            "mode": "live", "action": "rollback_deployment", "target": name,
            "result": f"rolled_back_to_revision_{revision(previous_rs)}",
        }
    except ApiException as e:
        logger.error(f"rollback_deployment({name}) failed: {e}")
        return {"mode": "live", "action": "rollback_deployment", "target": name, "result": "error", "error": str(e)}


def delete_pod(name: str, namespace: str = NAMESPACE_DEFAULT) -> dict:
    _, core_v1 = _clients()
    if not core_v1:
        logger.info(f"[MOCK] delete_pod({name})")
        return {"mode": "mock", "action": "delete_pod", "target": name, "result": "simulated"}
    try:
        core_v1.delete_namespaced_pod(name, namespace)
        return {"mode": "live", "action": "delete_pod", "target": name, "result": "deleted"}
    except ApiException as e:
        logger.error(f"delete_pod({name}) failed: {e}")
        return {"mode": "live", "action": "delete_pod", "target": name, "result": "error", "error": str(e)}


def restart_pod(name: str, namespace: str = NAMESPACE_DEFAULT) -> dict:
    # Kubernetes has no in-place pod restart; the standard pattern is
    # deleting the pod so its owning controller recreates it.
    return delete_pod(name, namespace)
