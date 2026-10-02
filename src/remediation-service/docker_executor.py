"""
Docker remediation executor -- uses the Docker SDK (docker-py), never shell
commands, so failures surface as typed exceptions instead of parsed stdout.
"""
from __future__ import annotations

from typing import Optional

import docker
from docker.errors import DockerException, NotFound

from shared.logger import setup_logger

logger = setup_logger("remediation-service.docker_executor")

_client: Optional[docker.DockerClient] = None


def get_client() -> Optional[docker.DockerClient]:
    global _client
    if _client is not None:
        return _client
    try:
        _client = docker.from_env()
        _client.ping()
        return _client
    except DockerException as e:
        logger.warning(f"Docker client unavailable, remediation will run in mock mode: {e}")
        _client = None
        return None


def restart_container(name: str, timeout: int = 10) -> dict:
    client = get_client()
    if not client:
        logger.info(f"[MOCK] restart_container({name})")
        return {"mode": "mock", "action": "restart_container", "target": name, "result": "simulated"}
    try:
        container = client.containers.get(name)
        container.restart(timeout=timeout)
        return {"mode": "live", "action": "restart_container", "target": name, "result": "restarted"}
    except NotFound:
        return {"mode": "live", "action": "restart_container", "target": name, "result": "not_found", "error": True}
    except DockerException as e:
        logger.error(f"restart_container({name}) failed: {e}")
        return {"mode": "live", "action": "restart_container", "target": name, "result": "error", "error": str(e)}


def stop_container(name: str, timeout: int = 10) -> dict:
    client = get_client()
    if not client:
        logger.info(f"[MOCK] stop_container({name})")
        return {"mode": "mock", "action": "stop_container", "target": name, "result": "simulated"}
    try:
        container = client.containers.get(name)
        container.stop(timeout=timeout)
        return {"mode": "live", "action": "stop_container", "target": name, "result": "stopped"}
    except NotFound:
        return {"mode": "live", "action": "stop_container", "target": name, "result": "not_found", "error": True}
    except DockerException as e:
        logger.error(f"stop_container({name}) failed: {e}")
        return {"mode": "live", "action": "stop_container", "target": name, "result": "error", "error": str(e)}


def start_container(name: str) -> dict:
    client = get_client()
    if not client:
        logger.info(f"[MOCK] start_container({name})")
        return {"mode": "mock", "action": "start_container", "target": name, "result": "simulated"}
    try:
        container = client.containers.get(name)
        container.start()
        return {"mode": "live", "action": "start_container", "target": name, "result": "started"}
    except NotFound:
        return {"mode": "live", "action": "start_container", "target": name, "result": "not_found", "error": True}
    except DockerException as e:
        logger.error(f"start_container({name}) failed: {e}")
        return {"mode": "live", "action": "start_container", "target": name, "result": "error", "error": str(e)}


def inspect_container(name: str) -> dict:
    client = get_client()
    if not client:
        return {"mode": "mock", "action": "inspect_container", "target": name, "result": "simulated"}
    try:
        container = client.containers.get(name)
        return {
            "mode": "live",
            "action": "inspect_container",
            "target": name,
            "status": container.status,
            "restart_count": container.attrs.get("RestartCount"),
            "started_at": container.attrs.get("State", {}).get("StartedAt"),
            "health": container.attrs.get("State", {}).get("Health", {}).get("Status"),
        }
    except NotFound:
        return {"mode": "live", "action": "inspect_container", "target": name, "result": "not_found", "error": True}
    except DockerException as e:
        logger.error(f"inspect_container({name}) failed: {e}")
        return {"mode": "live", "action": "inspect_container", "target": name, "result": "error", "error": str(e)}
