# Data Model: 001-webui-backend-refactor

本数据模型基于 feature spec 的 Key Entities、小结以及现有实现（`core/`, `common/`, `webui/models.py`, `webui/services/*` 和测试用例）整理，用于指导后续实现与接口设计。

## 1. 后端服务实例（Backend Service）

- **Entity**: `BackendService`
- **Responsibility**: 表示整个订阅系统的常驻进程状态，由 WebUI 仪表盘展示。
- **Key Fields**（对应 `webui.models.SystemStatus`）:
  - `status: str` — 当前状态：`"running" | "stopped" | "error"`。
  - `uptime: str` — 运行时长（`HH:MM:SS`），从主进程启动到当前时间。
  - `cpu_usage: float` — CPU 使用率（百分比）。
  - `memory_usage: float` — 内存使用率（百分比）。
  - `disk_usage: float` — 磁盘使用率（百分比），用于简单容量告警。
  - `version: str` — 当前运行版本（例如 `"0.5.5"`）。
- **State Transitions**:
  - `stopped -> running`：通过 `/api/system/start` 启动主进程。
  - `running -> stopped`：通过 `/api/system/stop` 或进程退出。
  - 任意 -> `error`：监控到主进程异常退出或指标异常时，由服务层映射为错误态（后续可扩展）。

## 2. 订阅监控任务（Subscription Monitor Job）

- **Entity**: `SubscriptionMonitorJob`
- **Responsibility**: 表示对一组 RSS 源进行周期轮询的任务集合。当前实现中主要体现在 `core/rss_monitor.py`，对 WebUI 以聚合状态呈现。
- **Key Fields**（高层抽象，未来可在 API 或模型中显式化）:
  - `enabled: bool` — 是否启用订阅监控。
  - `interval_seconds: int` — 轮询间隔（来自配置 `common.interval_time`）。
  - `last_check_at: datetime | None` — 最近一次检查时间。
  - `last_found_count: int` — 最近一次检查发现的新条目数。
- **State Transitions**:
  - `enabled` 状态由配置和系统控制接口共同决定（例如重启系统后默认启用）。

## 3. 下载任务（Download Task）

- **Entity**: `DownloadTask`
- **Responsibility**: 对应从 RSS 中提取出的单个或一组下载项，结合 Alist/qBittorrent/WebDAV 形成完整下载链路。
- **Key Fields**（与现有核心逻辑对齐，WebUI 当前主要通过日志侧面反映）:
  - `id: str` — 任务 ID（可以是内部生成的 UUID）。
  - `title: str` — 原始标题（来自 RSS）。
  - `series_name: str` — 番剧名称（来自 extractor/LLM 解析）。
  - `episode_number: str | int` — 集数信息。
  - `download_url: str` — 种子或磁力链接。
  - `target_path: str` — 在网盘上的目标路径（含番剧目录）。
  - `status: str` — `"pending" | "downloading" | "completed" | "failed"` 等。
  - `created_at: datetime` — 任务创建时间。
  - `finished_at: datetime | None` — 完成或失败时间。
- **Notes**:
  - WebUI 当前通过日志 API 暴露下载行为（如“Download started/completed”），后续可以在 API 层增加显式任务查询端点。

## 4. 配置（Application Configuration）

- **Entity**: `AppConfig`
- **Responsibility**: 表示持久化在 YAML 文件中的整体配置，由 WebUI 通过配置表单完整管理。
- **Key Fields**（对应 `ConfigService` 验证和 `tests/webui/test_services.py` 中假定结构）:
  - `common`:
    - `interval_time: int` — RSS 检查间隔（秒），最小值约束为 60。
    - `log_level: str` — 日志级别：`"DEBUG" | "INFO" | "WARNING" | "ERROR"`。
  - `alist`:
    - `base_url: str` — Alist/WebDAV 服务地址（需要合法 URL）。
    - `token: str` — 访问 Alist 的鉴权 Token（可选但强烈建议配置）。
    - `downloader: str` — 下载器类型，例如 `"qBittorrent"`。
  - `mikan`:
    - `subscribe_url: list[str]` — RSS 订阅地址列表。
    - `filters: list[str]` — 过滤规则（如“非合集”“1080p”）。
  - 其他模块配置（如重命名、WebDAV 行为）沿用现有结构，WebUI 通过 schema 动态驱动表单。
- **Validation Rules**（由 `ConfigService` 实现）:
  - `interval_time >= 60`。
  - `log_level` 必须在允许枚举内。
  - `alist.base_url` 必须为合法 URL。
  - 缺失关键字段会被视为无效配置并在验证结果中列出。

## 5. 日志相关实体

### 5.1 日志文件信息（LogFileInfo）

- **Entity**: `LogFileInfo`（对应 `webui.models.LogFileInfo`）
- **Fields**:
  - `name: str` — 文件名，例如 `"app.log"` 或 `"app_2025-10-10.log"`。
  - `size: int` — 文件大小（字节）。
  - `modified: str` — 最近修改时间（ISO8601）。

### 5.2 日志条目（LogEntry）

- **Entity**: `LogEntry`（对应 `webui.models.LogEntry`）
- **Fields**:
  - `timestamp: str` — 日志时间（ISO8601 字符串）。
  - `level: str` — 日志级别：`"DEBUG" | "INFO" | "WARNING" | "ERROR"`。
  - `message: str` — 日志正文。
  - `module: str | None` — 模块名（可选）。
  - `line_number: int | None` — 行号（可选）。
  - `thread_id: str | None` — 线程标识（可选）。

## 6. 维护任务（Maintenance Job, WebDAV 手动修复）

- **Entity**: `WebdavManualFixJob`
- **Responsibility**: 表示一次由用户触发的 WebDAV 嵌套修复任务（预览或实际执行），通过 WebUI 中的“手动修复”界面发起。
- **Request Model**（对应 `ManualFixRequest`）:
  - `path: str | None` — 目标路径，例如 `/115/TV/...`。
  - `execute_mode: bool | None` — `False` 表示预览（dry-run），`True` 表示实际执行。
  - `recursive_scan: bool | None` — 是否递归扫描子目录。
  - `conflict_strategy: str | None` — 冲突解决策略：`"skip" | "rename" | "overwrite"`。
- **Response Model**（对应 `ManualFixResponse`）:
  - `success: bool` — 是否成功。
  - `message: str | None` — 人类可读的结果说明。
  - `target_dir: str | None` — 实际操作的目录。
  - `dry_run: bool | None` — 是否为预览模式。
  - `options: dict | None` — 传给底层脚本/服务的选项快照。
  - `result: dict | None` — 统计信息（如总条目、成功数、跳过数、错误数）和明细。

## 7. WebUI 通用响应包装（ApiResponse）

- **Entity**: `ApiResponse`（对应 `webui.models.ApiResponse`）
- **Responsibility**: 为某些端点提供统一的 `success/message/data` 包装结构。
- **Fields**（抽象）:
  - `success: bool` — 操作是否成功。
  - `message: str | None` — 可选消息。
  - `data: dict | list | None` — 具体负载，按端点定义。

---

此数据模型文档主要服务于：
- 设计与维护 WebUI 所依赖的核心 API 与服务层模型；
- 为未来可能增加的 OpenAPI schema 生成器或类型检查提供结构参考；
- 在讨论新需求（例如显式的任务列表页面）时，作为实体与字段设计的基础。
