"""
WebUI API单元测试

测试WebUI的所有API端点功能，包括系统控制、日志查看和配置管理。
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from aioresponses import aioresponses
import yaml

from alist_mikananirss.webui.server import app
from alist_mikananirss.webui.models import (
    SystemStatus,
    LogEntry,
    ConfigItem,
    WebdavManualFixJob,
    WebdavJobStatus,
)
from alist_mikananirss.webui.services.config_service import ConfigService


class TestSystemAPI:
    """系统控制API测试"""

    def setup_method(self):
        """测试前置设置"""
        self.client = TestClient(app)

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_get_system_status(self, mock_service):
        """测试获取系统状态"""
        # 模拟服务返回
        mock_service.get_system_status.return_value = SystemStatus(
            status="running",
            uptime="2:30:45",
            cpu_usage=25.5,
            memory_usage=60.2,
            disk_usage=45.8,
            version="0.5.5"
        )

        response = self.client.get("/api/system/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["cpu_usage"] == 25.5
        assert data["memory_usage"] == 60.2

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_start_system(self, mock_service):
        """测试启动系统"""
        mock_service.start_system.return_value = {"success": True, "message": "System started"}

        response = self.client.post("/api/system/start")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.start_system.assert_called_once()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_start_system_failure_returns_400(self, mock_service):
        """启动失败时返回400并带有人类可读信息"""
        mock_service.start_system.return_value = {
            "success": False,
            "message": "System already running",
        }

        response = self.client.post("/api/system/start")

        assert response.status_code == 400
        assert response.json()["detail"] == "System already running"
        mock_service.start_system.assert_called_once()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_stop_system(self, mock_service):
        """测试停止系统"""
        mock_service.stop_system.return_value = {"success": True, "message": "System stopped"}

        response = self.client.post("/api/system/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.stop_system.assert_called_once()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_stop_system_failure_returns_400(self, mock_service):
        """停止失败时返回400并暴露错误原因"""
        mock_service.stop_system.return_value = {
            "success": False,
            "message": "System not running",
        }

        response = self.client.post("/api/system/stop")

        assert response.status_code == 400
        assert response.json()["detail"] == "System not running"
        mock_service.stop_system.assert_called_once()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_restart_system(self, mock_service):
        """测试重启系统"""
        mock_service.restart_system.return_value = {"success": True, "message": "System restarted"}

        response = self.client.post("/api/system/restart")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.restart_system.assert_called_once()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_restart_system_failure_returns_400(self, mock_service):
        """重启失败时返回400，提示调用方检查状态"""
        mock_service.restart_system.return_value = {
            "success": False,
            "message": "Unable to stop system",
        }

        response = self.client.post("/api/system/restart")

        assert response.status_code == 400
        assert response.json()["detail"] == "Unable to stop system"
        mock_service.restart_system.assert_called_once()

    def test_health_check(self):
        """测试健康检查端点"""
        response = self.client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "webui"


class TestLogsAPI:
    """日志API测试"""

    def setup_method(self):
        """测试前置设置"""
        self.client = TestClient(app)

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_get_log_files(self, mock_service):
        """测试获取日志文件列表"""
        mock_service.get_log_files.return_value = [
            {"name": "app.log", "size": 1024000, "modified": "2025-10-10T10:00:00"},
            {"name": "error.log", "size": 512000, "modified": "2025-10-10T09:30:00"}
        ]

        response = self.client.get("/api/logs/files")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "app.log"
        assert data[0]["size"] == 1024000

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_get_log_content(self, mock_service):
        """测试获取日志内容"""
        mock_logs = [
            {
                "timestamp": "2025-10-10T10:00:00",
                "level": "INFO",
                "message": "System started successfully",
                "module": None,
                "line_number": None,
                "thread_id": None,
            },
            {
                "timestamp": "2025-10-10T10:01:00",
                "level": "WARNING",
                "message": "High memory usage detected",
                "module": None,
                "line_number": None,
                "thread_id": None,
            },
        ]
        mock_service.get_log_content.return_value = {
            "entries": mock_logs,
            "total": 2,
            "has_more": False
        }

        response = self.client.get("/api/logs/content?file=app.log&limit=100")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["entries"]) == 2
        assert data["entries"][0]["level"] == "INFO"

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_get_log_content_missing_file(self, mock_service):
        """缺少日志文件时返回404"""
        mock_service.get_log_content.side_effect = FileNotFoundError("Log file 'app.log' not found")

        response = self.client.get("/api/logs/content?file=app.log")

        assert response.status_code == 404
        assert "app.log" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_get_log_content_invalid_level(self, mock_service):
        """非法日志级别返回400"""
        response = self.client.get("/api/logs/content?file=app.log&level=invalid")

        assert response.status_code == 400
        mock_service.get_log_content.assert_not_called()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_get_recent_logs(self, mock_service):
        """测试获取最近日志"""
        mock_service.get_recent_logs.return_value = [
            {
                "timestamp": "2025-10-10T10:05:00",
                "level": "ERROR",
                "message": "Connection failed",
                "module": None,
                "line_number": None,
                "thread_id": None,
            }
        ]

        response = self.client.get("/api/logs/recent?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["level"] == "ERROR"

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_search_logs(self, mock_service):
        """测试搜索日志"""
        mock_service.search_logs.return_value = {
            "entries": [
                {
                    "timestamp": "2025-10-10T10:00:00",
                    "level": "INFO",
                    "message": "Download completed: anime.mkv",
                    "module": None,
                    "line_number": None,
                    "thread_id": None,
                }
            ],
            "total": 1,
            "has_more": False
        }

        response = self.client.get("/api/logs/search?q=download&level=INFO")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "download" in data["entries"][0]["message"].lower()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_search_logs_invalid_level(self, mock_service):
        """搜索日志时非法级别返回400"""
        response = self.client.get("/api/logs/search?q=download&level=verbose")

        assert response.status_code == 400
        mock_service.search_logs.assert_not_called()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_stream_logs_endpoint(self, mock_service):
        """测试实时日志流端点返回SSE数据"""

        mock_service.get_tail_entries.return_value = {
            "entries": [
                {
                    "timestamp": "2025-10-10T10:05:00",
                    "level": "INFO",
                    "message": "Snapshot event",
                    "module": None,
                    "line_number": None,
                    "thread_id": None,
                }
            ],
            "total": 1,
            "has_more": False,
        }

        async def fake_stream_log_entries(*_, **__):
            yield LogEntry(
                timestamp="2025-10-10T10:10:00",
                level="INFO",
                message="Tail event",
                module=None,
                line_number=None,
                thread_id=None,
            )

        mock_service.get_log_file_path.return_value = Path("app.log")
        mock_service.stream_log_entries.return_value = fake_stream_log_entries()

        with self.client.stream(
            "GET",
            "/api/logs/stream?file=app.log&poll_interval=0.1&level=INFO&initial_limit=1",
        ) as response:
            assert response.status_code == 200
            lines = []
            for raw_line in response.iter_lines():
                text_line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
                lines.append(text_line)
                if text_line.startswith("data: ") and "Tail event" in text_line:
                    break

        assert any(line.startswith("retry:") for line in lines)
        assert any(line.startswith("event: snapshot") for line in lines)
        assert any("Tail event" in line for line in lines if isinstance(line, str))
        mock_service.get_tail_entries.assert_called_once()
        mock_service.stream_log_entries.assert_called_once_with(
            file="app.log",
            poll_interval=0.1,
            start_at_end=True,
            level="INFO",
            search=None,
        )

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_stream_logs_file_not_found(self, mock_service):
        """测试实时日志流端点文件不存在错误"""
        mock_service.get_log_file_path.return_value = None

        response = self.client.get("/api/logs/stream?file=missing.log")

        assert response.status_code == 404


class TestConfigAPI:
    """配置API测试"""

    def setup_method(self):
        """测试前置设置"""
        self.client = TestClient(app)

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.config.config_service')
    async def test_get_current_config(self, mock_service):
        """测试获取当前配置"""
        mock_service.get_current_config.return_value = {
            "common": {"interval_time": 300, "log_level": "INFO"},
            "alist": {"base_url": "http://localhost:5244", "downloader": "qBittorrent"}
        }

        response = self.client.get("/api/config/current")

        assert response.status_code == 200
        data = response.json()
        assert "common" in data
        assert "alist" in data
        assert data["common"]["interval_time"] == 300

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.config.config_service')
    async def test_validate_config(self, mock_service):
        """测试配置验证"""
        mock_service.validate_config.return_value = {
            "valid": True,
            "errors": []
        }

        test_config = {
            "common": {"interval_time": 300},
            "alist": {"base_url": "http://localhost:5244"}
        }

        response = self.client.post(
            "/api/config/validate",
            json=test_config
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.config.config_service')
    async def test_validate_config_with_errors(self, mock_service):
        """测试配置验证（有错误）"""
        mock_service.validate_config.return_value = {
            "valid": False,
            "errors": [
                {
                    "section": "alist",
                    "field": "base_url",
                    "message": "Invalid URL format"
                }
            ]
        }

        invalid_config = {
            "alist": {"base_url": "invalid-url"}
        }

        response = self.client.post(
            "/api/config/validate",
            json=invalid_config
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert data["errors"][0]["field"] == "base_url"

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.config.config_service')
    async def test_save_config(self, mock_service):
        """测试保存配置"""
        mock_service.save_config.return_value = {"success": True}

        test_config = {
            "common": {"interval_time": 600},
            "alist": {"base_url": "http://localhost:5244"}
        }

        response = self.client.post(
            "/api/config/save",
            json=test_config
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.save_config.assert_called_once_with(test_config)

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.config.config_service')
    async def test_get_config_schema(self, mock_service):
        """测试获取配置模式"""
        mock_service.get_config_schema.return_value = {
            "common": {
                "interval_time": {"type": "integer", "min": 60, "default": 300},
                "log_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"], "default": "INFO"}
            }
        }

        response = self.client.get("/api/config/schema")

        assert response.status_code == 200
        data = response.json()
        assert "common" in data
        assert data["common"]["interval_time"]["type"] == "integer"

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.config.config_service')
    async def test_test_config(self, mock_service):
        """测试配置连接测试"""
        mock_service.test_config.return_value = {
            "success": True,
            "results": {
                "alist": {"status": "connected", "message": "Connection successful"},
                "mikan": {"status": "connected", "message": "RSS feed accessible"}
            }
        }

        test_config = {
            "alist": {"base_url": "http://localhost:5244"},
            "mikan": {"subscribe_url": ["https://example.com/rss"]}
        }

        response = self.client.post(
            "/api/config/test",
            json=test_config
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "alist" in data["results"]
        assert data["results"]["alist"]["status"] == "connected"


class TestConfigAPIUS2:
    """User Story 2 相关的配置API测试"""

    def setup_method(self):
        self.client = TestClient(app)

    def _override_config_service(self, monkeypatch, config_path: Path) -> ConfigService:
        service = ConfigService(config_path=str(config_path))
        service_module = "alist_mikananirss.webui.services.config_service"
        api_module = "alist_mikananirss.webui.api.config"

        monkeypatch.setattr(f"{service_module}._config_service", service, raising=False)
        monkeypatch.setattr(f"{service_module}.config_service", service, raising=False)
        monkeypatch.setattr(f"{service_module}.get_config_service", lambda: service, raising=False)
        monkeypatch.setattr(f"{api_module}.config_service", service, raising=False)
        monkeypatch.setattr(f"{api_module}.get_config_service", lambda: service, raising=False)
        return service

    def test_get_current_config_without_file_returns_default_meta(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        self._override_config_service(monkeypatch, config_path)

        response = self.client.get("/api/config/current")

        assert response.status_code == 200
        data = response.json()
        assert data["common"]["interval_time"] >= 60
        assert isinstance(data["alist"]["base_url"], str)
        assert isinstance(data["alist"]["download_path"], str)
        assert data["_meta"]["needs_setup"] is True
        assert data["_meta"]["source"] == "default"

    def test_get_current_config_with_corrupted_file_recovers(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("common: [broken")
        self._override_config_service(monkeypatch, config_path)

        response = self.client.get("/api/config/current")

        assert response.status_code == 200
        meta = response.json()["_meta"]
        assert meta["needs_setup"] is True
        assert meta["recovered_from_error"] is True
        assert meta["error"].startswith("Config file error")

    def test_save_config_creates_backup_file(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        base_config = {
            "common": {"interval_time": 300, "log_level": "INFO"},
            "alist": {
                "base_url": "http://127.0.0.1:5244",
                "token": "token",
                "downloader": "qBittorrent",
                "download_path": "/downloads",
                "convert_torrent_to_magnet": False,
            },
        }
        config_path.write_text(yaml.safe_dump(base_config, allow_unicode=True))
        self._override_config_service(monkeypatch, config_path)

        payload = {
            "common": {"interval_time": 600, "log_level": "DEBUG"},
            "alist": {
                "base_url": "http://127.0.0.1:5244",
                "token": "token",
                "downloader": "qBittorrent",
                "download_path": "/downloads",
                "convert_torrent_to_magnet": False,
            },
        }

        response = self.client.post("/api/config/save", json=payload)

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["backup_created"] is True
        assert config_path.with_suffix(".yaml.backup").exists()

    def test_save_config_returns_validation_errors_detail(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        self._override_config_service(monkeypatch, config_path)

        payload = {
            "common": {"interval_time": 10},
            "alist": {"base_url": "bad"},
        }

        response = self.client.post("/api/config/save", json=payload)

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "common.interval_time" in detail["field_errors"]
        assert "alist.base_url" in detail["field_errors"]
        assert "alist.token" in detail["field_errors"]
        assert "alist.download_path" in detail["field_errors"]
        assert "mikan.subscribe_url" in detail["field_errors"]
        assert detail["success"] is False
        assert isinstance(detail["errors"], list)

    def test_validate_config_reports_missing_required_fields(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        self._override_config_service(monkeypatch, config_path)

        invalid_config = {
            "common": {"interval_time": 10, "log_level": "INVALID"},
            "alist": {"base_url": "", "token": "", "download_path": ""},
            "mikan": {"subscribe_url": []},
        }

        response = self.client.post("/api/config/validate", json=invalid_config)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "common.interval_time" in data["field_errors"]
        assert "common.log_level" in data["field_errors"]
        assert "alist.base_url" in data["field_errors"]
        assert "alist.token" in data["field_errors"]
        assert "alist.download_path" in data["field_errors"]
        assert "mikan.subscribe_url" in data["field_errors"]

    def test_test_config_returns_validation_errors_when_invalid(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        self._override_config_service(monkeypatch, config_path)

        invalid_config = {
            "common": {"interval_time": 30},
            "alist": {"base_url": "invalid", "token": "", "download_path": ""},
            "mikan": {"subscribe_url": []},
        }

        response = self.client.post("/api/config/test", json=invalid_config)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "validation" in data["results"]
        assert any("alist.base_url" in err["field"] for err in data["results"]["validation"])


class TestWebDAVAPI:
    """WebDAV API 测试"""

    def setup_method(self):
        self.client = TestClient(app)

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.webdav.webdav_service')
    async def test_manual_fix_returns_job_id(self, mock_service):
        job = WebdavManualFixJob(
            id="job123",
            status=WebdavJobStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
            target_dir="/data",
            dry_run=True,
            options={"execute_mode": False},
        )
        mock_service.submit_manual_fix = AsyncMock(return_value=job)

        response = self.client.post("/api/webdav/manual-fix", json={"path": "/data"})

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "job123"
        assert data["status"] == "queued"
        mock_service.submit_manual_fix.assert_called_once()

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.webdav.webdav_service')
    async def test_manual_fix_status_endpoint(self, mock_service):
        job = WebdavManualFixJob(
            id="job789",
            status=WebdavJobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            target_dir="/data",
            dry_run=False,
            result={"total_found": 3},
            options={"execute_mode": True},
        )
        mock_service.get_job = AsyncMock(return_value=job)

        response = self.client.get("/api/webdav/jobs/job789")

        assert response.status_code == 200
        payload = response.json()
        assert payload["job_id"] == "job789"
        assert payload["status"] == "completed"
        assert payload["result"]["total_found"] == 3

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.webdav.webdav_service')
    async def test_manual_fix_status_not_found(self, mock_service):
        mock_service.get_job = AsyncMock(return_value=None)

        response = self.client.get("/api/webdav/jobs/unknown")

        assert response.status_code == 404


class TestWebUIPages:
    """WebUI页面测试"""

    def setup_method(self):
        """测试前置设置"""
        self.client = TestClient(app)

    def test_root_page(self):
        """测试根页面"""
        response = self.client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_page(self):
        """测试仪表板页面"""
        response = self.client.get("/dashboard")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_logs_page(self):
        """测试日志页面"""
        response = self.client.get("/logs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_config_page(self):
        """测试配置页面"""
        response = self.client.get("/config")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestErrorHandling:
    """错误处理测试"""

    def setup_method(self):
        """测试前置设置"""
        self.client = TestClient(app)

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_system_service_error(self, mock_service):
        """测试系统服务错误处理"""
        mock_service.get_system_status.side_effect = Exception("Service unavailable")

        response = self.client.get("/api/system/status")

        assert response.status_code == 500

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.logs.log_service')
    async def test_logs_service_error(self, mock_service):
        """测试日志服务错误处理"""
        mock_service.get_log_files.side_effect = Exception("File system error")

        response = self.client.get("/api/logs/files")

        assert response.status_code == 500

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.config.config_service')
    async def test_config_service_error(self, mock_service):
        """测试配置服务错误处理"""
        mock_service.get_current_config.side_effect = Exception("Config file error")

        response = self.client.get("/api/config/current")

        assert response.status_code == 500

    def test_invalid_json_request(self):
        """测试无效JSON请求"""
        response = self.client.post(
            "/api/config/validate",
            content=b"invalid json",
            headers={"content-type": "application/json"}
        )

        assert response.status_code == 422

    def test_not_found_endpoint(self):
        """测试不存在的端点"""
        response = self.client.get("/api/nonexistent")

        assert response.status_code == 404


class TestAPIResponseFormat:
    """API响应格式测试"""

    def setup_method(self):
        """测试前置设置"""
        self.client = TestClient(app)

    @pytest.mark.asyncio
    @patch('alist_mikananirss.webui.api.system.system_service')
    async def test_response_headers(self, mock_service):
        """测试响应头"""
        mock_service.get_system_status.return_value = SystemStatus(
            status="running",
            uptime="1:00:00",
            cpu_usage=50.0,
            memory_usage=60.0,
            disk_usage=70.0,
            version="0.5.5"
        )

        response = self.client.get("/api/system/status")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_cors_headers(self):
        """测试CORS头"""
        response = self.client.options("/api/system/status")

        assert "access-control-allow-origin" in response.headers


# 测试数据工厂
def create_test_system_status():
    """创建测试用的系统状态数据"""
    return SystemStatus(
        status="running",
        uptime="5:30:15",
        cpu_usage=42.5,
        memory_usage=68.3,
        disk_usage=55.7,
        version="0.5.5"
    )


def create_test_log_entries():
    """创建测试用的日志条目"""
    return [
        LogEntry(
            timestamp="2025-10-10T10:00:00",
            level="INFO",
            message="Application started",
            module=None,
            line_number=None,
            thread_id=None,
        ),
        LogEntry(
            timestamp="2025-10-10T10:01:00",
            level="WARNING",
            message="High CPU usage detected",
            module=None,
            line_number=None,
            thread_id=None,
        ),
        LogEntry(
            timestamp="2025-10-10T10:02:00",
            level="ERROR",
            message="Failed to connect to database",
            module=None,
            line_number=None,
            thread_id=None,
        )
    ]


def create_test_config():
    """创建测试用的配置数据"""
    return {
        "common": {
            "interval_time": 300,
            "log_level": "INFO"
        },
        "alist": {
            "base_url": "http://localhost:5244",
            "token": "test-token",
            "downloader": "qBittorrent"
        },
        "mikan": {
            "subscribe_url": ["https://mikanani.me/RSS/MyBangumi?token=test"],
            "filters": ["非合集", "1080p"]
        }
    }
