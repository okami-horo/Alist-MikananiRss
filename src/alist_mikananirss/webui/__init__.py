"""
WebUI模块 - Alist-MikananiRss的Web用户界面

提供基于Web的用户界面，包括：
- 系统状态监控和控制
- 实时日志查看
- 可视化配置管理
- 多主题响应式界面

主要组件：
- models: 数据模型定义
- services: 业务逻辑服务层
- api: RESTful API接口
- templates: HTML模板文件
- static: 静态资源文件
"""

from .models import (
    SystemStatus,
    LogFileInfo,
    LogEntry,
    ConfigValidationResult,
    ApiResponse,
)

from .server import create_app

__all__ = [
    # 数据模型
    "SystemStatus",
    "LogFileInfo",
    "LogEntry",
    "ConfigValidationResult",
    "ApiResponse",
    # 服务器应用
    "create_app",
]

__version__ = "0.1.0"
__author__ = "Alist-MikananiRss Team"