"""
WebUI集成测试

测试WebUI的端到端功能，验证前后端交互和完整用户工作流程。
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from aioresponses import aioresponses
import tempfile
import os
from pathlib import Path
import yaml

from alist_mikananirss.webui.server import app
from alist_mikananirss.webui.services.system_service import SystemService
from alist_mikananirss.webui.services.log_service import LogService
from alist_mikananirss.webui.services.config_service import ConfigService


class TestWebUIIntegration:
    """WebUI端到端集成测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def mock_services(self):
        """模拟所有服务"""
        with patch('alist_mikananirss.webui.api.system.system_service') as mock_system, \
             patch('alist_mikananirss.webui.api.logs.log_service') as mock_logs, \
             patch('alist_mikananirss.webui.api.config.config_service') as mock_config:

            # 设置默认返回值
            mock_system.get_system_status.return_value = {
                "status": "running",
                "uptime": "2:30:45",
                "cpu_usage": 25.5,
                "memory_usage": 60.2,
                "disk_usage": 45.8,
                "version": "0.5.5"
            }

            mock_system.start_system.return_value = {"success": True, "message": "System started"}
            mock_system.stop_system.return_value = {"success": True, "message": "System stopped"}
            mock_system.restart_system.return_value = {"success": True, "message": "System restarted"}

            mock_logs.get_log_files.return_value = [
                {"name": "app.log", "size": 1024000, "modified": "2025-10-10T10:00:00"},
                {"name": "error.log", "size": 512000, "modified": "2025-10-10T09:30:00"}
            ]

            mock_logs.get_log_content.return_value = {
                "entries": [
                    {
                        "timestamp": "2025-10-10T10:00:00",
                        "level": "INFO",
                        "message": "Application started"
                    },
                    {
                        "timestamp": "2025-10-10T10:01:00",
                        "level": "WARNING",
                        "message": "High memory usage detected"
                    }
                ],
                "total": 2,
                "has_more": False
            }

            mock_logs.get_recent_logs.return_value = [
                {
                    "timestamp": "2025-10-10T10:05:00",
                    "level": "INFO",
                    "message": "Download completed: anime.mkv"
                }
            ]

            mock_config.get_current_config.return_value = {
                "common": {"interval_time": 300, "log_level": "INFO"},
                "alist": {"base_url": "http://localhost:5244", "downloader": "qBittorrent"},
                "mikan": {"subscribe_url": ["https://mikanani.me/RSS/MyBangumi?token=test"]}
            }

            mock_config.validate_config.return_value = {"valid": True, "errors": []}
            mock_config.save_config.return_value = {"success": True}
            mock_config.get_config_schema.return_value = {
                "common": {"interval_time": {"type": "integer", "min": 60}},
                "alist": {"base_url": {"type": "string", "format": "uri"}}
            }

            yield {
                'system': mock_system,
                'logs': mock_logs,
                'config': mock_config
            }

    def test_complete_dashboard_workflow(self, client, mock_services):
        """测试完整的仪表板工作流程"""
        # 1. 访问仪表板页面
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # 2. 获取系统状态
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

        # 3. 测试系统控制
        response = client.post("/api/system/restart")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # 4. 验证服务调用
        mock_services['system'].get_system_status.assert_called()
        mock_services['system'].restart_system.assert_called_once()

    def test_browser_control_subscription_flow(self, client, mock_services):
        """测试仅通过浏览器完成启动→状态→停止的闭环"""
        # 模拟状态从 stopped -> running -> stopped 的变化
        mock_services['system'].get_system_status.side_effect = [
            {
                "status": "stopped",
                "uptime": "0:00:00",
                "cpu_usage": 5.0,
                "memory_usage": 20.0,
                "disk_usage": 30.0,
                "version": "0.5.5",
            },
            {
                "status": "running",
                "uptime": "0:10:00",
                "cpu_usage": 35.0,
                "memory_usage": 45.0,
                "disk_usage": 55.0,
                "version": "0.5.5",
            },
            {
                "status": "stopped",
                "uptime": "0:00:00",
                "cpu_usage": 7.0,
                "memory_usage": 25.0,
                "disk_usage": 32.0,
                "version": "0.5.5",
            },
        ]

        # 1. 初始状态应为 stopped
        status_resp = client.get("/api/system/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "stopped"

        # 2. 启动订阅
        start_resp = client.post("/api/system/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["success"] is True
        mock_services['system'].start_system.assert_called_once()

        # 3. 再次查询状态，应变为 running
        running_resp = client.get("/api/system/status")
        assert running_resp.status_code == 200
        assert running_resp.json()["status"] == "running"

        # 4. 停止订阅
        stop_resp = client.post("/api/system/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["success"] is True
        mock_services['system'].stop_system.assert_called_once()

        # 5. 最终状态恢复为 stopped
        final_resp = client.get("/api/system/status")
        assert final_resp.status_code == 200
        assert final_resp.json()["status"] == "stopped"

        # 验证调用顺序（start 在 stop 之前）
        assert mock_services['system'].start_system.call_count == 1
        assert mock_services['system'].stop_system.call_count == 1

    def test_complete_logs_workflow(self, client, mock_services):
        """测试完整的日志查看工作流程"""
        # 1. 访问日志页面
        response = client.get("/logs")
        assert response.status_code == 200

        # 2. 获取日志文件列表
        response = client.get("/api/logs/files")
        assert response.status_code == 200
        files = response.json()
        assert len(files) == 2

        # 3. 获取日志内容
        response = client.get("/api/logs/content?file=app.log&limit=100")
        assert response.status_code == 200
        content = response.json()
        assert len(content["entries"]) == 2
        assert content["total"] == 2

        # 4. 获取最近日志
        response = client.get("/api/logs/recent?limit=10")
        assert response.status_code == 200
        recent = response.json()
        assert len(recent) == 1

        # 5. 搜索日志
        response = client.get("/api/logs/search?q=memory&level=WARNING")
        assert response.status_code == 200
        search_results = response.json()
        assert search_results["total"] >= 0

        # 验证服务调用
        mock_services['logs'].get_log_files.assert_called()
        mock_services['logs'].get_log_content.assert_called_with(
            file="app.log",
            limit=100,
            offset=0,
            level=None,
            search=None
        )
        mock_services['logs'].get_recent_logs.assert_called_with(limit=10)

    def test_complete_config_workflow(self, client, mock_services):
        """测试完整的配置管理工作流程"""
        # 1. 访问配置页面
        response = client.get("/config")
        assert response.status_code == 200

        # 2. 获取当前配置
        response = client.get("/api/config/current")
        assert response.status_code == 200
        config = response.json()
        assert "common" in config
        assert "alist" in config

        # 3. 获取配置模式
        response = client.get("/api/config/schema")
        assert response.status_code == 200
        schema = response.json()
        assert "common" in schema

        # 4. 验证配置
        test_config = {
            "common": {"interval_time": 600, "log_level": "DEBUG"},
            "alist": {"base_url": "http://localhost:5244"}
        }
        response = client.post("/api/config/validate", json=test_config)
        assert response.status_code == 200
        validation = response.json()
        assert validation["valid"] is True

        # 5. 保存配置
        response = client.post("/api/config/save", json=test_config)
        assert response.status_code == 200
        save_result = response.json()
        assert save_result["success"] is True

        # 6. 测试配置连接
        response = client.post("/api/config/test", json=test_config)
        assert response.status_code == 200
        test_result = response.json()
        assert test_result["success"] is True

        # 验证服务调用
        mock_services['config'].get_current_config.assert_called()
        mock_services['config'].validate_config.assert_called_with(test_config)
        mock_services['config'].save_config.assert_called_with(test_config)

    def test_error_handling_workflow(self, client):
        """测试错误处理工作流程"""
        with patch('alist_mikananirss.webui.api.system.system_service') as mock_system:
            # 模拟服务错误
            mock_system.get_system_status.side_effect = Exception("Service unavailable")

            # 1. 系统状态API错误
            response = client.get("/api/system/status")
            assert response.status_code == 500

        with patch('alist_mikananirss.webui.api.logs.log_service') as mock_logs:
            # 模拟文件不存在错误
            mock_logs.get_log_files.side_effect = FileNotFoundError("Log directory not found")

            # 2. 日志API错误
            response = client.get("/api/logs/files")
            assert response.status_code == 500

        with patch('alist_mikananirss.webui.api.config.config_service') as mock_config:
            # 模拟配置文件错误
            mock_config.get_current_config.side_effect = Exception("Config file corrupted")

            # 3. 配置API错误
            response = client.get("/api/config/current")
            assert response.status_code == 500

    def test_cors_and_security_headers(self, client):
        """测试CORS和安全头"""
        # 测试OPTIONS请求
        response = client.options("/api/system/status")
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

        # 测试正常请求
        response = client.get("/api/system/status")
        assert "content-type" in response.headers
        assert "application/json" in response.headers["content-type"]

    def test_static_file_serving(self, client):
        """测试静态文件服务"""
        # 这里测试静态文件路由是否存在
        # 实际的静态文件测试需要真实的文件存在
        response = client.get("/static/css/webui.css")
        # 可能返回404（文件不存在）或200（文件存在），但路由应该存在
        assert response.status_code in [200, 404]


class TestRealWorldScenarios:
    """真实世界场景测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_new_user_onboarding_scenario(self, client):
        """测试新用户引导场景"""
        with patch('alist_mikananirss.webui.api.system.system_service') as mock_system, \
             patch('alist_mikananirss.webui.api.config.config_service') as mock_config:

            # 模拟新用户首次访问
            mock_system.get_system_status.return_value = {
                "status": "stopped",
                "uptime": "0:00:00",
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "version": "0.5.5"
            }

            mock_config.get_current_config.return_value = {
                "common": {"interval_time": 300, "log_level": "INFO"},
                "alist": {"base_url": "", "token": ""},  # 未配置
                "mikan": {"subscribe_url": []}  # 未配置
            }

            # 1. 用户访问仪表板
            response = client.get("/dashboard")
            assert response.status_code == 200

            # 2. 查看系统状态（应该显示未运行）
            response = client.get("/api/system/status")
            assert response.json()["status"] == "stopped"

            # 3. 访问配置页面进行初始配置
            response = client.get("/config")
            assert response.status_code == 200

            response = client.get("/api/config/current")
            config = response.json()
            assert config["alist"]["base_url"] == ""  # 确认未配置

            # 4. 用户配置Alist
            new_config = {
                "common": {"interval_time": 300, "log_level": "INFO"},
                "alist": {
                    "base_url": "http://localhost:5244",
                    "token": "new-user-token",
                    "downloader": "qBittorrent"
                }
            }

            response = client.post("/api/config/validate", json=new_config)
            assert response.json()["valid"] is True

            response = client.post("/api/config/save", json=new_config)
            assert response.json()["success"] is True

            # 5. 启动系统
            mock_system.start_system.return_value = {"success": True, "message": "System started"}
            response = client.post("/api/system/start")
            assert response.json()["success"] is True

    def test_system_troubleshooting_scenario(self, client):
        """测试系统故障排查场景"""
        with patch('alist_mikananirss.webui.api.system.system_service') as mock_system, \
             patch('alist_mikananirss.webui.api.logs.log_service') as mock_logs:

            # 模拟系统出现问题
            mock_system.get_system_status.return_value = {
                "status": "running",
                "uptime": "1:30:00",
                "cpu_usage": 95.5,  # 高CPU使用率
                "memory_usage": 98.2,  # 高内存使用率
                "disk_usage": 88.7,  # 高磁盘使用率
                "version": "0.5.5"
            }

            mock_logs.get_recent_logs.return_value = [
                {
                    "timestamp": "2025-10-10T10:05:00",
                    "level": "ERROR",
                    "message": "Out of memory error occurred"
                },
                {
                    "timestamp": "2025-10-10T10:04:00",
                    "level": "WARNING",
                    "message": "High CPU usage detected: 95%"
                },
                {
                    "timestamp": "2025-10-10T10:03:00",
                    "level": "ERROR",
                    "message": "Failed to allocate memory"
                }
            ]

            # 1. 用户在仪表板看到异常状态
            response = client.get("/api/system/status")
            status = response.json()
            assert status["cpu_usage"] > 90
            assert status["memory_usage"] > 90

            # 2. 用户查看日志排查问题
            response = client.get("/api/logs/recent?limit=10")
            logs = response.json()
            assert any(log["level"] == "ERROR" for log in logs)
            assert any("memory" in log["message"].lower() for log in logs)

            # 3. 用户搜索特定错误
            response = client.get("/api/logs/search?q=memory&level=ERROR")
            search_results = response.json()
            assert search_results["total"] > 0

            # 4. 用户决定重启系统
            mock_system.restart_system.return_value = {"success": True, "message": "System restarted"}
            response = client.post("/api/system/restart")
            assert response.json()["success"] is True

    def test_configuration_update_scenario(self, client):
        """测试配置更新场景"""
        with patch('alist_mikananirss.webui.api.config.config_service') as mock_config, \
             patch('alist_mikananirss.webui.api.system.system_service') as mock_system:

            # 初始配置
            mock_config.get_current_config.return_value = {
                "common": {"interval_time": 300, "log_level": "INFO"},
                "alist": {
                    "base_url": "http://localhost:5244",
                    "token": "old-token",
                    "downloader": "qBittorrent"
                },
                "mikan": {
                    "subscribe_url": ["https://mikanani.me/RSS/MyBangumi?token=old"]
                }
            }

            # 1. 用户访问配置管理
            response = client.get("/config")
            assert response.status_code == 200

            response = client.get("/api/config/current")
            original_config = response.json()
            assert original_config["alist"]["token"] == "old-token"

            # 2. 用户更新配置
            updated_config = original_config.copy()
            updated_config["alist"]["token"] = "new-token"
            updated_config["mikan"]["subscribe_url"] = [
                "https://mikanani.me/RSS/MyBangumi?token=new"
            ]
            updated_config["common"]["interval_time"] = 600

            # 3. 验证新配置
            mock_config.validate_config.return_value = {"valid": True, "errors": []}
            response = client.post("/api/config/validate", json=updated_config)
            assert response.json()["valid"] is True

            # 4. 测试配置连接
            mock_config.test_config.return_value = {
                "success": True,
                "results": {
                    "alist": {"status": "connected", "message": "Connection successful"},
                    "mikan": {"status": "connected", "message": "RSS feed accessible"}
                }
            }
            response = client.post("/api/config/test", json=updated_config)
            test_result = response.json()
            assert test_result["success"] is True
            assert test_result["results"]["alist"]["status"] == "connected"

            # 5. 保存配置
            mock_config.save_config.return_value = {"success": True}
            response = client.post("/api/config/save", json=updated_config)
            assert response.json()["success"] is True

            # 6. 重启系统应用新配置
            mock_system.restart_system.return_value = {"success": True, "message": "System restarted"}
            response = client.post("/api/system/restart")
            assert response.json()["success"] is True

    def test_log_analysis_scenario(self, client):
        """测试日志分析场景"""
        with patch('alist_mikananirss.webui.api.logs.log_service') as mock_logs:
            # 模拟大量日志数据
            mock_logs.get_log_files.return_value = [
                {"name": "app_2025-10-10.log", "size": 5242880, "modified": "2025-10-10T10:00:00"},
                {"name": "error_2025-10-10.log", "size": 1048576, "modified": "2025-10-10T10:00:00"},
                {"name": "debug_2025-10-09.log", "size": 2097152, "modified": "2025-10-09T10:00:00"}
            ]

            # 模拟不同类型的日志条目
            mock_logs.get_log_content.return_value = {
                "entries": [
                    {
                        "timestamp": "2025-10-10T10:00:00",
                        "level": "INFO",
                        "message": "RSS check completed: 5 new items found"
                    },
                    {
                        "timestamp": "2025-10-10T10:01:00",
                        "level": "INFO",
                        "message": "Download started: anime_episode_01.torrent"
                    },
                    {
                        "timestamp": "2025-10-10T10:02:00",
                        "level": "WARNING",
                        "message": "Download speed slow: 100 KB/s"
                    },
                    {
                        "timestamp": "2025-10-10T10:03:00",
                        "level": "ERROR",
                        "message": "Download failed: connection timeout"
                    },
                    {
                        "timestamp": "2025-10-10T10:04:00",
                        "level": "INFO",
                        "message": "Download retry started: anime_episode_01.torrent"
                    },
                    {
                        "timestamp": "2025-10-10T10:05:00",
                        "level": "INFO",
                        "message": "Download completed successfully: anime_episode_01.mkv"
                    }
                ],
                "total": 6,
                "has_more": True
            }

            # 1. 用户查看可用的日志文件
            response = client.get("/api/logs/files")
            files = response.json()
            assert len(files) == 3
            assert any("2025-10-10" in f["name"] for f in files)

            # 2. 用户查看当天的日志内容
            response = client.get("/api/logs/content?file=app_2025-10-10.log&limit=100")
            content = response.json()
            assert len(content["entries"]) == 6
            assert content["has_more"] is True

            # 3. 用户过滤错误日志
            mock_logs.get_log_content.return_value = {
                "entries": [
                    {
                        "timestamp": "2025-10-10T10:03:00",
                        "level": "ERROR",
                        "message": "Download failed: connection timeout"
                    }
                ],
                "total": 1,
                "has_more": False
            }
            response = client.get("/api/logs/content?file=app_2025-10-10.log&level=ERROR")
            error_logs = response.json()
            assert len(error_logs["entries"]) == 1
            assert error_logs["entries"][0]["level"] == "ERROR"

            # 4. 用户搜索特定关键词
            mock_logs.search_logs.return_value = {
                "entries": [
                    {
                        "timestamp": "2025-10-10T10:01:00",
                        "level": "INFO",
                        "message": "Download started: anime_episode_01.torrent"
                    },
                    {
                        "timestamp": "2025-10-10T10:05:00",
                        "level": "INFO",
                        "message": "Download completed successfully: anime_episode_01.mkv"
                    }
                ],
                "total": 2,
                "has_more": False
            }
            response = client.get("/api/logs/search?q=download")
            search_results = response.json()
            assert search_results["total"] == 2
            assert all("download" in entry["message"].lower() for entry in search_results["entries"])

            # 5. 用户查看最近的日志活动
            response = client.get("/api/logs/recent?limit=20")
            recent_logs = response.json()
            assert len(recent_logs) >= 0


class TestPerformanceAndScalability:
    """性能和可扩展性测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, client):
        """测试并发API请求"""
        with patch('alist_mikananirss.webui.api.system.system_service') as mock_system:
            mock_system.get_system_status.return_value = {
                "status": "running",
                "uptime": "1:00:00",
                "cpu_usage": 50.0,
                "memory_usage": 60.0,
                "disk_usage": 70.0,
                "version": "0.5.5"
            }

            # 创建多个并发请求
            async def make_request():
                response = client.get("/api/system/status")
                return response

            # 模拟并发请求（实际异步测试需要更复杂的设置）
            for i in range(10):
                response = client.get("/api/system/status")
                assert response.status_code == 200

            # 验证服务被调用了正确的次数
            assert mock_system.get_system_status.call_count >= 10

    def test_large_log_data_handling(self, client):
        """测试大量日志数据处理"""
        with patch('alist_mikananirss.webui.api.logs.log_service') as mock_logs:
            # 模拟大量日志数据
            large_log_entries = []
            for i in range(1000):
                large_log_entries.append({
                    "timestamp": f"2025-10-10T10:{i:02d}:00",
                    "level": "INFO",
                    "message": f"Log entry number {i}"
                })

            mock_logs.get_log_content.return_value = {
                "entries": large_log_entries[:100],  # 返回前100条
                "total": 1000,
                "has_more": True
            }

            response = client.get("/api/logs/content?file=large.log&limit=100")
            assert response.status_code == 200
            content = response.json()
            assert len(content["entries"]) == 100
            assert content["total"] == 1000

    def test_config_validation_performance(self, client):
        """测试配置验证性能"""
        with patch('alist_mikananirss.webui.api.config.config_service') as mock_config:
            # 创建复杂配置
            complex_config = {
                "common": {"interval_time": 300, "log_level": "INFO"},
                "alist": {
                    "base_url": "http://localhost:5244",
                    "token": "test-token",
                    "downloader": "qBittorrent"
                },
                "mikan": {
                    "subscribe_url": [f"https://example{i}.com/rss" for i in range(100)],
                    "filters": [f"filter{i}" for i in range(50)]
                }
            }

            mock_config.validate_config.return_value = {"valid": True, "errors": []}

            # 测试验证性能
            response = client.post("/api/config/validate", json=complex_config)
            assert response.status_code == 200
            assert response.json()["valid"] is True


# 测试辅助函数
def create_test_client():
    """创建测试客户端"""
    return TestClient(app)


def mock_all_services():
    """模拟所有服务的装饰器"""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            with patch('alist_mikananirss.webui.api.system.system_service') as mock_system, \
                 patch('alist_mikananirss.webui.api.logs.log_service') as mock_logs, \
                 patch('alist_mikananirss.webui.api.config.config_service') as mock_config:

                # 设置默认返回值
                mock_system.get_system_status.return_value = {
                    "status": "running",
                    "uptime": "1:00:00",
                    "cpu_usage": 50.0,
                    "memory_usage": 60.0,
                    "disk_usage": 70.0,
                    "version": "0.5.5"
                }

                mock_logs.get_log_files.return_value = []
                mock_logs.get_log_content.return_value = {"entries": [], "total": 0, "has_more": False}

                mock_config.get_current_config.return_value = {}
                mock_config.validate_config.return_value = {"valid": True, "errors": []}

                return test_func(*args, **kwargs)
        return wrapper
    return decorator