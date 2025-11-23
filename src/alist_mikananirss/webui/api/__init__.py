"""
WebUI API路由模块

提供RESTful API接口，包括：
- 系统控制和状态查询
- 日志查看和流式传输
- 配置管理和验证

Central registry for all WebUI API routers.
"""

from __future__ import annotations

from typing import Iterable, Tuple, Optional

from fastapi import FastAPI, APIRouter

from .system import (
    public_router as system_public_router,
    control_router as system_control_router,
    service_public_router,
    service_control_router,
    router as system_router,
)
from .logs import public_router as logs_public_router, router as logs_router
from .config import admin_router as config_admin_router, router as config_router
from .webdav import admin_router as webdav_admin_router, router as webdav_router

PUBLIC_API_ROUTERS: Tuple[Tuple[APIRouter, str, list[str]], ...] = (
    (service_public_router, "/api/public/service", ["Service", "public"]),
    (system_public_router, "/api/public/system", ["System", "public"]),
    (logs_public_router, "/api/public/logs", ["Logs", "public"]),
)

ADMIN_API_ROUTERS: Tuple[Tuple[APIRouter, str, list[str]], ...] = (
    (service_control_router, "/api/admin/service", ["Service", "admin"]),
    (system_control_router, "/api/admin/system", ["System", "admin"]),
    (config_admin_router, "/api/admin/config", ["Configuration", "admin"]),
    (webdav_admin_router, "/api/admin/webdav", ["WebDAV", "admin"]),
)

LEGACY_API_ROUTERS: Tuple[Tuple[APIRouter, str, list[str]], ...] = (
    (system_router, "/api/system", ["System"]),
    (logs_router, "/api/logs", ["Logs"]),
    (config_router, "/api/config", ["Configuration"]),
    (webdav_router, "/api/webdav", ["WebDAV"]),
)

API_ROUTERS: Tuple[Tuple[APIRouter, str, list[str]], ...] = PUBLIC_API_ROUTERS + ADMIN_API_ROUTERS + LEGACY_API_ROUTERS


def register_api_routes(
    app: FastAPI,
    routers: Iterable[Tuple[APIRouter, str, Iterable[str]]] | None = None,
    dependencies: Optional[Iterable] = None,
) -> None:
    """Attach all API routers to the provided FastAPI app."""

    active_routers = tuple(routers) if routers is not None else API_ROUTERS
    for router, prefix, tags in active_routers:
        include_kwargs = {"prefix": prefix, "tags": list(tags)}
        if dependencies:
            include_kwargs["dependencies"] = list(dependencies)
        app.include_router(router, **include_kwargs)


__all__ = [
    "system_public_router",
    "system_control_router",
    "service_public_router",
    "service_control_router",
    "system_router",
    "logs_public_router",
    "logs_router",
    "config_admin_router",
    "config_router",
    "webdav_admin_router",
    "webdav_router",
    "PUBLIC_API_ROUTERS",
    "ADMIN_API_ROUTERS",
    "LEGACY_API_ROUTERS",
    "API_ROUTERS",
    "register_api_routes",
]
