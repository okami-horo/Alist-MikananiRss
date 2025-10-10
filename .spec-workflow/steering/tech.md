# 技术架构文档

## 技术栈概览

### 核心技术栈
- **编程语言**: Python 3.11+
- **异步框架**: asyncio (原生异步编程)
- **HTTP客户端**: aiohttp (异步HTTP请求)
- **配置管理**: Pydantic (数据验证和设置管理)
- **日志系统**: loguru (结构化日志)
- **数据库**: SQLite + aiosqlite (异步数据库操作)

### 外部集成
- **Alist API**: v3.42.0+ 文件管理平台
- **RSS解析**: feedparser (RSS/Atom订阅源解析)
- **AI服务**: OpenAI GPT、Google Gemini、DeepSeek (智能重命名)
- **下载器**: qBittorrent、Aria2、115 Open (离线下载)
- **通知服务**: Telegram Bot、PushPlus (状态通知)
- **WebDAV**: webdav4 (云存储文件操作)

## 系统架构

### 整体架构设计
```
┌─────────────────────────────────────────────────────────────┐
│                    Alist-MikananiRss                      │
├─────────────────────────────────────────────────────────────┤
│  命令行接口 (CLI) & Telegram机器人                          │
├─────────────────────────────────────────────────────────────┤
│                      核心业务层                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ RSS监控器   │ │ 下载管理器  │ │ 任务监控器  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ AI重命名器  │ │ 通知发送器  │ │ WebDAV修复器│           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│                      服务适配层                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Alist API   │ │  RSS解析器  │ │ LLM提供商   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ 通知机器人  │ │ WebDAV客户端│ │ 种子转换器  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│                      基础设施层                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  配置管理   │ │  数据库     │ │  日志系统   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件架构

### 1. RSS监控引擎 (RssMonitor)
**职责**: 定期检查RSS源，发现新番剧更新

**技术特点**:
- 异步并发处理多个RSS源
- 智能去重和过滤机制
- 支持多种RSS源格式解析
- 自动种子到磁力链接转换

**关键流程**:
```python
async def get_new_resources() -> List[ResourceInfo]:
    # 1. 并发获取所有RSS源条目
    feed_entries = await asyncio.gather(*[website.get_feed_entries() for website in websites])

    # 2. 正则表达式过滤
    filtered_entries = filter(filter.filt_single, feed_entries)

    # 3. 数据库去重检查
    new_entries = [entry for entry in filtered_entries if not await db.exists(entry.title)]

    # 4. 批量种子转换
    if convert_torrent_to_magnet:
        magnet_links = await batch_convert_torrents_to_magnets(torrent_urls)

    return processed_resources
```

### 2. 下载管理器 (DownloadManager)
**职责**: 管理Alist下载任务，监控下载进度

**技术特点**:
- 单例模式确保全局唯一
- 智能路径构建和文件组织
- 批量任务创建优化API调用
- 自适应轮询间隔

**任务监控机制**:
```python
class TaskMonitor:
    async def run(self):
        # 自适应轮询间隔
        poll_interval = 0.5  # 基础间隔
        while running_tasks:
            # 1. 获取远程任务状态
            remote_tasks = await self._fetch_remote_tasks()

            # 2. 更新本地任务状态
            self._refresh_task(running_tasks, remote_tasks)

            # 3. 处理完成的任务
            completed_tasks = self._extract_completed_tasks()
            await self._process_completed_tasks(completed_tasks)

            # 4. 自适应休眠
            await asyncio.sleep(poll_interval)
```

### 3. AI重命名引擎 (AnimeRenamer)
**职责**: 使用AI分析文件名并重命名为标准格式

**技术特点**:
- 支持多个LLM提供商
- 结构化输出确保格式一致性
- 自定义重命名规则映射
- 批量处理优化

**AI集成架构**:
```python
class LLMExtractor:
    async def extract_anime_info(self, filename: str) -> AnimeInfo:
        # 1. 构建提示词
        prompt = self._build_prompt(filename)

        # 2. 调用LLM API
        response = await self.llm_provider.generate(prompt)

        # 3. 结构化输出解析
        anime_info = self._parse_response(response)

        return anime_info
```

### 4. WebDAV修复器 (WebDAVNestedFixer)
**职责**: 修复WebDAV嵌套目录结构问题

**技术特点**:
- 递归目录扫描
- 智能冲突处理策略
- 批量文件操作优化
- 详细的操作日志

### 5. 通知系统 (NotificationSender)
**职责**: 多渠道状态通知和消息推送

**技术特点**:
- 支持多种通知渠道
- 批量通知合并优化
- 异步消息发送
- 失败重试机制

## 数据流架构

### 主要数据流
```
RSS源 → RSS解析器 → 过滤器 → 数据库去重 → 下载管理器 → Alist API
                                    ↓
WebDAV修复器 ← 文件重命名 ← AI分析 ← 下载完成监控 ← 任务监控器
                                    ↓
                              通知发送器 → 用户通知
```

### 数据模型设计
```python
@dataclass
class ResourceInfo:
    resource_title: str          # RSS条目标题
    torrent_url: str            # 种子/磁力链接
    anime_name: Optional[str]   # 动漫名称
    season: Optional[int]       # 季数
    episode: Optional[int]      # 集数
    group: Optional[str]        # 字幕组
    quality: Optional[str]      # 画质质量
```

## 配置系统架构

### 分层配置设计
```yaml
# config.yaml - 主配置文件
common:         # 通用配置
alist:          # Alist集成配置
mikan:          # RSS订阅配置
rename:         # AI重命名配置
notification:   # 通知配置
webdav:         # WebDAV配置
bot_assistant:  # 机器人助手配置
dev:           # 开发调试配置
```

### 配置验证系统
- **Pydantic模型**: 强类型配置验证
- **默认值策略**: 合理的默认配置
- **环境变量支持**: 敏感信息外部化
- **配置热重载**: 运行时配置更新

## 性能优化策略

### 1. 异步并发优化
- **并发RSS处理**: 同时处理多个RSS源
- **信号量控制**: 限制并发数量避免资源耗尽
- **批量API调用**: 减少网络往返次数
- **连接池复用**: HTTP客户端连接复用

### 2. 内存管理优化
- **固定大小集合**: 避免内存无限增长
- **及时资源清理**: 任务完成后清理相关对象
- **流式处理**: 大文件采用流式读取
- **缓存策略**: 合理的TTL缓存机制

### 3. 网络优化
- **自适应轮询**: 根据任务数量调整轮询间隔
- **批量操作**: 文件操作的批量处理
- **重试机制**: 智能的指数退避重试
- **超时控制**: 合理的网络超时设置

## 错误处理和恢复

### 分层错误处理
```python
# 1. 网络层错误处理
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
async def api_call():
    # API调用逻辑

# 2. 业务层错误处理
try:
    result = await business_logic()
except SpecificError as e:
    logger.error(f"业务逻辑错误: {e}")
    # 降级处理

# 3. 系统层错误处理
except Exception as e:
    logger.critical(f"系统错误: {e}")
    # 系统级恢复
```

### 恢复策略
- **任务重试**: 指数退避重试机制
- **状态恢复**: 数据库持久化任务状态
- **降级服务**: 核心功能保障
- **监控告警**: 异常情况及时通知

## 安全考虑

### 1. 认证和授权
- **Token认证**: Alist API Token认证
- **API密钥管理**: LLM服务API密钥安全存储
- **访问控制**: 最小权限原则

### 2. 数据安全
- **敏感信息**: 配置文件敏感信息加密
- **网络安全**: HTTPS通信支持
- **输入验证**: 严格的输入参数验证

### 3. 运行安全
- **资源限制**: 并发数量和内存使用限制
- **异常处理**: 避免敏感信息泄露
- **日志安全**: 敏感信息脱敏处理

## 可扩展性设计

### 1. 插件化架构
```python
# RSS源插件化
class Website(ABC):
    @abstractmethod
    async def get_feed_entries(self) -> List[FeedEntry]:
        pass

# LLM提供商插件化
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass
```

### 2. 配置驱动扩展
- **动态RSS源**: 配置文件添加新RSS源
- **自定义过滤器**: 正则表达式过滤规则
- **通知渠道**: 新增通知方式
- **下载器支持**: 新下载器适配

### 3. 模块化设计
- **松耦合**: 模块间依赖最小化
- **接口抽象**: 面向接口编程
- **依赖注入**: 便于测试和扩展
- **事件驱动**: 异步事件处理机制

## 监控和观测

### 1. 日志系统
```python
# 结构化日志配置
logger.add(
    "log/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    level=INFO,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)
```

### 2. 指标监控
- **任务统计**: 下载成功/失败数量
- **性能指标**: API响应时间、处理速度
- **资源使用**: 内存、CPU使用情况
- **错误监控**: 异常类型和频率统计

### 3. 健康检查
- **服务可用性**: 定期检查外部服务状态
- **资源检查**: 磁盘空间、网络连接
- **配置验证**: 配置文件有效性检查
- **功能测试**: 核心功能端到端测试

## 部署架构

### 1. 容器化部署
```dockerfile
# 多阶段构建优化镜像大小
FROM python:3.11-slim as builder
# 依赖安装阶段

FROM python:3.11-slim as runtime
# 运行时阶段
```

### 2. 环境配置
- **开发环境**: 详细日志和调试功能
- **测试环境**: 模拟数据和测试配置
- **生产环境**: 优化配置和安全设置

### 3. 运维支持
- **优雅关闭**: 信号处理和资源清理
- **配置热更新**: 运行时配置修改
- **日志轮转**: 自动日志管理
- **备份恢复**: 配置和数据备份策略