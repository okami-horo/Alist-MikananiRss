from collections import defaultdict
from typing import Annotated, Dict, List

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from alist_mikananirss.alist import AlistDownloaderType

from .bot_assistant import TelegramBotAssistantConfig
from .extractor import ExtractorConfig
from .notifier import PushPlusConfig, TelegramConfig
from .remap import RemapConfig


class CommonConfig(BaseModel):
    interval_time: int = Field(
        default=300, ge=0, description="Interval time must be non-negative"
    )
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    proxies: Dict[str, str] = Field(
        default_factory=dict, description="Proxies for requests"
    )


class AlistConfig(BaseModel):
    base_url: str = Field(
        default="http://127.0.0.1:5244", description="Base URL of Alist"
    )
    token: str = Field(default="", description="Token for Alist API")
    downloader: AlistDownloaderType = Field(
        default=AlistDownloaderType.QBIT, description="Alist Downloader type"
    )
    download_path: str = Field(
        default="/downloads", description="Download path for Alist Downloader"
    )
    convert_torrent_to_magnet: bool = Field(
        default=False,
        description="Convert torrent files to magnet links before downloading",
    )

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, url: str) -> str:
        try:
            # 正确的URL验证方式
            parsed_url = HttpUrl(url)
            normalized = str(parsed_url).rstrip("/")
            return normalized
        except ValueError:
            raise ValueError(f"Invalid URL: {url}")


class MikanConfig(BaseModel):
    subscribe_url: List[str] = Field(
        default_factory=lambda: ["https://mikanani.me/RSS/"], min_length=1
    )
    regex_pattern: Dict[str, str] = Field(
        default_factory=dict,
        description="Regex pattern for filter",
    )

    filters: List[str] = Field(default_factory=list, description="Filters for rss")

    @field_validator("subscribe_url")
    @classmethod
    def validate_url(cls, url: List[str]) -> List[str]:
        for u in url:
            HttpUrl(u)
        return url

    @field_validator("regex_pattern")
    @classmethod
    def merge_regex_patterns(cls, patterns: Dict[str, str]) -> Dict[str, str]:
        default_patterns = {
            "简体": "(简体|简中|简日|CHS)",
            "繁体": "(繁体|繁中|繁日|CHT|Baha)",
            "1080p": "(X1080|1080P)",
            "非合集": "^(?!.*(\\d{2}-\\d{2}|合集)).*",
        }
        default_patterns.update(patterns)
        return default_patterns


class RenameConfig(BaseModel):
    enable: bool = Field(default=False)
    extractor: ExtractorConfig | None = Field(default=None)
    rename_format: str = Field(
        "{name} S{season:02d}E{episode:02d}", description="Rename format"
    )
    remap: RemapConfig = Field(
        default_factory=RemapConfig, description="Remap configuration"
    )

    @model_validator(mode="after")
    def validate_rename_config(self):
        if self.enable and not self.extractor:
            raise ValueError("Rename is enabled but no extractor config provided")
        return self

    @field_validator("rename_format")
    @classmethod
    def validate_rename_format(cls, rename_format: str) -> str:
        if not rename_format:
            return rename_format

        all_key_test_data = {
            "name": "test",
            "season": 1,
            "episode": 1,
            "fansub": "fansub",
            "quality": "1080p",
            "language": "简体中文",
        }
        safe_dict = defaultdict(lambda: "undefined", all_key_test_data)
        res = rename_format.format_map(safe_dict)
        if "undefined" in res:
            unknown_keys = [
                key for key, value in safe_dict.items() if value == "undefined"
            ]
            raise ValueError(f"Error keys in rename format: {', '.join(unknown_keys)}")
        return rename_format


NotificationBotConfig = Annotated[
    TelegramConfig | PushPlusConfig, Field(discriminator="bot_type")
]


class NotificationConfig(BaseModel):
    enable: bool = Field(default=False)
    interval_time: int = Field(
        default=300, ge=0, description="Interval time must be non-negative"
    )
    bots: List[NotificationBotConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_notification_config(self):
        if self.enable and not len(self.bots):
            raise ValueError("Notification is enabled but no notifier config provided")
        return self


class BotAssistantConfig(BaseModel):
    enable: bool = Field(default=False)
    bots: List[TelegramBotAssistantConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bot_assistant_config(self):
        if self.enable and len(self.bots) == 0:
            raise ValueError("Bot assistant is enabled but no bot config provided")
        return self


class WebdavFixerConfig(BaseModel):
    """WebDAV修复工具配置"""
    enable: bool = Field(
        default=False, description="是否启用WebDAV修复工具"
    )
    execute_mode: bool = Field(
        default=False, description="是否实际执行修复操作（false=仅预览）"
    )
    recursive_scan: bool = Field(
        default=True, description="是否递归扫描子目录"
    )
    conflict_strategy: str = Field(
        default="skip",
        pattern="^(skip|rename|overwrite)$",
        description="冲突处理策略"
    )


class WebdavManualFixConfig(BaseModel):
    """WebDAV手动修复配置"""
    enable: bool = Field(
        default=True, description="是否允许手动触发修复"
    )
    default_path: str | None = Field(
        default=None, description="手动修复的默认目标路径"
    )
    execute_mode: bool = Field(
        default=False, description="是否实际执行修复操作（false=仅预览）"
    )
    recursive_scan: bool = Field(
        default=True, description="是否递归扫描子目录"
    )
    conflict_strategy: str = Field(
        default="skip",
        pattern="^(skip|rename|overwrite)$",
        description="手动修复的冲突处理策略"
    )


class WebdavConfig(BaseModel):
    """WebDAV配置"""
    username: str = Field(default="admin", description="WebDAV用户名")
    password: str = Field(default="", description="WebDAV密码")
    timeout: int = Field(default=60, ge=1, le=600, description="WebDAV请求超时时间（秒）")
    fixer: WebdavFixerConfig = Field(
        default_factory=WebdavFixerConfig, description="WebDAV修复工具配置"
    )
    manual: WebdavManualFixConfig = Field(
        default_factory=WebdavManualFixConfig, description="WebDAV手动修复配置"
    )


class WebUIConfig(BaseModel):
    """WebUI配置"""
    enable: bool = Field(
        default=False, description="是否启用WebUI界面"
    )
    host: str = Field(
        default="0.0.0.0", description="WebUI服务器绑定地址"
    )
    port: int = Field(
        default=8080, ge=1, le=65535, description="WebUI服务器端口"
    )
    debug: bool = Field(
        default=False, description="是否启用调试模式"
    )
    secret_key: str = Field(
        default="alist-mikananirss-webui-secret-key",
        description="WebUI会话密钥"
    )
    session_timeout: int = Field(
        default=3600, ge=300, description="会话超时时间（秒）"
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:8080", "http://localhost:8080"],
        description="允许的跨域来源",
    )
    allowed_hosts: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"],
        description="允许的主机名",
    )
    auth_enabled: bool = Field(
        default=True, description="是否启用内置Header Token鉴权"
    )
    auth_header: str = Field(
        default="X-API-Key", description="用于鉴权的Header名称"
    )
    auto_start_monitor: bool = Field(
        default=True, description="WebUI启动时是否自动启动订阅服务"
    )
    use_cdn_assets: bool = Field(
        default=False, description="是否使用CDN加载前端资源"
    )
    auto_open_browser: bool = Field(
        default=False, description="启动WebUI后自动打开浏览器（仅开发/本地环境建议启用）"
    )


class DevConfig(BaseModel):
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
