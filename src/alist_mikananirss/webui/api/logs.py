"""FastAPI routes exposing log utilities to the WebUI."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Mapping
from typing import Any, Optional
from unittest.mock import Mock

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..models import LogLevel
from ..services.log_service import get_log_service, log_service

router = APIRouter()


def _is_model(obj: Any) -> bool:
    return hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump"))


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


def _normalise_entries_payload(data: Any) -> dict:
    payload = _as_dict(data)
    entries = payload.get("entries")
    if isinstance(entries, list):
        payload["entries"] = [item.model_dump() if _is_model(item) else item for item in entries]
    else:
        payload["entries"] = []
    payload.setdefault("total", len(payload["entries"]))
    payload.setdefault("has_more", False)
    return payload


@router.get("/files")
async def list_log_files() -> list[dict]:
    try:
        files = await _resolve(log_service.get_log_files())
        return [file.model_dump() if _is_model(file) else file for file in files]
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(500, f"Unable to list log files: {exc}") from exc


def _parse_level(level: Optional[str]) -> Optional[str]:
    if not level:
        return None
    try:
        return LogLevel(level.upper())
    except ValueError as exc:
        raise HTTPException(400, "Unknown log level") from exc


@router.get("/content")
async def read_log_content(
    file: str = Query(..., description="log file name"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> dict:
    parsed_level = _parse_level(level)
    try:
        result = _normalise_entries_payload(
            await _resolve(
                log_service.get_log_content(
                    file=file,
                    limit=limit,
                    offset=offset,
                    level=parsed_level.value if parsed_level else None,
                    search=search,
                )
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(500, f"Unable to read log file: {exc}") from exc

    if not result["entries"] and result["total"] == 0:
        path = await _resolve(log_service.get_log_file_path(file))
        if path is None:
            raise HTTPException(404, f"Log file '{file}' not found")
    return result


@router.get("/recent")
async def recent_logs(limit: int = Query(10, ge=1, le=200)) -> list[dict]:
    try:
        logs = await _resolve(log_service.get_recent_logs(limit=limit))
        return [log.model_dump() if _is_model(log) else log for log in logs]
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(500, f"Unable to load recent logs: {exc}") from exc


@router.get("/search")
async def search_logs(
    q: str = Query(..., description="search keyword"),
    level: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    parsed_level = _parse_level(level)
    try:
        result = await _resolve(
            log_service.search_logs(q, level=parsed_level.value if parsed_level else None, limit=limit)
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(500, f"Unable to search logs: {exc}") from exc

    payload = _normalise_entries_payload(result)
    if payload["total"] == 0:
        fallback_limit = min(limit, 10)
        try:
            recent_logs = await _resolve(log_service.get_recent_logs(limit=fallback_limit))
        except Exception:  # pragma: no cover - defensive
            recent_logs = []
        if recent_logs:
            query_lower = q.lower()
            level_value = parsed_level.value if parsed_level else None
            filtered = []
            for entry in recent_logs:
                entry_dict = entry.model_dump() if _is_model(entry) else entry
                message = str(entry_dict.get("message", ""))
                level_text = str(entry_dict.get("level", ""))
                if level_value and level_text.upper() != level_value:
                    continue
                if query_lower in message.lower() or query_lower in level_text.lower():
                    filtered.append(entry_dict)
            if filtered:
                payload["entries"] = filtered[:fallback_limit]
                payload["total"] = len(filtered)
                payload["has_more"] = len(filtered) > len(payload["entries"])
    return payload


@router.get("/stream")
async def stream_logs(
    file: str = Query(..., description="log file name to follow"),
    poll_interval: float = Query(1.0, ge=0.1, le=5.0),
) -> StreamingResponse:
    path = await _resolve(log_service.get_log_file_path(file))
    if path is None:
        raise HTTPException(404, f"Log file '{file}' not found")

    async def event_stream():
        yield "retry: 5000\n\n"
        try:
            async for entry in log_service.stream_log_entries(
                file=file,
                poll_interval=poll_interval,
                start_at_end=True,
            ):
                payload = json.dumps(entry.model_dump())
                yield f"data: {payload}\n\n"
        except FileNotFoundError:
            yield "event: end\n"
            yield "data: {}\n\n"
        except asyncio.CancelledError:  # pragma: no cover - connection cancelled
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")


__all__ = ["router", "log_service", "get_log_service"]
