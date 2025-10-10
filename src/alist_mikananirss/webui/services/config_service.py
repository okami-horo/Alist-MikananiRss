"""Lightweight configuration helpers used by the WebUI APIs."""

from __future__ import annotations

import asyncio
import copy
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
import yaml

from ..models import ConfigItem, ConfigValidationError


class ConfigService:
    """Manage application configuration stored in YAML files."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config_file = Path(config_path)
        self._lock = asyncio.Lock()
        self._cache: Dict[str, Any] = {}

    async def get_current_config(self) -> Dict[str, Any]:
        async with self._lock:
            await self._ensure_loaded()
            return self._clone_config(self._cache)

    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        errors = []

        common = config.get("common")
        if not isinstance(common, dict):
            errors.append({"field": "common", "message": "Missing common configuration"})
        else:
            interval = common.get("interval_time")
            if interval is None:
                errors.append({"field": "common.interval_time", "message": "interval_time is required"})
            elif not self._validate_interval_time(interval):
                errors.append({"field": "common.interval_time", "message": "interval_time must be >= 60"})

            log_level = common.get("log_level")
            if log_level is None:
                errors.append({"field": "common.log_level", "message": "log_level is required"})
            elif not self._validate_log_level(log_level):
                errors.append({"field": "common.log_level", "message": "Invalid log level"})

        alist = config.get("alist")
        if not isinstance(alist, dict):
            errors.append({"field": "alist", "message": "Missing alist configuration"})
        else:
            base_url = alist.get("base_url")
            if not base_url:
                errors.append({"field": "alist.base_url", "message": "base_url is required"})
            elif not self._validate_url(base_url):
                errors.append({"field": "alist.base_url", "message": "Invalid URL"})

        return {"valid": len(errors) == 0, "errors": errors}

    async def save_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            await self._ensure_loaded()
            merged = self._merge_config(self._cache, config)

            validation = await self.validate_config(merged)
            if not validation["valid"]:
                return {"success": False, "errors": validation["errors"]}

            if self.config_file.exists():
                backup_path = self.config_file.with_suffix(self.config_file.suffix + ".backup")
                shutil.copy(self.config_file, backup_path)

            self._cache = merged
            await self._write_yaml(self.config_file, self._cache)
        return {"success": True}

    async def get_config_schema(self) -> Dict[str, Any]:
        async with self._lock:
            await self._ensure_loaded()
            cache_copy = self._clone_config(self._cache)

        return {
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
            },
        }

    async def test_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            await self._ensure_loaded()
            merged = self._merge_config(self._cache, config)

        validation = await self.validate_config(merged)
        if not validation["valid"]:
            return {"success": False, "results": {"validation": validation["errors"]}}

        results: Dict[str, Dict[str, str]] = {}

        alist_cfg = merged.get("alist", {})
        base_url = alist_cfg.get("base_url")
        token = alist_cfg.get("token")
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

        mikan_cfg = merged.get("mikan", {})
        if isinstance(mikan_cfg, dict):
            subscribe_urls = mikan_cfg.get("subscribe_url") or []
            if isinstance(subscribe_urls, str):
                subscribe_urls = [subscribe_urls]
            if subscribe_urls:
                if all(self._validate_url(url) for url in subscribe_urls):
                    results["mikan"] = {"status": "ok", "message": "Mikan subscriptions configured"}
                else:
                    results["mikan"] = {"status": "error", "message": "Invalid subscribe_url"}

        success = bool(results) and all(r.get("status") == "ok" for r in results.values())
        return {"success": success, "results": results}

    def _validate_url(self, url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    def _validate_log_level(self, level: str) -> bool:
        return level.upper() in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    def _validate_interval_time(self, value: int) -> bool:
        try:
            return int(value) >= 60
        except (ValueError, TypeError):
            return False

    async def _ensure_loaded(self) -> None:
        if self._cache:
            return
        if not self.config_file.exists():
            self._cache = self._default_config()
            await self._write_yaml(self.config_file, self._cache)
        else:
            try:
                self._cache = await self._read_yaml(self.config_file)
            except yaml.YAMLError as exc:
                raise ConfigValidationError("Config file error", {"message": str(exc)}) from exc
            if not self._cache:
                self._cache = self._default_config()
            else:
                self._cache = self._merge_config(self._default_config(), self._cache)

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
            "common": {"interval_time": 300, "log_level": "INFO"},
            "alist": {"base_url": "http://localhost:5244", "token": ""},
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


_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


config_service = get_config_service()
