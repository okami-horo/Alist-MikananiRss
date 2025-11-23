"""
WebUI数据模型定义

定义WebUI相关的数据模型和响应结构，使用Pydantic进行数据验证。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    ConfigDict,
    field_validator,
    field_serializer,
)


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemStatusEnum(str, Enum):
    """系统状态枚举"""
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"


class SystemStatus(BaseModel):
    """系统状态信息，用于API响应"""

    model_config = ConfigDict(extra="ignore")
    status: str = Field(..., description="当前状态，如 running/stopped")
    uptime: str = Field("0:00:00", description="运行时长，格式为 HH:MM:SS")
    cpu_usage: float = Field(0.0, ge=0, le=100, description="CPU使用率")
    memory_usage: float = Field(0.0, ge=0, le=100, description="内存使用率")
    disk_usage: float = Field(0.0, ge=0, le=100, description="磁盘使用率")
    version: Optional[str] = Field(None, description="应用版本号")
    process_info: Optional["ProcessInfo"] = Field(None, description="进程信息")
    last_error: Optional[str] = Field(None, description="最后错误信息")
    service_status: Optional[str] = Field(None, description="订阅服务状态别名")

    @field_validator("status")
    @classmethod
    def _normalise_status(cls, value: str) -> str:
        if not value:
            raise ValueError("status 不能为空")
        return value.lower()


class ProcessInfo(BaseModel):
    """进程信息"""
    pid: int = Field(..., description="进程ID")
    name: str = Field(..., description="进程名称")
    status: SystemStatusEnum = Field(..., description="进程状态")
    start_time: Optional[datetime] = Field(None, description="启动时间")
    cpu_percent: Optional[float] = Field(None, description="CPU使用率(%)")
    memory_mb: Optional[float] = Field(None, description="内存使用量(MB)")

    @field_serializer("start_time")
    def serialize_start_time(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


class SystemStatusInfo(BaseModel):
    """系统状态信息"""
    status: SystemStatusEnum = Field(..., description="系统状态")
    uptime: Optional[int] = Field(None, description="运行时间(秒)")
    version: str = Field(..., description="应用版本")
    python_version: str = Field(..., description="Python版本")
    process_info: Optional[ProcessInfo] = Field(None, description="进程信息")
    last_error: Optional[str] = Field(None, description="最后错误信息")

    model_config = ConfigDict()


class LogFileInfo(BaseModel):
    """日志文件信息"""
    name: str = Field(..., description="文件名")
    path: str = Field(..., description="文件路径")
    size: int = Field(..., description="文件大小(字节)")
    modified_time: str = Field(..., description="修改时间ISO格式")
    log_level: Optional[str] = Field(None, description="主要日志级别")

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: int) -> int:
        """验证文件大小"""
        if v < 0:
            raise ValueError("文件大小不能为负数")
        return v


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: str = Field(..., description="日志时间ISO格式")
    level: str = Field(..., description="日志级别")
    message: str = Field(..., description="日志消息")
    module: Optional[str] = Field(None, description="模块名称")
    line_number: Optional[int] = Field(None, description="行号")
    thread_id: Optional[str] = Field(None, description="线程ID")

    @field_validator("level")
    @classmethod
    def normalise_level(cls, value: str) -> str:
        if not value:
            return "INFO"
        return value.upper()


class LogFilter(BaseModel):
    """日志过滤器"""
    levels: List[LogLevel] = Field(default_factory=list, description="日志级别过滤")
    keywords: List[str] = Field(default_factory=list, description="关键词过滤")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    module: Optional[str] = Field(None, description="模块过滤")

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: Optional[datetime], info: ValidationInfo) -> Optional[datetime]:
        """验证时间范围"""
        start_time = info.data.get("start_time") if info else None
        if start_time and v and start_time >= v:
            raise ValueError("结束时间必须大于开始时间")
        return v


class WebdavJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WebdavManualFixJob(BaseModel):
    id: str
    status: WebdavJobStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    target_dir: Optional[str] = None
    dry_run: Optional[bool] = None
    options: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None

    @field_serializer("created_at", "started_at", "finished_at")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


class ConfigValidationResult(BaseModel):
    """配置验证结果"""
    valid: bool = Field(..., description="是否有效")
    errors: List[str] = Field(default_factory=list, description="错误信息")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    field_errors: Dict[str, List[str]] = Field(default_factory=dict, description="字段错误")

    def add_error(self, field: str, error: str) -> None:
        """添加字段错误"""
        if field not in self.field_errors:
            self.field_errors[field] = []
        self.field_errors[field].append(error)
        self.valid = False

    def add_general_error(self, error: str) -> None:
        """添加一般错误"""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str) -> None:
        """添加警告"""
        self.warnings.append(warning)


class ConfigValidationError(Exception):
    """配置验证异常，用于在验证失败时提供详细信息"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """将错误信息转换为字典"""
        return {"message": self.message, "details": self.details}


class ConfigSection(BaseModel):
    """配置段落"""
    key: str = Field(..., description="配置键")
    title: str = Field(..., description="配置标题")
    description: Optional[str] = Field(None, description="配置描述")
    type: str = Field(..., description="配置类型")
    default: Any = Field(None, description="默认值")
    current: Any = Field(None, description="当前值")
    required: bool = Field(default=False, description="是否必需")
    editable: bool = Field(default=True, description="是否可编辑")
    options: Optional[List[Dict[str, Any]]] = Field(None, description="选项列表")
    validation: Optional[Dict[str, Any]] = Field(None, description="验证规则")


class ConfigGroup(BaseModel):
    """配置组"""
    name: str = Field(..., description="组名")
    title: str = Field(..., description="组标题")
    description: Optional[str] = Field(None, description="组描述")
    sections: List[ConfigSection] = Field(default_factory=list, description="配置段落")
    collapsed: bool = Field(default=False, description="是否折叠")


class ConfigItem(BaseModel):
    """单独的配置项，常用于测试或界面展示"""

    key: str = Field(..., description="配置键")
    value: Any = Field(..., description="配置值")
    type: str = Field(default="string", description="配置类型")
    description: Optional[str] = Field(None, description="配置说明")
    required: bool = Field(default=False, description="是否必填")


class ApiResponse(BaseModel):
    """API响应基类"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")

    model_config = ConfigDict()

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class PaginatedResponse(ApiResponse):
    """分页响应"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    pages: int = Field(..., description="总页数")

    @classmethod
    def create(
        cls,
        success: bool,
        message: str,
        data: Optional[List[Any]] = None,
        total: int = 0,
        page: int = 1,
        page_size: int = 10,
        **kwargs
    ) -> "PaginatedResponse":
        """创建分页响应"""
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            success=success,
            message=message,
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            **kwargs
        )


class OperationResult(BaseModel):
    """操作结果"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作消息")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")
    error_code: Optional[str] = Field(None, description="错误代码")


class WebUIConfig(BaseModel):
    """WebUI配置"""
    model_config = ConfigDict(extra="ignore")
    host: str = Field(default="127.0.0.1", description="服务器地址")
    port: int = Field(default=8080, ge=1, le=65535, description="服务器端口")
    debug: bool = Field(default=False, description="调试模式")
    secret_key: str = Field(default="dev-secret-key", description="密钥")
    session_timeout: int = Field(default=3600, ge=300, description="会话超时时间（秒）")
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:8080", "http://localhost:8080"],
        description="CORS允许源"
    )
    allowed_hosts: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"], description="受信任主机")
    auth_enabled: bool = Field(default=True, description="是否启用内置鉴权")
    auth_header: str = Field(default="X-API-Key", description="鉴权Header名称")
    auto_start_monitor: bool = Field(default=True, description="是否随WebUI自动启动订阅服务")
    static_files: bool = Field(default=True, description="是否提供静态文件")
    use_cdn_assets: bool = Field(default=False, description="是否使用CDN加载前端资源")
    auto_open_browser: bool = Field(default=False, description="是否自动打开浏览器")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """验证端口"""
        if v < 1 or v > 65535:
            raise ValueError("端口必须在1-65535范围内")
        return v


class ThemeConfig(BaseModel):
    """主题配置"""
    name: str = Field(default="default", description="主题名称")
    primary_color: str = Field(default="#007bff", description="主色调")
    dark_mode: bool = Field(default=False, description="深色模式")
    font_size: str = Field(default="medium", pattern="^(small|medium|large)$", description="字体大小")

    @field_validator("primary_color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """验证颜色格式"""
        if not v.startswith("#") or len(v) != 7:
            raise ValueError("颜色必须是十六进制格式，如 #ffffff")
        return v
