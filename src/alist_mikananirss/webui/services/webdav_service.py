from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from alist_mikananirss.common.config import AppConfig
from alist_mikananirss.core.webdav_fixer import WebDAVNestedFixer

from .config_service import config_service

logger = logging.getLogger(__name__)


class WebDAVService:
    """Execute WebDAV helper actions for the WebUI."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def run_manual_fix(
        self,
        path: Optional[str] = None,
        *,
        execute_mode: Optional[bool] = None,
        recursive_scan: Optional[bool] = None,
        conflict_strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        async with self._lock:
            cfg_dict = await config_service.get_current_config()
            app_cfg = AppConfig.model_validate(cfg_dict)

            manual_cfg = app_cfg.webdav.manual
            if not manual_cfg.enable:
                return {
                    "success": False,
                    "message": "Manual WebDAV fix is disabled in configuration.",
                }

            target_dir = (path or "").strip() or (manual_cfg.default_path or "").strip()
            if not target_dir:
                target_dir = app_cfg.alist.download_path
            if not target_dir:
                return {
                    "success": False,
                    "message": "No valid target directory specified for manual fix.",
                }

            effective_execute = manual_cfg.execute_mode if execute_mode is None else execute_mode
            effective_recursive = manual_cfg.recursive_scan if recursive_scan is None else recursive_scan

            valid_strategies = {"skip", "rename", "overwrite"}
            effective_conflict = manual_cfg.conflict_strategy
            if conflict_strategy:
                effective_conflict = conflict_strategy if conflict_strategy in valid_strategies else effective_conflict

            dry_run = not effective_execute

            logger.info(
                "Starting manual WebDAV fix: target_dir=%s, execute=%s, recursive=%s, conflict=%s",
                target_dir,
                effective_execute,
                effective_recursive,
                effective_conflict,
            )

            fixer = WebDAVNestedFixer(
                verbose=False,
                url=f"{app_cfg.alist.base_url.rstrip('/')}/dav",
                username=app_cfg.webdav.username,
                password=app_cfg.webdav.password,
                config=app_cfg,
            )

            try:
                result = await fixer.fix_nested_structure(
                    target_dir=target_dir,
                    dry_run=dry_run,
                    handle_conflicts=effective_conflict,
                    recursive=effective_recursive,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Manual WebDAV fix failed: %s", exc)
                return {
                    "success": False,
                    "message": f"Manual WebDAV fix failed: {exc}",
                    "target_dir": target_dir,
                    "dry_run": dry_run,
                    "options": {
                        "execute_mode": effective_execute,
                        "recursive_scan": effective_recursive,
                        "conflict_strategy": effective_conflict,
                    },
                }

            logger.info(
                "Manual WebDAV fix completed: success=%s, total=%s",
                result.get("success"),
                result.get("total_found"),
            )

            overall_success = bool(result.get("success"))
            mode_label = "预览" if dry_run else "执行"
            message = (
                f"Manual WebDAV fix {mode_label} completed"
                if overall_success
                else f"Manual WebDAV fix {mode_label} finished with issues"
            )

            return {
                "success": overall_success,
                "message": message,
                "target_dir": target_dir,
                "dry_run": dry_run,
                "options": {
                    "execute_mode": effective_execute,
                    "recursive_scan": effective_recursive,
                    "conflict_strategy": effective_conflict,
                },
                "result": result,
            }


_webdav_service: Optional[WebDAVService] = None


def get_webdav_service() -> WebDAVService:
    global _webdav_service
    if _webdav_service is None:
        _webdav_service = WebDAVService()
    return _webdav_service


webdav_service = get_webdav_service()
