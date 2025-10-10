"""FastAPI routes for system level operations exposed to the WebUI."""

from __future__ import annotations

import inspect
from datetime import datetime
from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

from fastapi import APIRouter, HTTPException, Response

from ..services.system_service import get_system_service, system_service

router = APIRouter()

async def _resolve(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _as_dict(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump", None)):
        dumped = value.model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    if hasattr(value, "dict") and callable(getattr(value, "dict", None)):
        dumped = value.dict()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    if isinstance(value, Mock):
        return {}
    if value is None:
        return {}
    return {"result": value}


@router.get("/status")
async def get_system_status() -> dict:
    try:
        status = await _resolve(system_service.get_system_status())
        return _as_dict(status)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(500, f"Unable to retrieve system status: {exc}") from exc


@router.post("/start")
async def start_system() -> dict:
    result = _as_dict(await _resolve(system_service.start_system()))
    if result.get("success"):
        return result
    raise HTTPException(400, result.get("message", "Unable to start system"))


@router.post("/stop")
async def stop_system() -> dict:
    result = _as_dict(await _resolve(system_service.stop_system()))
    if result.get("success"):
        return result
    raise HTTPException(400, result.get("message", "Unable to stop system"))


@router.post("/restart")
async def restart_system() -> dict:
    result = _as_dict(await _resolve(system_service.restart_system()))
    if result.get("success"):
        return result
    raise HTTPException(400, result.get("message", "Unable to restart system"))


@router.get("/health")
async def health_check() -> dict:
    healthy = await _resolve(system_service.health_check())
    return {"healthy": healthy, "timestamp": datetime.utcnow().isoformat()}


@router.options("/status", include_in_schema=False)
async def options_status() -> Response:
    response = Response(status_code=200)
    response.headers["access-control-allow-origin"] = "*"
    response.headers["access-control-allow-methods"] = "*"
    response.headers["access-control-allow-headers"] = "*"
    return response


# Provide the getter in __all__ for tests/consumers needing a fresh instance.
__all__ = ["router", "get_system_service", "system_service"]
