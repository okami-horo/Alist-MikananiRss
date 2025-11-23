"""
WebUI服务类单元测试

测试WebUI的服务类功能，包括系统服务、日志服务和配置服务。
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from datetime import datetime, timezone
import tempfile
import os

from alist_mikananirss.webui.services.system_service import SystemService
from alist_mikananirss.webui.services.log_service import LogService
from alist_mikananirss.webui.services.config_service import ConfigService
from alist_mikananirss.webui.services.webdav_service import WebDAVService
from alist_mikananirss.webui.models import (
    SystemStatus,
    LogEntry,
    LogFileInfo,
    ConfigValidationError,
    WebdavJobStatus,
)


class TestSystemService:
    """系统服务测试"""

    @pytest.fixture
    def system_service(self):
        """创建系统服务实例"""
        return SystemService()

    @pytest.mark.asyncio
    async def test_get_system_status_running(self, system_service):
        """测试获取运行中的系统状态"""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:

            # 模拟系统资源使用情况
            mock_cpu.return_value = 25.5
            mock_memory.return_value = MagicMock(percent=60.2)
            mock_disk.return_value = MagicMock(percent=45.8)

            # 模拟进程存在
            with patch.object(system_service, '_is_main_process_running', return_value=True):

                status = await system_service.get_system_status()

                assert isinstance(status, SystemStatus)
                assert status.status == "running"
                assert status.cpu_usage == 25.5
                assert status.memory_usage == 60.2
                assert status.disk_usage == 45.8
                assert status.version == "0.5.5"

    @pytest.mark.asyncio
    async def test_get_system_status_stopped(self, system_service):
        """测试获取停止状态"""
        with patch.object(system_service, '_is_main_process_running', return_value=False):

            status = await system_service.get_system_status()

            assert status.status == "stopped"
            assert status.uptime == "0:00:00"

    @pytest.mark.asyncio
    async def test_get_system_status_recovers_invalid_pid_file(self, tmp_path, monkeypatch, system_service):
        """损坏的PID文件不会阻塞状态查询"""
        bad_pid = tmp_path / "alist.pid"
        bad_pid.write_text("not-a-pid", encoding="utf-8")
        import importlib

        system_module = importlib.import_module("alist_mikananirss.webui.services.system_service")
        monkeypatch.setattr(system_module, "PID_FILE", bad_pid)

        with patch.object(system_service, "_matches_target_process", return_value=False):
            status = await system_service.get_system_status()

        assert status.status == "stopped"
        assert not bad_pid.exists()

    @pytest.mark.asyncio
    async def test_start_system(self, system_service):
        """测试启动系统"""
        with patch('subprocess.Popen') as mock_popen, \
             patch.object(system_service, '_is_main_process_running', return_value=False):

            mock_process = MagicMock()
            mock_process.pid = 1234
            mock_popen.return_value = mock_process

            result = await system_service.start_system()

            assert result["success"] is True
            assert "started" in result["message"].lower()
            mock_popen.assert_called_once()
            assert system_service._managed_pid == 1234

    @pytest.mark.asyncio
    async def test_start_system_already_running(self, system_service):
        """测试启动已运行的系统"""
        with patch.object(system_service, '_is_main_process_running', return_value=True):

            result = await system_service.start_system()

            assert result["success"] is False
            assert "already running" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_stop_system(self, system_service):
        """测试停止系统"""
        mock_process = MagicMock()
        mock_process.pid = 4567
        system_service._managed_pid = mock_process.pid

        with patch.object(system_service, '_get_main_process', return_value=mock_process), \
             patch.object(system_service, '_is_main_process_running', return_value=True):

            result = await system_service.stop_system()

            assert result["success"] is True
            assert "stopped" in result["message"].lower()
            assert system_service._managed_pid is None

    @pytest.mark.asyncio
    async def test_stop_system_not_running(self, system_service):
        """测试停止未运行的系统"""
        with patch.object(system_service, '_is_main_process_running', return_value=False):

            result = await system_service.stop_system()

            assert result["success"] is False
            assert "not running" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_restart_system(self, system_service):
        """测试重启系统"""
        with patch.object(system_service, 'stop_system') as mock_stop, \
             patch.object(system_service, 'start_system') as mock_start, \
             patch.object(system_service, '_is_main_process_running', return_value=True):

            mock_stop.return_value = {"success": True}
            mock_start.return_value = {"success": True}

            result = await system_service.restart_system()

            assert result["success"] is True
            assert "restarted" in result["message"].lower()
            mock_stop.assert_called_once()
            mock_start.assert_called_once()

    def test_is_main_process_running_true(self, system_service):
        """测试检查主进程运行状态（运行中）"""
        with patch('psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.cmdline.return_value = ["python", "-m", "alist_mikananirss"]
            mock_iter.return_value = [mock_process]

            result = system_service._is_main_process_running()

            assert result is True

    def test_is_main_process_running_false(self, system_service):
        """测试检查主进程运行状态（未运行）"""
        with patch('psutil.process_iter') as mock_iter:
            mock_iter.return_value = []

            result = system_service._is_main_process_running()

            assert result is False

    def test_is_main_process_running_skips_webui(self, system_service):
        """测试检查主进程时跳过WebUI进程"""
        with patch('psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.cmdline.return_value = [
                "python",
                "-m",
                "src.alist_mikananirss.webui.server"
            ]
            mock_iter.return_value = [mock_process]

            result = system_service._is_main_process_running()

            assert result is False

    def test_calculate_uptime(self, system_service):
        """测试计算运行时间"""
        now = datetime.now(timezone.utc)
        start_time = now.replace(hour=8, minute=0, second=0)

        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = now.replace(hour=10, minute=30, second=15)

            uptime = system_service._calculate_uptime(start_time)

            assert uptime == "2:30:15"


class TestLogService:
    """日志服务测试"""

    @pytest.fixture
    def log_service(self):
        """创建日志服务实例"""
        return LogService()

    @pytest.fixture
    def sample_log_file(self):
        """创建示例日志文件"""
        content = """2025-10-10 10:00:00 | INFO     | Application started
2025-10-10 10:01:00 | WARNING  | High memory usage
2025-10-10 10:02:00 | ERROR    | Connection failed
2025-10-10 10:03:00 | INFO     | Retrying connection
2025-10-10 10:04:00 | INFO     | Connection established"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_file = f.name

        yield temp_file

        # 清理
        os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_get_log_files(self, log_service):
        """测试获取日志文件列表"""
        with patch('pathlib.Path.glob') as mock_glob:
            mock_file1 = MagicMock()
            mock_file1.name = "app.log"
            mock_file1.stat.return_value.st_size = 1024000
            mock_file1.stat.return_value.st_mtime = 1696934400  # 2025-10-10 10:00:00

            mock_file2 = MagicMock()
            mock_file2.name = "error.log"
            mock_file2.stat.return_value.st_size = 512000
            mock_file2.stat.return_value.st_mtime = 1696930800  # 2025-10-10 09:00:00

            mock_glob.return_value = [mock_file1, mock_file2]

            with patch.object(log_service, 'log_dir', Path('/mock/logs')):
                files = await log_service.get_log_files()

                assert len(files) == 2
                assert files[0].name == "app.log"
                assert files[0].size == 1024000
                assert files[1].name == "error.log"

    @pytest.mark.asyncio
    async def test_get_log_content(self, log_service, sample_log_file):
        """测试获取日志内容"""
        with patch.object(log_service, 'log_dir', Path(tempfile.gettempdir())):
            with patch('pathlib.Path.is_file', return_value=True):
                content = await log_service.get_log_content(
                    os.path.basename(sample_log_file),
                    limit=100,
                    offset=0
                )

                assert len(content["entries"]) == 5
                assert content["total"] == 5
                assert content["entries"][0]["level"] == "INFO"
                assert content["entries"][1]["level"] == "WARNING"
                assert content["entries"][2]["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_get_log_content_with_filter(self, log_service, sample_log_file):
        """测试获取过滤后的日志内容"""
        with patch.object(log_service, 'log_dir', Path(tempfile.gettempdir())):
            with patch('pathlib.Path.is_file', return_value=True):
                content = await log_service.get_log_content(
                    os.path.basename(sample_log_file),
                    level="INFO",
                    limit=100,
                    offset=0
                )

                assert len(content["entries"]) == 3  # 只有INFO级别的日志
                for entry in content["entries"]:
                    assert entry["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_get_log_content_with_search(self, log_service, sample_log_file):
        """测试搜索日志内容"""
        with patch.object(log_service, 'log_dir', Path(tempfile.gettempdir())):
            with patch('pathlib.Path.is_file', return_value=True):
                content = await log_service.get_log_content(
                    os.path.basename(sample_log_file),
                    search="connection",
                    limit=100,
                    offset=0
                )

                assert len(content["entries"]) == 3  # 包含"connection"的日志
                for entry in content["entries"]:
                    assert "connection" in entry["message"].lower()

    @pytest.mark.asyncio
    async def test_get_log_content_respects_offset_and_limit(self, log_service, sample_log_file):
        """支持分页参数并返回 has_more 状态"""
        with patch.object(log_service, 'log_dir', Path(tempfile.gettempdir())):
            with patch('pathlib.Path.is_file', return_value=True):
                content = await log_service.get_log_content(
                    os.path.basename(sample_log_file),
                    limit=2,
                    offset=1,
                )

                assert content["total"] == 5
                assert len(content["entries"]) == 2
                assert content["has_more"] is True

    @pytest.mark.asyncio
    async def test_get_log_content_missing_file(self, log_service):
        """缺少日志文件时返回清晰错误"""
        with patch.object(log_service, 'log_dir', Path('/non-existent')):
            with pytest.raises(FileNotFoundError) as excinfo:
                await log_service.get_log_content("missing.log")

        assert "missing.log" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_stream_log_entries(self, tmp_path):
        """测试实时日志流功能"""
        log_dir = tmp_path
        log_file = log_dir / "stream.log"
        log_file.write_text("")

        service = LogService(log_dir=str(log_dir))

        async def append_line():
            await asyncio.sleep(0.05)
            line = "2025-10-10T10:00:00 | INFO | Tail message generated"
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

        producer = asyncio.create_task(append_line())
        stream = service.stream_log_entries(log_file.name, poll_interval=0.01)

        entry = await asyncio.wait_for(anext(stream), timeout=1.0)

        await stream.aclose()
        await producer

        assert entry.level == "INFO"
        assert "Tail message" in entry.message

    @pytest.mark.asyncio
    async def test_get_recent_logs(self, log_service, sample_log_file):
        """测试获取最近日志"""
        with patch.object(log_service, 'log_dir', Path(tempfile.gettempdir())):
            with patch('pathlib.Path.is_file', return_value=True):
                logs = await log_service.get_recent_logs(limit=3)

                assert len(logs) == 3
                # 检查是否按时间倒序排列（最新的在前）
                timestamps = [log["timestamp"] for log in logs]
                assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_recent_logs_aggregates_multiple_files(self, tmp_path):
        """最近日志聚合多个文件并按时间排序"""
        file1 = tmp_path / "old.log"
        file2 = tmp_path / "new.log"
        file1.write_text(
            "2024-01-01 00:00:00 | INFO | old message\n"
            "2024-01-01 00:01:00 | ERROR | another old message\n",
            encoding="utf-8",
        )
        file2.write_text(
            "2025-02-02 10:00:00 | INFO | newer message\n",
            encoding="utf-8",
        )

        service = LogService(log_dir=str(tmp_path))
        logs = await service.get_recent_logs(limit=3)

        timestamps = [item["timestamp"] for item in logs]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_search_logs(self, log_service, sample_log_file):
        """测试搜索日志"""
        with patch.object(log_service, 'log_dir', Path(tempfile.gettempdir())):
            with patch('pathlib.Path.is_file', return_value=True):
                results = await log_service.search_logs("ERROR", limit=10)

                assert len(results["entries"]) == 1
                assert results["entries"][0]["level"] == "ERROR"
                assert "Connection failed" in results["entries"][0]["message"]

    @pytest.mark.asyncio
    async def test_get_log_file_not_found(self, log_service):
        """测试获取不存在的日志文件"""
        with patch('pathlib.Path.is_file', return_value=False):
            with pytest.raises(FileNotFoundError):
                await log_service.get_log_content("nonexistent.log")

    def test_parse_log_line(self, log_service):
        """测试解析日志行"""
        line = "2025-10-10 10:00:00 | INFO     | Application started"

        entry = log_service._parse_log_line(line)

        assert isinstance(entry, LogEntry)
        assert entry.level == "INFO"
        assert entry.message == "Application started"
        assert entry.timestamp == "2025-10-10T10:00:00"

    def test_parse_log_line_invalid(self, log_service):
        """测试解析无效日志行"""
        line = "invalid log line"

        entry = log_service._parse_log_line(line)

        assert entry is None

    def test_get_log_file_path(self, log_service):
        """测试获取日志文件路径"""
        with patch.object(log_service, 'log_dir', Path('/mock/logs')):
            path = log_service._get_log_file_path("app.log")

            assert path == Path('/mock/logs/app.log')


class TestConfigService:
    """配置服务测试"""

    @pytest.fixture
    def config_service(self):
        """创建配置服务实例"""
        return ConfigService()

    @pytest.fixture
    def sample_config_file(self):
        """创建示例配置文件"""
        config = {
            "common": {
                "interval_time": 300,
                "log_level": "INFO"
            },
            "alist": {
                "base_url": "http://localhost:5244",
                "token": "test-token",
                "downloader": "qBittorrent"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config, f)
            temp_file = f.name

        yield temp_file

        # 清理
        os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_get_current_config(self, config_service, sample_config_file):
        """测试获取当前配置"""
        with patch.object(config_service, 'config_file', Path(sample_config_file)):
            config = await config_service.get_current_config()

            assert "common" in config
            assert "alist" in config
            assert config["common"]["interval_time"] == 300
            assert config["alist"]["base_url"] == "http://localhost:5244"

    @pytest.mark.asyncio
    async def test_get_current_config_recovers_corrupted_file(self, tmp_path, config_service, monkeypatch):
        """损坏的配置文件会自动备份并回退到默认配置"""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("::invalid::yaml", encoding="utf-8")
        monkeypatch.setattr(config_service, "config_file", cfg_path)

        config = await config_service.get_current_config()

        meta = config.get("_meta", {})
        assert meta.get("needs_setup") is True
        assert meta.get("recovered_from_error") is True
        backup_path = cfg_path.with_suffix(".yaml.backup")
        assert backup_path.exists()

    @pytest.mark.asyncio
    async def test_validate_config_valid(self, config_service):
        """测试验证有效配置"""
        valid_config = {
            "common": {
                "interval_time": 300,
                "log_level": "INFO"
            },
            "alist": {
                "base_url": "http://localhost:5244",
                "token": "test-token"
            }
        }

        result = await config_service.validate_config(valid_config)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_config_invalid(self, config_service):
        """测试验证无效配置"""
        invalid_config = {
            "common": {
                "interval_time": -1,  # 无效值
                "log_level": "INVALID"  # 无效值
            },
            "alist": {
                "base_url": "invalid-url"  # 无效URL
            }
        }

        result = await config_service.validate_config(invalid_config)

        assert result["valid"] is False
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validate_config_missing_required(self, config_service):
        """测试验证缺少必需字段的配置"""
        incomplete_config = {
            "common": {
                "interval_time": 300
                # 缺少 log_level
            }
            # 缺少 alist 配置
        }

        result = await config_service.validate_config(incomplete_config)

        assert result["valid"] is False
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_save_config(self, config_service):
        """测试保存配置"""
        test_config = {
            "common": {
                "interval_time": 600,
                "log_level": "DEBUG"
            },
            "alist": {
                "base_url": "http://localhost:5244",
                "token": "token",
                "download_path": "/downloads"
            },
            "mikan": {
                "subscribe_url": ["https://example.com/rss"]
            }
        }

        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            temp_file = f.name

        try:
            with patch.object(config_service, 'config_file', Path(temp_file)):
                result = await config_service.save_config(test_config)

                assert result["success"] is True

                # 验证文件已保存
                with open(temp_file, 'r') as f:
                    import yaml
                    saved_config = yaml.safe_load(f)
                    assert saved_config["common"]["interval_time"] == 600
                    assert saved_config["common"]["log_level"] == "DEBUG"
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_save_config_backup(self, config_service):
        """测试保存配置时创建备份"""
        test_config = {
            "common": {"interval_time": 600, "log_level": "INFO"},
            "alist": {
                "base_url": "http://localhost:5244",
                "token": "token",
                "download_path": "/downloads",
            },
            "mikan": {
                "subscribe_url": ["https://example.com/rss"],
            },
        }

        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            temp_file = f.name

        backup_file = temp_file + '.backup'

        try:
            # 创建原始配置文件
            with open(temp_file, 'w') as f:
                import yaml
                yaml.dump({"common": {"interval_time": 300}}, f)

            with patch.object(config_service, 'config_file', Path(temp_file)):
                result = await config_service.save_config(test_config)

                assert result["success"] is True
                assert os.path.exists(backup_file)  # 备份文件应该存在
        finally:
            for file in [temp_file, backup_file]:
                if os.path.exists(file):
                    os.unlink(file)

    @pytest.mark.asyncio
    async def test_get_config_schema(self, config_service):
        """测试获取配置模式"""
        schema = await config_service.get_config_schema()

        assert "common" in schema
        assert "alist" in schema
        assert "interval_time" in schema["common"]
        assert "type" in schema["common"]["interval_time"]

    @pytest.mark.asyncio
    async def test_test_config_connections(self, config_service):
        """测试配置连接"""
        test_config = {
            "alist": {
                "base_url": "http://localhost:5244",
                "token": "test-token",
                "download_path": "/downloads",
            },
            "mikan": {
                "subscribe_url": ["https://mikanani.me/RSS/MyBangumi?token=test"]
            }
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟成功连接
            mock_response = MagicMock()
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response

            results = await config_service.test_config(test_config)

            assert results["success"] is True
            assert "alist" in results["results"]
            assert "mikan" in results["results"]

    @pytest.mark.asyncio
    async def test_test_config_connection_failure(self, config_service):
        """测试配置连接失败"""
        test_config = {
            "alist": {
                "base_url": "http://invalid-url:9999",
                "token": "test-token",
                "download_path": "/downloads",
            }
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟连接失败
            import aiohttp
            mock_get.side_effect = aiohttp.ClientError("Connection failed")

            results = await config_service.test_config(test_config)

            assert results["success"] is False
            assert "alist" in results["results"]
            assert results["results"]["alist"]["status"] == "error"

    def test_validate_url(self, config_service):
        """测试URL验证"""
        assert config_service._validate_url("http://localhost:5244") is True
        assert config_service._validate_url("https://example.com") is True
        assert config_service._validate_url("invalid-url") is False
        assert config_service._validate_url("") is False

    def test_validate_log_level(self, config_service):
        """测试日志级别验证"""
        assert config_service._validate_log_level("DEBUG") is True
        assert config_service._validate_log_level("INFO") is True
        assert config_service._validate_log_level("WARNING") is True
        assert config_service._validate_log_level("ERROR") is True
        assert config_service._validate_log_level("INVALID") is False

    def test_validate_interval_time(self, config_service):
        """测试间隔时间验证"""
        assert config_service._validate_interval_time(300) is True
        assert config_service._validate_interval_time(60) is True  # 最小值
        assert config_service._validate_interval_time(59) is False  # 小于最小值
        assert config_service._validate_interval_time(-1) is False  # 负数


class TestServiceIntegration:
    """服务集成测试"""

    @pytest.mark.asyncio
    async def test_system_and_config_integration(self):
        """测试系统服务和配置服务集成"""
        system_service = SystemService()
        config_service = ConfigService()

        with patch.object(system_service, '_is_main_process_running', return_value=True), \
             patch.object(config_service, 'get_current_config') as mock_get_config:

            mock_get_config.return_value = {
                "common": {"interval_time": 300},
                "alist": {"base_url": "http://localhost:5244"}
            }

            # 获取系统状态
            status = await system_service.get_system_status()

            # 获取配置
            config = await config_service.get_current_config()

            assert status.status == "running"
            assert config["common"]["interval_time"] == 300

    @pytest.mark.asyncio
    async def test_log_and_system_integration(self):
        """测试日志服务和系统服务集成"""
        log_service = LogService()
        system_service = SystemService()

        with patch.object(log_service, 'get_recent_logs') as mock_logs, \
             patch.object(system_service, 'get_system_status') as mock_status:

            mock_logs.return_value = [
                {
                    "timestamp": "2025-10-10T10:00:00",
                    "level": "INFO",
                    "message": "System started",
                    "module": None,
                    "line_number": None,
                    "thread_id": None
                }
            ]

            mock_status.return_value = SystemStatus(
                status="running",
                uptime="1:00:00",
                cpu_usage=50.0,
                memory_usage=60.0,
                disk_usage=70.0,
                version="0.5.5"
            )

            # 获取系统状态
            status = await system_service.get_system_status()

            # 获取最近日志
            logs = await log_service.get_recent_logs(limit=10)

            assert status.status == "running"
            assert len(logs) == 1
            assert logs[0]["level"] == "INFO"


class TestWebDAVService:
    """WebDAV 手动修复服务测试"""

    def _minimal_config(self) -> dict:
        return {
            "common": {"interval_time": 300, "log_level": "INFO"},
            "alist": {
                "base_url": "http://127.0.0.1:5244",
                "token": "token",
                "downloader": "qBittorrent",
                "download_path": "/downloads",
                "convert_torrent_to_magnet": False,
            },
            "mikan": {"subscribe_url": ["https://example.com/rss"], "filters": [], "regex_pattern": {}},
            "webdav": {
                "username": "admin",
                "password": "1234",
                "manual": {
                    "enable": True,
                    "default_path": "/downloads",
                    "execute_mode": False,
                    "recursive_scan": True,
                    "conflict_strategy": "skip",
                },
            },
        }

    @pytest.mark.asyncio
    async def test_submit_manual_fix_creates_job_and_updates_status(self, monkeypatch):
        """提交手动修复任务会生成 Job 并在执行后完成"""
        service = WebDAVService()
        monkeypatch.setattr(
            "alist_mikananirss.webui.services.webdav_service.config_service.get_current_config",
            AsyncMock(return_value=self._minimal_config()),
        )

        async def fake_execute(**_kwargs):
            return {
                "success": True,
                "message": "ok",
                "target_dir": "/data",
                "dry_run": True,
                "options": {"execute_mode": False, "recursive_scan": True, "conflict_strategy": "skip"},
                "result": {"total_found": 2},
            }

        monkeypatch.setattr(service, "_execute_manual_fix", AsyncMock(side_effect=fake_execute))

        job = await service.submit_manual_fix(path="/data")
        assert job.status == WebdavJobStatus.QUEUED

        await asyncio.sleep(0.05)
        stored = await service.get_job(job.id)
        assert stored is not None
        assert stored.status == WebdavJobStatus.COMPLETED
        assert stored.result["total_found"] == 2

    @pytest.mark.asyncio
    async def test_submit_manual_fix_disallowed_when_disabled(self, monkeypatch):
        """配置禁用时直接报错"""
        cfg = self._minimal_config()
        cfg["webdav"]["manual"]["enable"] = False
        monkeypatch.setattr(
            "alist_mikananirss.webui.services.webdav_service.config_service.get_current_config",
            AsyncMock(return_value=cfg),
        )

        service = WebDAVService()
        with pytest.raises(ValueError):
            await service.submit_manual_fix(path="/data")

    @pytest.mark.asyncio
    async def test_submit_manual_fix_failure_marks_job_failed(self, monkeypatch):
        """执行异常时 Job 标记为失败并记录错误"""
        monkeypatch.setattr(
            "alist_mikananirss.webui.services.webdav_service.config_service.get_current_config",
            AsyncMock(return_value=self._minimal_config()),
        )
        service = WebDAVService()
        monkeypatch.setattr(service, "_execute_manual_fix", AsyncMock(side_effect=RuntimeError("boom")))

        job = await service.submit_manual_fix(path="/data")
        await asyncio.sleep(0.05)

        stored = await service.get_job(job.id)
        assert stored is not None
        assert stored.status == WebdavJobStatus.FAILED
        assert "boom" in (stored.error or "")


# 测试工具函数
def create_test_system_service():
    """创建测试用的系统服务"""
    service = SystemService()
    return service


def create_test_log_service():
    """创建测试用的日志服务"""
    service = LogService()
    return service


def create_test_config_service():
    """创建测试用的配置服务"""
    service = ConfigService()
    return service
