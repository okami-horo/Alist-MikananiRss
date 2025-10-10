"""System service helpers used by the WebUI layer."""

from __future__ import annotations

import asyncio
import datetime
import subprocess
from pathlib import Path
from typing import Dict, Optional

import psutil

from ..models import SystemStatus

DEFAULT_VERSION = "0.5.5"


class SystemService:
    """Provide high level system status and lifecycle helpers."""

    def __init__(self, main_module: str = "alist_mikananirss") -> None:
        self.main_module = main_module
        self._status: str = "stopped"
        self._start_time: Optional[datetime.datetime] = None
        self._lock = asyncio.Lock()
        self._managed_pid: Optional[int] = None

    async def get_system_status(self) -> SystemStatus:
        """Return current status plus basic resource metrics."""
        async with self._lock:
            running = self._is_main_process_running()
            if running:
                if self._start_time is None:
                    process = self._get_main_process()
                    if process:
                        try:
                            self._start_time = datetime.datetime.fromtimestamp(
                                process.create_time(), datetime.timezone.utc
                            )
                        except Exception:  # pragma: no cover - defensive
                            self._start_time = datetime.datetime.now(datetime.timezone.utc)
                    else:
                        self._start_time = datetime.datetime.now(datetime.timezone.utc)
                self._status = "running"
                uptime = self._calculate_uptime(self._start_time)
            else:
                self._status = "stopped"
                uptime = "0:00:00"
                self._start_time = None

            status_value = self._status

        cpu_usage = psutil.cpu_percent(interval=None)
        memory_usage = psutil.virtual_memory().percent
        drive = Path.cwd().anchor or "/"
        disk_usage = psutil.disk_usage(drive).percent

        return SystemStatus(
            status=status_value,
            uptime=uptime,
            cpu_usage=round(cpu_usage, 2),
            memory_usage=round(memory_usage, 2),
            disk_usage=round(disk_usage, 2),
            version=DEFAULT_VERSION,
        )

    async def start_system(self) -> Dict[str, object]:
        """Attempt to start the main application process."""
        async with self._lock:
            if self._is_main_process_running():
                return {"success": False, "message": "System already running"}

            try:
                process = subprocess.Popen(  # nosec B603 - launched intentionally for tests
                    ["python", "-m", self.main_module],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self._managed_pid = getattr(process, "pid", None)
            except Exception as exc:  # pragma: no cover - defensive
                return {"success": False, "message": f"Failed to start system: {exc}"}

            self._status = "running"
            self._start_time = datetime.datetime.now(datetime.timezone.utc)
            return {"success": True, "message": "System started"}

    async def stop_system(self) -> Dict[str, object]:
        """Attempt to terminate the main application process."""
        async with self._lock:
            if not self._is_main_process_running():
                return {"success": False, "message": "System not running"}

            process = self._get_main_process()
            if not process:
                self._status = "stopped"
                self._start_time = None
                return {"success": True, "message": "System stopped"}

            try:
                process.terminate()
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                process.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            self._status = "stopped"
            self._start_time = None
            self._managed_pid = None
            return {"success": True, "message": "System stopped"}

    async def restart_system(self) -> Dict[str, object]:
        """Stop then start the system."""
        stop_result = await self.stop_system()
        if not stop_result.get("success") and stop_result.get("message") != "System not running":
            return stop_result

        start_result = await self.start_system()
        if start_result.get("success"):
            start_result["message"] = "System restarted"
        return start_result

    async def health_check(self) -> bool:
        """Simple availability probe used by the HTTP layer."""
        async with self._lock:
            return True

    def _is_main_process_running(self) -> bool:
        """Return True if a process for the main module is found."""
        if self._managed_pid:
            try:
                proc = psutil.Process(self._managed_pid)
                if self._matches_target_process(proc.cmdline()):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._managed_pid = None

        for process in psutil.process_iter(["cmdline"]):
            try:
                cmdline = self._safe_cmdline(process)
                if self._matches_target_process(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _get_main_process(self) -> Optional[psutil.Process]:
        """Locate the process running the main module."""
        if self._managed_pid:
            try:
                proc = psutil.Process(self._managed_pid)
                if self._matches_target_process(proc.cmdline()):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._managed_pid = None

        for process in psutil.process_iter(["cmdline"]):
            try:
                cmdline = self._safe_cmdline(process)
                if self._matches_target_process(cmdline):
                    self._managed_pid = process.pid
                    return process
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _calculate_uptime(self, start_time: Optional[datetime.datetime]) -> str:
        """Return HH:MM:SS uptime string for the provided start time."""
        if not start_time:
            return "0:00:00"

        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - start_time
        total_seconds = int(delta.total_seconds())
        return str(datetime.timedelta(seconds=total_seconds))

    @staticmethod
    def _safe_cmdline(process: psutil.Process) -> list[str]:
        """Return a process cmdline, handling attribute differences."""
        if hasattr(process, "cmdline") and callable(process.cmdline):
            return process.cmdline() or []
        return process.info.get("cmdline") or []

    def _matches_target_process(self, cmdline: list[str]) -> bool:
        """Check if the provided cmdline belongs to the controlled service."""
        if not cmdline:
            return False

        joined = " ".join(str(part) for part in cmdline).lower()
        if not joined:
            return False

        # Skip WebUI / uvicorn processes to avoid terminating the WebUI itself
        if "webui" in joined and "server" in joined:
            return False
        if "uvicorn" in joined:
            return False

        return self.main_module.lower() in joined


_system_service: Optional[SystemService] = None


def get_system_service() -> SystemService:
    """Return a shared SystemService instance."""
    global _system_service
    if _system_service is None:
        _system_service = SystemService()
    return _system_service


system_service = get_system_service()
