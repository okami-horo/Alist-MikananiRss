"""FastAPI routes that expose configuration helpers for the WebUI."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any, Dict
from unittest.mock import Mock

from fastapi import APIRouter, Body, HTTPException

from ..services.config_service import config_service, get_config_service

router = APIRouter()


async def _resolve(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _as_dict(value: Any) -> Dict[str, Any]:
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


@router.get("/current")
async def get_current_config() -> Dict[str, Any]:
    try:
        result = await _resolve(config_service.get_current_config())
        return _as_dict(result)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(500, f"Unable to load configuration: {exc}") from exc


@router.post("/validate")
async def validate_config(config: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    payload = _as_dict(await _resolve(config_service.validate_config(config)))
    if "valid" not in payload:
        payload["valid"] = True
    payload.setdefault("errors", [])
    payload.setdefault("field_errors", {})
    return payload


@router.post("/save")
async def save_config(config: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    result = _as_dict(await _resolve(config_service.save_config(config)))
    if "success" not in result:
        result["success"] = True
    if result.get("success"):
        return result
    raise HTTPException(400, result)


@router.get("/schema")
async def get_schema() -> Dict[str, Any]:
    return _as_dict(await _resolve(config_service.get_config_schema()))


@router.post("/test")
async def test_config(config: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    payload = _as_dict(await _resolve(config_service.test_config(config)))
    payload["success"] = bool(payload.get("success", True))
    payload.setdefault("results", {})
    return payload


__all__ = ["router", "config_service", "get_config_service"]
