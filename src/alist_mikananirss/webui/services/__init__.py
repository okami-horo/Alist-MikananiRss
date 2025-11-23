"""
WebUI服务层模块

提供业务逻辑服务，包括：
- SystemService: 系统状态管理
- LogService: 日志查看和流式传输
- ConfigService: 配置管理
"""

from __future__ import annotations

import os
from typing import Dict

from .system_service import SystemService, get_system_service, system_service
from .log_service import LogService, get_log_service, log_service
from .config_service import ConfigService, get_config_service, config_service

ServiceRegistry = Dict[str, object]
_service_registry: ServiceRegistry | None = None


def _build_registry() -> ServiceRegistry:
    return {
        "system": get_system_service(os.environ.get("ALIST_MIKAN_CONFIG")),
        "logs": get_log_service(),
        "config": get_config_service(),
    }


def get_service_registry() -> ServiceRegistry:
    """Return the cached service registry, creating it on first access."""

    global _service_registry
    if _service_registry is None:
        _service_registry = _build_registry()
    return _service_registry


def get_service(name: str):
    """Retrieve a specific service instance by name."""

    registry = get_service_registry()
    try:
        return registry[name]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown service '{name}'") from exc


def refresh_service_registry() -> ServiceRegistry:
    """Rebuild the registry (useful for tests)."""

    global _service_registry
    _service_registry = _build_registry()
    return _service_registry


__all__ = [
    "SystemService",
    "LogService",
    "ConfigService",
    "system_service",
    "log_service",
    "config_service",
    "get_service_registry",
    "get_service",
    "refresh_service_registry",
]
