"""Lightweight configuration helpers used by the WebUI APIs."""

from __future__ import annotations

import asyncio
import copy
import logging
import shutil
from pathlib import Path
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp
from pydantic import ValidationError
import yaml

from ...common.config.config import AppConfig
from ..models import ConfigItem, ConfigValidationError

logger = logging.getLogger(__name__)


class ConfigService:
    """Manage application configuration stored in YAML files."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        resolved_path = config_path or os.environ.get("ALIST_MIKAN_CONFIG", "config.yaml")
        self.config_file = Path(resolved_path)
        self._lock = asyncio.Lock()
        self._cache: Dict[str, Any] = {}
        self._meta: Dict[str, Any] = {"needs_setup": False, "source": "file"}

    async def get_current_config(self) -> Dict[str, Any]:
        async with self._lock:
            meta = await self._ensure_loaded()
            normalized = self._normalize_to_app_config(self._cache)
            result = normalized.model_dump(mode="json")
        result["_meta"] = meta
        return result

    async def validate_config(self, config: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        errors: list[Dict[str, str]] = []
        field_errors: Dict[str, list[str]] = {}

        def add_error(field: str, message: str) -> None:
            if any(err for err in errors if err["field"] == field and err["message"] == message):
                return
            errors.append({"field": field, "message": message})
            field_errors.setdefault(field, []).append(message)

        incoming = config or {}
        incoming_common = incoming.get("common", {}) or {}
        incoming_alist = incoming.get("alist", {}) or {}
        incoming_mikan = incoming.get("mikan", {}) or {}

        if not incoming_alist.get("token"):
            add_error("alist.token", "token is required")
        if strict or "download_path" in incoming_alist:
            if not incoming_alist.get("download_path"):
                add_error("alist.download_path", "download_path is required")

        subscribe_urls_raw = incoming_mikan.get("subscribe_url", None)
        subscribe_urls_provided = list(subscribe_urls_raw or [])
        require_subscribe = False
        if strict:
            require_subscribe = self._meta.get("needs_setup", False) or subscribe_urls_raw is not None
        else:
            require_subscribe = subscribe_urls_raw is not None
        if require_subscribe and len(subscribe_urls_provided) == 0:
            add_error("mikan.subscribe_url", "At least one subscribe_url is required")

        merged = self._merge_config(self._default_config(), config or {})

        normalized: AppConfig | None = None
        try:
            normalized = self._normalize_to_app_config(merged)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err.get("loc", []) if part != "__root__")
                add_error(loc or "config", err.get("msg", str(exc)))
        except Exception as exc:
            add_error("config", str(exc))

        normalized_dict = normalized.model_dump(mode="json") if normalized else merged

        common = normalized_dict.get("common", {}) or {}
        if not self._validate_interval_time(common.get("interval_time")):
            add_error("common.interval_time", "interval_time must be >= 60 seconds")

        log_level = common.get("log_level", "INFO")
        if not self._validate_log_level(log_level):
            add_error("common.log_level", "log_level must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL")

        alist = normalized_dict.get("alist", {}) or {}
        base_url = alist.get("base_url", "")
        if not base_url:
            add_error("alist.base_url", "base_url is required")
        elif not self._validate_url(base_url):
            add_error("alist.base_url", "Invalid URL")

        subscribe_urls = list((normalized_dict.get("mikan", {}) or {}).get("subscribe_url", []) or [])
        if len(subscribe_urls) > 0:
            for idx, url in enumerate(subscribe_urls):
                if not self._validate_url(url):
                    add_error(f"mikan.subscribe_url[{idx}]", "Invalid RSS URL")

        webdav_cfg = normalized_dict.get("webdav", {}) or {}
        if webdav_cfg.get("timeout", 0) < 5:
            add_error("webdav.timeout", "timeout must be >= 5 seconds")

        if errors:
            logger.warning(
                "Configuration validation failed",
                extra={
                    "action": "config_validate",
                    "error_count": len(errors),
                    "strict": strict,
                },
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "field_errors": field_errors,
        }

    async def save_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            await self._ensure_loaded()
            validation = await self.validate_config(config, strict=True)
            if not validation["valid"]:
                logger.warning(
                    "Configuration save aborted due to validation errors",
                    extra={"action": "config_save", "error_count": len(validation["errors"])},
                )
                return {
                    "success": False,
                    "errors": validation["errors"],
                    "field_errors": validation["field_errors"],
                }

            merged = self._merge_config(self._cache, config)

            backup_created = False
            if self.config_file.exists() and not self._meta.get("needs_setup", False):
                backup_path = self.config_file.with_suffix(self.config_file.suffix + ".backup")
                shutil.copy(self.config_file, backup_path)
                backup_created = True

            normalized = self._normalize_to_app_config(merged)
            self._cache = normalized.model_dump(mode="json")
            await self._write_yaml(self.config_file, self._cache)
            self._meta = {"needs_setup": False, "source": "file"}
        logger.info(
            "Configuration saved",
            extra={
                "action": "config_save",
                "path": str(self.config_file),
                "backup_created": backup_created,
            },
        )
        return {"success": True, "backup_created": backup_created}

    async def get_config_schema(self) -> Dict[str, Any]:
        async with self._lock:
            await self._ensure_loaded()
            cache_copy = self._clone_config(self._cache)

        schema: Dict[str, Any] = {
            "common": {
                "interval_time": ConfigItem(
                    key="interval_time",
                    value=cache_copy.get("common", {}).get("interval_time", 300),
                    type="integer",
                    description="RSS轮询时间间隔(秒)",
                    required=True,
                ).model_dump(),
                "log_level": ConfigItem(
                    key="log_level",
                    value=cache_copy.get("common", {}).get("log_level", "INFO"),
                    type="select",
                    description="日志级别",
                    required=True,
                ).model_dump(),
            },
            "alist": {
                "base_url": ConfigItem(
                    key="base_url",
                    value=cache_copy.get("alist", {}).get("base_url", "http://localhost:5244"),
                    description="Alist服务器地址",
                    required=True,
                ).model_dump(),
                "token": ConfigItem(
                    key="token",
                    value=cache_copy.get("alist", {}).get("token", ""),
                    description="Alist访问Token",
                    required=True,
                ).model_dump(),
                "downloader": ConfigItem(
                    key="downloader",
                    value=cache_copy.get("alist", {}).get("downloader", "qBittorrent"),
                    type="select",
                    description="下载器类型",
                    required=True,
                ).model_dump(),
                "download_path": ConfigItem(
                    key="download_path",
                    value=cache_copy.get("alist", {}).get("download_path", ""),
                    description="下载保存路径",
                    required=True,
                ).model_dump(),
            },
            "mikan": {
                "subscribe_url": ConfigItem(
                    key="subscribe_url",
                    value=cache_copy.get("mikan", {}).get("subscribe_url", []),
                    type="list",
                    description="RSS订阅地址列表",
                ).model_dump(),
                "filters": ConfigItem(
                    key="filters",
                    value=cache_copy.get("mikan", {}).get("filters", []),
                    type="list",
                    description="过滤规则",
                ).model_dump(),
            },
            "notification": cache_copy.get("notification", {}),
            "rename": cache_copy.get("rename", {}),
            "webdav": cache_copy.get("webdav", {}),
            "webui": cache_copy.get("webui", {}),
            "bot_assistant": cache_copy.get("bot_assistant", {}),
            "dev": cache_copy.get("dev", {}),
        }
        return schema

    async def test_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            await self._ensure_loaded()
            merged = self._merge_config(self._cache, config)

        validation = await self.validate_config(merged, strict=True)
        if not validation["valid"]:
            return {"success": False, "results": {"validation": validation["errors"]}}

        normalized = self._normalize_to_app_config(merged)
        results: Dict[str, Dict[str, str]] = {}

        alist_cfg = normalized.alist
        base_url = alist_cfg.base_url
        token = alist_cfg.token
        if base_url and token:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    headers = {"Authorization": token}
                    async with session.get(f"{base_url}/api/me", headers=headers) as resp:
                        if resp.status == 200:
                            results["alist"] = {"status": "ok", "message": "Alist connected"}
                        else:
                            results["alist"] = {"status": "error", "message": f"HTTP {resp.status}"}
            except Exception as exc:
                results["alist"] = {"status": "error", "message": str(exc)}

        subscribe_urls = normalized.mikan.subscribe_url or []
        if subscribe_urls:
            if all(self._validate_url(url) for url in subscribe_urls):
                results["mikan"] = {"status": "ok", "message": "Mikan subscriptions configured"}
            else:
                results["mikan"] = {"status": "error", "message": "Invalid subscribe_url"}

        success = bool(results) and all(r.get("status") == "ok" for r in results.values())
        logger.info(
            "Configuration connectivity test finished",
            extra={
                "action": "config_test",
                "alist_status": results.get("alist", {}).get("status"),
                "mikan_status": results.get("mikan", {}).get("status"),
                "success": success,
            },
        )
        return {"success": success, "results": results}

    def _validate_url(self, url: str) -> bool:
        parsed = urlparse(url or "")
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _validate_log_level(self, level: str) -> bool:
        if not level:
            return False
        return str(level).upper() in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    def _validate_interval_time(self, value: int) -> bool:
        try:
            return int(value) >= 60
        except (ValueError, TypeError):
            return False

    async def _ensure_loaded(self) -> Dict[str, Any]:
        if self._cache:
            return self._meta.copy()
        if not self.config_file.exists():
            self._cache = self._default_config()
            await self._write_yaml(self.config_file, self._cache)
            self._meta = {"needs_setup": True, "source": "default"}
            logger.warning(
                "Config file missing; generated default configuration",
                extra={"action": "config_recover", "path": str(self.config_file)},
            )
            return self._meta.copy()

        try:
            loaded = await self._read_yaml(self.config_file)
            merged = self._merge_config(self._default_config(), loaded or {})
            normalized = self._normalize_to_app_config(merged)
            self._cache = normalized.model_dump(mode="json")
            self._meta = {"needs_setup": False, "source": "file"}
        except (yaml.YAMLError, ConfigValidationError, ValidationError) as exc:  # pragma: no cover - defensive
            message = getattr(exc, "message", None) or str(exc)
            backup_path = self.config_file.with_suffix(self.config_file.suffix + ".backup")
            try:
                if self.config_file.exists():
                    shutil.copy(self.config_file, backup_path)
            except Exception:
                backup_path = None
            self._cache = self._default_config()
            self._meta = {
                "needs_setup": True,
                "source": "default",
                "recovered_from_error": True,
                "error": f"Config file error: {message}",
            }
            if backup_path:
                self._meta["backup_path"] = str(backup_path)
            await self._write_yaml(self.config_file, self._cache)
            logger.warning(
                "Config file invalid; recovered defaults and created backup",
                extra={
                    "action": "config_recover",
                    "path": str(self.config_file),
                    "backup_path": str(backup_path) if backup_path else None,
                    "error": message,
                },
            )

        return self._meta.copy()

    async def _read_yaml(self, path: Path) -> Dict[str, Any]:
        data = await asyncio.to_thread(path.read_text, encoding="utf-8")
        loaded = yaml.safe_load(data) or {}
        if not isinstance(loaded, dict):
            raise ConfigValidationError("Config file corrupted", {"path": str(path)})
        return loaded

    async def _write_yaml(self, path: Path, data: Dict[str, Any]) -> None:
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=True)
        await asyncio.to_thread(path.write_text, text, "utf-8")

    def _default_config(self) -> Dict[str, Any]:
        return {
            "common": {
                "interval_time": 300,
                "log_level": "INFO",
                "proxies": {},
            },
            "alist": {
                "base_url": "http://127.0.0.1:5244",
                "token": "",
                "downloader": "qBittorrent",
                "download_path": "/downloads",
                "convert_torrent_to_magnet": False,
            },
            "mikan": {
                "subscribe_url": ["https://mikanani.me/RSS/"],
                "filters": [],
                "regex_pattern": {},
            },
            "notification": {
                "enable": False,
                "interval_time": 300,
                "bots": [],
            },
            "rename": {
                "enable": False,
                "rename_format": "{name} S{season:02d}E{episode:02d}",
                "remap": {
                    "enable": False,
                    "cfg_path": "./remap.yaml",
                },
                "extractor": None,
            },
            "webdav": {
                "username": "admin",
                "password": "",
                "timeout": 60,
                "fixer": {
                    "enable": False,
                    "execute_mode": False,
                    "recursive_scan": True,
                    "conflict_strategy": "skip",
                },
                "manual": {
                    "enable": True,
                    "default_path": None,
                    "execute_mode": False,
                    "recursive_scan": True,
                    "conflict_strategy": "skip",
                },
            },
            "webui": {
                "enable": True,
                "host": "0.0.0.0",
                "port": 8080,
                "debug": False,
                "secret_key": "alist-mikananirss-webui-secret-key",
                "session_timeout": 3600,
                "cors_origins": ["http://127.0.0.1:8080", "http://localhost:8080"],
                "allowed_hosts": ["localhost", "127.0.0.1"],
                "auth_enabled": True,
                "auth_header": "X-API-Key",
                "auto_start_monitor": True,
                "use_cdn_assets": False,
                "auto_open_browser": False,
            },
            "bot_assistant": {
                "enable": False,
                "bots": [],
            },
            "dev": {
                "log_level": "INFO",
            },
        }

    def _clone_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(data)

    def _merge_config(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        merged = copy.deepcopy(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_config(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    def _normalize_to_app_config(self, config: Dict[str, Any]) -> AppConfig:
        if isinstance(config, AppConfig):
            return config
        merged = self._merge_config(self._default_config(), config or {})
        return AppConfig.model_validate(merged)


_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


config_service = get_config_service()
