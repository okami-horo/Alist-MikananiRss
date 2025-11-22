"""
WebUI API路由模块

提供RESTful API接口，包括：
- 系统控制和状态查询
- 日志查看和流式传输
- 配置管理和验证

Central registry for all WebUI API routers.
"""

from __future__ import annotations

from typing import Iterable, Tuple

from fastapi import FastAPI, APIRouter

from .system import router as system_router
from .logs import router as logs_router
from .config import router as config_router
from .webdav import router as webdav_router

API_ROUTERS: Tuple[Tuple[APIRouter, str, list[str]], ...] = (
    (system_router, "/api/system", ["System"]),
    (logs_router, "/api/logs", ["Logs"]),
    (config_router, "/api/config", ["Configuration"]),
    (webdav_router, "/api/webdav", ["WebDAV"]),
)


def register_api_routes(app: FastAPI, routers: Iterable[Tuple[APIRouter, str, Iterable[str]]] | None = None) -> None:
    """Attach all API routers to the provided FastAPI app."""

    active_routers = tuple(routers) if routers is not None else API_ROUTERS
    for router, prefix, tags in active_routers:
        app.include_router(router, prefix=prefix, tags=list(tags))


__all__ = [
    "system_router",
    "logs_router",
    "config_router",
    "webdav_router",
    "API_ROUTERS",
    "register_api_routes",
]