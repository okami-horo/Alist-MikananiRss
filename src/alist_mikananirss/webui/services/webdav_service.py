from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from alist_mikananirss.common.config import AppConfig
from alist_mikananirss.core.webdav_fixer import WebDAVNestedFixer

from .config_service import config_service
from ..models import WebdavManualFixJob, WebdavJobStatus

logger = logging.getLogger(__name__)

MAX_JOB_HISTORY = 20


class WebDAVService:
    """Execute WebDAV helper actions for the WebUI."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._jobs: Dict[str, WebdavManualFixJob] = {}

    async def list_jobs(self) -> list[WebdavManualFixJob]:
        return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    async def get_job(self, job_id: str) -> Optional[WebdavManualFixJob]:
        return self._jobs.get(job_id)

    async def submit_manual_fix(
        self,
        path: Optional[str] = None,
        *,
        execute_mode: Optional[bool] = None,
        recursive_scan: Optional[bool] = None,
        conflict_strategy: Optional[str] = None,
    ) -> WebdavManualFixJob:
        cfg_dict = await config_service.get_current_config()
        app_cfg = AppConfig.model_validate(cfg_dict)

        (
            target_dir,
            dry_run,
            effective_execute,
            effective_recursive,
            effective_conflict,
            options,
        ) = self._prepare_manual_fix_options(
            app_cfg,
            path,
            execute_mode=execute_mode,
            recursive_scan=recursive_scan,
            conflict_strategy=conflict_strategy,
        )

        job = WebdavManualFixJob(
            id=uuid.uuid4().hex,
            status=WebdavJobStatus.QUEUED,
            target_dir=target_dir,
            dry_run=dry_run,
            options=options,
            message="Manual WebDAV fix job queued",
        )
        self._store_job(job)

        task = asyncio.create_task(
            self._run_job(
                job.id,
                app_cfg,
                target_dir,
                dry_run,
                effective_execute,
                effective_recursive,
                effective_conflict,
                options,
            )
        )
        task.add_done_callback(self._log_task_exception)

        logger.info(
            "Manual WebDAV fix job queued",
            extra={
                "action": "webdav_manual_fix",
                "job_id": job.id,
                "target_dir": target_dir,
                "dry_run": dry_run,
                "recursive": effective_recursive,
                "conflict_strategy": effective_conflict,
            },
        )

        return job

    async def run_manual_fix(
        self,
        path: Optional[str] = None,
        *,
        execute_mode: Optional[bool] = None,
        recursive_scan: Optional[bool] = None,
        conflict_strategy: Optional[str] = None,
    ) -> WebdavManualFixJob:
        """Backward compatible wrapper for submitting a manual fix job."""
        return await self.submit_manual_fix(
            path=path,
            execute_mode=execute_mode,
            recursive_scan=recursive_scan,
            conflict_strategy=conflict_strategy,
        )

    def _store_job(self, job: WebdavManualFixJob) -> None:
        self._jobs[job.id] = job
        if len(self._jobs) > MAX_JOB_HISTORY:
            # Drop oldest jobs to avoid unbounded growth
            for stale in sorted(self._jobs.values(), key=lambda item: item.created_at)[:-MAX_JOB_HISTORY]:
                self._jobs.pop(stale.id, None)

    async def _run_job(
        self,
        job_id: str,
        app_cfg: AppConfig,
        target_dir: str,
        dry_run: bool,
        effective_execute: bool,
        effective_recursive: bool,
        effective_conflict: str,
        options: Dict[str, Any],
    ) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = WebdavJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.message = "Manual WebDAV fix in progress"
        self._store_job(job)

        try:
            async with self._lock:
                result = await self._execute_manual_fix(
                    app_cfg=app_cfg,
                    target_dir=target_dir,
                    dry_run=dry_run,
                    effective_execute=effective_execute,
                    effective_recursive=effective_recursive,
                    effective_conflict=effective_conflict,
                )

            job.result = result.get("result")
            job.options = result.get("options", options)
            job.target_dir = result.get("target_dir", target_dir)
            job.dry_run = result.get("dry_run", dry_run)
            job.message = result.get("message")
            job.status = WebdavJobStatus.COMPLETED if result.get("success") else WebdavJobStatus.FAILED
            job.error = result.get("error")
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Manual WebDAV fix failed: %s", exc)
            job.status = WebdavJobStatus.FAILED
            job.error = str(exc)
            job.message = job.message or f"Manual WebDAV fix failed: {exc}"
        finally:
            job.finished_at = datetime.now(timezone.utc)
            self._store_job(job)

    def _prepare_manual_fix_options(
        self,
        app_cfg: AppConfig,
        path: Optional[str],
        *,
        execute_mode: Optional[bool],
        recursive_scan: Optional[bool],
        conflict_strategy: Optional[str],
    ) -> Tuple[str, bool, bool, bool, str, Dict[str, Any]]:
        manual_cfg = app_cfg.webdav.manual
        if not manual_cfg.enable:
            raise ValueError("Manual WebDAV fix is disabled in configuration.")

        target_dir = (path or "").strip() or (manual_cfg.default_path or "").strip()
        if not target_dir:
            target_dir = app_cfg.alist.download_path
        if not target_dir:
            raise ValueError("No valid target directory specified for manual fix.")

        effective_execute = manual_cfg.execute_mode if execute_mode is None else execute_mode
        effective_recursive = manual_cfg.recursive_scan if recursive_scan is None else recursive_scan

        valid_strategies = {"skip", "rename", "overwrite"}
        effective_conflict = manual_cfg.conflict_strategy
        if conflict_strategy:
            effective_conflict = conflict_strategy if conflict_strategy in valid_strategies else effective_conflict

        dry_run = not effective_execute

        options = {
            "execute_mode": effective_execute,
            "recursive_scan": effective_recursive,
            "conflict_strategy": effective_conflict,
        }
        return target_dir, dry_run, effective_execute, effective_recursive, effective_conflict, options

    async def _execute_manual_fix(
        self,
        *,
        app_cfg: AppConfig,
        target_dir: str,
        dry_run: bool,
        effective_execute: bool,
        effective_recursive: bool,
        effective_conflict: str,
    ) -> Dict[str, Any]:
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
                "error": str(exc),
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

    @staticmethod
    def _log_task_exception(task: asyncio.Task) -> None:
        try:
            exc = task.exception()
        except asyncio.CancelledError:  # pragma: no cover - defensive
            return
        if exc:  # pragma: no cover - defensive
            logger.error("Manual WebDAV fix task raised an exception: %s", exc)


_webdav_service: Optional[WebDAVService] = None


def get_webdav_service() -> WebDAVService:
    global _webdav_service
    if _webdav_service is None:
        _webdav_service = WebDAVService()
    return _webdav_service


webdav_service = get_webdav_service()
