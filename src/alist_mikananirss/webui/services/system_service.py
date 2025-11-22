"""System service helpers used by the WebUI layer."""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import psutil

from ..models import ProcessInfo, SystemStatus

DEFAULT_VERSION = "0.5.5"
PID_FILE = Path("alist_mikananirss.pid")


class SystemService:
    """Provide high level system status and lifecycle helpers."""

    def __init__(self, main_module: str = "alist_mikananirss") -> None:
        self.main_module = main_module
        self._status: str = "stopped"
        self._start_time: Optional[datetime.datetime] = None
        self._lock = asyncio.Lock()
        self._managed_pid: Optional[int] = None
        self._last_error: Optional[str] = None

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


        cpu_usage, memory_usage, disk_usage, process_info = self._collect_resource_stats()

        return SystemStatus(
            status=status_value,
            uptime=uptime,
            cpu_usage=round(cpu_usage, 2),
            memory_usage=round(memory_usage, 2),
            disk_usage=round(disk_usage, 2),
            version=DEFAULT_VERSION,
            process_info=process_info,
            last_error=self._last_error,
        )

    async def start_system(self) -> Dict[str, object]:
        """Attempt to start the main application process."""
        async with self._lock:
            if self._is_main_process_running():
                return {"success": False, "message": "System already running"}

            python_executable = sys.executable or shutil.which("python") or "python"
            try:
                process = subprocess.Popen(  # nosec B603 - launched intentionally for tests
                    [python_executable, "-m", self.main_module],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self._managed_pid = getattr(process, "pid", None)
                self._persist_pid(self._managed_pid)
            except Exception as exc:  # pragma: no cover - defensive
                self._last_error = str(exc)
                return {"success": False, "message": f"Failed to start system: {exc}"}

            await asyncio.sleep(0.2)
            poll_result = None
            if hasattr(process, "poll") and callable(process.poll):
                poll_result = process.poll()

            if isinstance(poll_result, int):
                self._managed_pid = None
                self._last_error = None
                return {
                    "success": False,
                    "message": (
                        "System process exited immediately with code "
                        f"{getattr(process, 'returncode', poll_result)}"
                    ),
                }

            self._status = "running"
            self._start_time = datetime.datetime.now(datetime.timezone.utc)
            self._last_error = None
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
                self._persist_pid(None)
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
            self._persist_pid(None)
            self._last_error = None
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

    def _persist_pid(self, pid: Optional[int]) -> None:
        """Write or clear the tracked PID file."""
        if pid is None:
            try:
                if PID_FILE.exists():
                    PID_FILE.unlink()
            except OSError:
                pass
            return

        try:
            PID_FILE.write_text(str(pid), encoding="utf-8")
        except OSError:
            pass

    def _load_pid_from_file(self) -> Optional[int]:
        """Read PID value persisted on disk."""
        try:
            if PID_FILE.exists():
                value = PID_FILE.read_text(encoding="utf-8").strip()
                return int(value)
        except (OSError, ValueError):
            self._persist_pid(None)
        return None

    def _collect_resource_stats(self) -> tuple[float, float, float, Optional[ProcessInfo]]:
        """Gather host resource metrics plus specific process info if available."""
        cpu_usage = psutil.cpu_percent(interval=None)
        memory_usage = psutil.virtual_memory().percent
        drive = Path.cwd().anchor or "/"
        disk_usage = psutil.disk_usage(drive).percent

        process = self._get_main_process()
        if not process:
            return cpu_usage, memory_usage, disk_usage, None

        try:
            process_info = ProcessInfo(
                pid=process.pid,
                name=process.name(),
                status=self._status,
                start_time=datetime.datetime.fromtimestamp(
                    process.create_time(), datetime.timezone.utc
                ),
                cpu_percent=process.cpu_percent(interval=None),
                memory_mb=round(process.memory_info().rss / (1024 * 1024), 2),
            )
        except (psutil.Error, OSError):  # pragma: no cover - defensive
            process_info = None

        return cpu_usage, memory_usage, disk_usage, process_info

    def _get_main_process(self) -> Optional[psutil.Process]:
        """Locate the process running the main module."""
        if self._managed_pid:
            try:
                proc = psutil.Process(self._managed_pid)
                if self._matches_target_process(proc.cmdline()):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._managed_pid = None
                self._persist_pid(None)

        pid_from_file = self._load_pid_from_file()
        if pid_from_file:
            try:
                proc = psutil.Process(pid_from_file)
                if self._matches_target_process(self._safe_cmdline(proc)):
                    self._managed_pid = pid_from_file
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._persist_pid(None)

        for process in psutil.process_iter(["cmdline"]):
            try:
                cmdline = self._safe_cmdline(process)
                if self._matches_target_process(cmdline):
                    self._managed_pid = process.pid
                    self._persist_pid(self._managed_pid)
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

        tokens = [str(part).lower() for part in cmdline if part]
        if not tokens:
            return False

        disallowed_keywords = {"webui", "uvicorn", "webdav"}
        if any(keyword in token for token in tokens for keyword in disallowed_keywords if keyword in token):
            return False

        module_name = self.main_module.lower()
        disallowed_subcommands = {"webui", "webdav-fix", "webdav_fix"}

        for index, token in enumerate(tokens):
            if token in {"-m", "--module"} and index + 1 < len(tokens):
                target = tokens[index + 1]
                if target == module_name:
                    remaining = tokens[index + 2 :]
                    if remaining and remaining[0] in disallowed_subcommands:
                        return False
                    return True

        entry_names = {
            module_name,
            module_name.replace("_", "-"),
            f"{module_name}.exe",
            f"{module_name.replace('_', '-')}.exe",
        }

        if tokens[0] in entry_names:
            remaining = tokens[1:]
            if remaining and remaining[0] in disallowed_subcommands:
                return False
            return True

        return False


_system_service: Optional[SystemService] = None


def get_system_service() -> SystemService:
    """Return a shared SystemService instance."""
    global _system_service
    if _system_service is None:
        _system_service = SystemService()
    return _system_service


system_service = get_system_service()
