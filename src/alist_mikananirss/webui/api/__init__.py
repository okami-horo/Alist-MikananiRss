"""
WebUI API路由模块

提供RESTful API接口，包括：
- 系统控制和状态查询
- 日志查看和流式传输
- 配置管理和验证
"""

from .system import router as system_router
from .logs import router as logs_router
from .config import router as config_router

__all__ = [
    "system_router",
    "logs_router",
    "config_router",
]