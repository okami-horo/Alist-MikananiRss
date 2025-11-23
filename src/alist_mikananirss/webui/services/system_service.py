"""Service lifecycle helpers used by the WebUI layer."""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import psutil

from ...alist import Alist
from ...common.config.config import AppConfig, ConfigManager
from ...common.database import SubscribeDatabase
from ...core.bot_assistant import BotAssistant
from ...core.download_manager import DownloadManager
from ...core.filter import RegexFilter
from ...core.notification_sender import NotificationSender
from ...core.remapper import RemapperManager
from ...core.renamer import AnimeRenamer
from ...core.rss_monitor import RssMonitor
from ...core.webdav_fixer import WebDAVNestedFixer
from ...extractor import Extractor, LLMExtractor, create_llm_provider
from ...main import init_logging, init_notification, init_proxies
from ..models import ProcessInfo, SystemStatus

DEFAULT_VERSION = "0.5.5"
logger = logging.getLogger(__name__)


@dataclass
class MonitorRuntime:
    """Track the resources and tasks that make up the subscription monitor."""

    config: AppConfig
    db: SubscribeDatabase
    alist_client: Alist
    rss_monitor: RssMonitor
    tasks: list[asyncio.Task] = field(default_factory=list)
    bot_assistant: BotAssistant | None = None
    webdav_fixer: WebDAVNestedFixer | None = None

    async def shutdown(self, cancel_tasks: bool = True) -> None:
        """Cancel running tasks and dispose of shared resources."""

        active_tasks = [task for task in self.tasks if task is not None]
        if cancel_tasks:
            for task in active_tasks:
                if not task.done():
                    task.cancel()

        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)

        if self.bot_assistant:
            with suppress(Exception):
                await self.bot_assistant.stop()

        with suppress(Exception):
            await self.db.close()
        with suppress(Exception):
            await self.alist_client.close()

        with suppress(Exception):
            DownloadManager.destroy_instance()
        with suppress(Exception):
            NotificationSender.destroy_instance()
        with suppress(Exception):
            AnimeRenamer.destroy_instance()
        with suppress(Exception):
            RemapperManager.destroy_instance()
        with suppress(Exception):
            Extractor.destroy_instance()


class SystemService:
    """Provide lifecycle helpers for the embedded subscription monitor."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path or os.environ.get("ALIST_MIKAN_CONFIG", "config.yaml"))
        self._status: str = "stopped"
        self._start_time: Optional[datetime.datetime] = None
        self._lock = asyncio.Lock()
        self._monitor_task: Optional[asyncio.Task] = None
        self._runtime: Optional[MonitorRuntime] = None
        self._last_error: Optional[str] = None

    def set_config_path(self, path: str | Path) -> None:
        """Update the configuration path used for future restarts."""
        self.config_path = Path(path)

    async def get_system_status(self) -> SystemStatus:
        """Return current monitor status plus basic resource metrics."""
        async with self._lock:
            status_value = self._status
            start_time = self._start_time
            last_error = self._last_error

        uptime = self._calculate_uptime(start_time)
        cpu_usage, memory_usage, disk_usage, process_info = self._collect_resource_stats(status_value)

        return SystemStatus(
            status=status_value,
            uptime=uptime,
            cpu_usage=round(cpu_usage, 2),
            memory_usage=round(memory_usage, 2),
            disk_usage=round(disk_usage, 2),
            version=DEFAULT_VERSION,
            process_info=process_info,
            last_error=last_error,
            service_status=status_value,
        )

    async def start_system(self) -> Dict[str, object]:
        """Start the in-process subscription monitor."""
        async with self._lock:
            if self._monitor_task and not self._monitor_task.done():
                logger.info("Subscription service already running")
                return {"success": False, "message": "Service already running"}
            self._status = "starting"
            self._last_error = None

        try:
            runtime = await self._initialize_runtime()
        except Exception as exc:  # pragma: no cover - defensive
            async with self._lock:
                self._status = "error"
                self._last_error = str(exc)
                self._monitor_task = None
                self._runtime = None
                self._start_time = None
            logger.exception("Failed to start subscription service: %s", exc)
            return {"success": False, "message": f"Failed to start service: {exc}"}

        monitor_task = asyncio.create_task(
            self._run_runtime(runtime), name="alist-mikananirss-monitor"
        )

        async with self._lock:
            self._runtime = runtime
            self._monitor_task = monitor_task
            self._status = "running"
            self._start_time = datetime.datetime.now(datetime.timezone.utc)

        logger.info("Subscription service started with config at %s", self.config_path)
        return {"success": True, "message": "Service started"}

    async def stop_system(self) -> Dict[str, object]:
        """Request a graceful shutdown of the subscription monitor."""
        async with self._lock:
            task = self._monitor_task
            if not task or task.done():
                self._status = "stopped"
                self._start_time = None
                logger.info("Stop request ignored because service is not running")
                return {"success": False, "message": "Service not running"}

            self._status = "stopping"

        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        async with self._lock:
            self._monitor_task = None
            self._runtime = None
            self._start_time = None
            stopped = self._status != "error"
            if stopped:
                self._status = "stopped"
                self._last_error = None

        logger.info("Subscription service stopped")
        return {"success": True, "message": "Service stopped"}

    async def restart_system(self) -> Dict[str, object]:
        """Restart the monitor service."""
        stop_result = await self.stop_system()
        if not stop_result.get("success") and stop_result.get("message") != "Service not running":
            return stop_result
        start_result = await self.start_system()
        if start_result.get("success"):
            start_result["message"] = "Service restarted"
        return start_result

    async def health_check(self) -> bool:
        """Simple availability probe used by the HTTP layer."""
        async with self._lock:
            return self._status == "running"

    def _load_config(self) -> AppConfig:
        """Load the AppConfig from disk."""
        manager = ConfigManager()
        try:
            return manager.load_config(self.config_path)
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to load config from {self.config_path}: {exc}") from exc

    async def _initialize_runtime(self) -> MonitorRuntime:
        """Prepare all runtime dependencies for the monitor."""
        cfg = self._load_config()
        init_logging(cfg)
        init_proxies(cfg)

        db = await SubscribeDatabase.create()
        alist_client: Optional[Alist] = None
        rss_monitor: Optional[RssMonitor] = None
        bot_assistant: Optional[BotAssistant] = None
        webdav_fixer: Optional[WebDAVNestedFixer] = None
        tasks: list[asyncio.Task] = []

        try:
            alist_client = Alist(cfg.alist.base_url, cfg.alist.token, cfg.alist.downloader)
            alist_ver = await alist_client.get_alist_ver()
            if alist_ver < "3.42.0":
                raise RuntimeError(f"Unsupported Alist version: {alist_ver}")

            if cfg.webdav.fixer.enable:
                webdav_url = f"{cfg.alist.base_url.rstrip('/')}/dav"
                webdav_fixer = WebDAVNestedFixer(
                    alist_client=alist_client,
                    verbose=False,
                    url=webdav_url,
                    username=cfg.webdav.username,
                    password=cfg.webdav.password,
                    config=cfg,
                )

            self._reset_singletons()
            DownloadManager.initialize(
                alist_client=alist_client,
                base_download_path=cfg.alist.download_path,
                use_renamer=cfg.rename.enable,
                need_notification=cfg.notification.enable,
                db=db,
                convert_torrent_to_magnet=cfg.alist.convert_torrent_to_magnet,
                enable_webdav_fix=cfg.webdav.fixer.enable,
                webdav=cfg.webdav,
                webdav_fixer=webdav_fixer,
            )

            if cfg.rename.enable:
                extractor_cfg = cfg.rename.extractor
                if extractor_cfg is None:
                    raise RuntimeError("Rename enabled but extractor configuration is missing")
                provider_kwargs = extractor_cfg.model_dump(
                    exclude={"extractor_type", "output_type"}
                )
                llm_provider = create_llm_provider(
                    extractor_cfg.extractor_type, **provider_kwargs
                )
                Extractor.initialize(LLMExtractor(llm_provider, extractor_cfg.output_type))
                AnimeRenamer.initialize(alist_client, cfg.rename.rename_format)

            if cfg.rename.remap.enable:
                RemapperManager.load_remappers_from_cfg(cfg.rename.remap.cfg_path)

            regex_filter = RegexFilter()
            regex_filter.update_regex(cfg.mikan.regex_pattern or {})
            for name in cfg.mikan.filters or []:
                regex_filter.add_pattern(name)

            rss_monitor = RssMonitor(
                subscribe_urls=list(cfg.mikan.subscribe_url or []),
                db=db,
                filter=regex_filter,
                use_extractor=cfg.rename.enable,
                convert_torrent_to_magnet=cfg.alist.convert_torrent_to_magnet,
            )
            rss_monitor.set_interval_time(cfg.common.interval_time)

            tasks.append(asyncio.create_task(rss_monitor.run(), name="rss-monitor"))

            if cfg.notification.enable:
                init_notification(cfg)
                tasks.append(asyncio.create_task(NotificationSender.run(), name="notification-sender"))

            if cfg.bot_assistant.enable and cfg.bot_assistant.bots:
                bot_cfg = cfg.bot_assistant.bots[0]
                if bot_cfg.bot_type == "telegram":
                    bot_assistant = BotAssistant(bot_cfg.token, rss_monitor)
                    tasks.append(asyncio.create_task(bot_assistant.run(), name="bot-assistant"))

            return MonitorRuntime(
                config=cfg,
                db=db,
                alist_client=alist_client,
                rss_monitor=rss_monitor,
                bot_assistant=bot_assistant,
                webdav_fixer=webdav_fixer,
                tasks=tasks,
            )
        except Exception:
            for task in tasks:
                with suppress(Exception):
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if bot_assistant:
                with suppress(Exception):
                    await bot_assistant.stop()
            with suppress(Exception):
                await db.close()
            if alist_client:
                with suppress(Exception):
                    await alist_client.close()
            self._reset_singletons()
            raise

    async def _run_runtime(self, runtime: MonitorRuntime) -> None:
        """Run the assembled runtime tasks until completion or cancellation."""
        try:
            await asyncio.gather(*runtime.tasks)
        except asyncio.CancelledError:
            logger.info("Subscription service task cancelled")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            async with self._lock:
                self._last_error = str(exc)
                self._status = "error"
            logger.exception("Subscription service crashed: %s", exc)
            raise
        finally:
            await runtime.shutdown(cancel_tasks=False)
            async with self._lock:
                if self._status != "error":
                    self._status = "stopped"
                self._monitor_task = None
                self._runtime = None
                self._start_time = None

    def _reset_singletons(self) -> None:
        """Clear singleton instances to ensure fresh configuration is applied."""
        with suppress(Exception):
            DownloadManager.destroy_instance()
        with suppress(Exception):
            NotificationSender.destroy_instance()
        with suppress(Exception):
            AnimeRenamer.destroy_instance()
        with suppress(Exception):
            RemapperManager.destroy_instance()
        with suppress(Exception):
            Extractor.destroy_instance()

    def _collect_resource_stats(self, status: str) -> tuple[float, float, float, Optional[ProcessInfo]]:
        """Gather host resource metrics plus current process info."""
        cpu_usage = psutil.cpu_percent(interval=None)
        memory_usage = psutil.virtual_memory().percent
        drive = Path.cwd().anchor or "/"
        disk_usage = psutil.disk_usage(drive).percent

        try:
            process = psutil.Process(os.getpid())
            process_info = ProcessInfo(
                pid=process.pid,
                name=process.name(),
                status=status,
                start_time=datetime.datetime.fromtimestamp(
                    process.create_time(), datetime.timezone.utc
                ),
                cpu_percent=process.cpu_percent(interval=None),
                memory_mb=round(process.memory_info().rss / (1024 * 1024), 2),
            )
        except (psutil.Error, OSError):  # pragma: no cover - defensive
            process_info = None

        return cpu_usage, memory_usage, disk_usage, process_info

    def _calculate_uptime(self, start_time: Optional[datetime.datetime]) -> str:
        """Return HH:MM:SS uptime string for the provided start time."""
        if not start_time:
            return "0:00:00"

        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - start_time
        total_seconds = int(delta.total_seconds())
        return str(datetime.timedelta(seconds=total_seconds))


_system_service: Optional[SystemService] = None


def get_system_service(config_path: str | Path | None = None) -> SystemService:
    """Return a shared SystemService instance."""
    global _system_service
    if _system_service is None:
        _system_service = SystemService(config_path=config_path)
    elif config_path:
        _system_service.set_config_path(config_path)
    return _system_service


system_service = get_system_service()
