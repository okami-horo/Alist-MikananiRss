# 项目结构文档

## 目录结构概览

```
alist-mikananirss/
├── src/alist_mikananirss/          # 主要源代码目录
│   ├── __init__.py                 # 包初始化和公共API导出
│   ├── __main__.py                 # 模块直接执行入口
│   ├── main.py                     # 应用程序主入口
│   ├── alist/                      # Alist API集成模块
│   ├── bot/                        # 通知和机器人模块
│   ├── common/                     # 公共组件模块
│   │   └── config/                 # 配置管理子模块
│   ├── core/                       # 核心业务逻辑模块
│   ├── extractor/                  # AI提取和分析模块
│   │   └── llm/                    # LLM提供商实现
│   ├── utils/                      # 工具函数模块
│   └── websites/                   # RSS源解析模块
├── tests/                          # 测试代码目录
│   ├── alist/                      # Alist模块测试
│   ├── bot/                        # 机器人模块测试
│   ├── common/                     # 公共模块测试
│   ├── core/                       # 核心模块测试
│   │   └── download_manager/       # 下载管理器详细测试
│   ├── extractor/                  # 提取器模块测试
│   └── websites/                   # RSS解析模块测试
├── .spec-workflow/                 # 项目指导文档
│   └── steering/                   # 指导文档目录
├── docker/                         # Docker相关文件
├── log/                            # 日志文件目录
├── docs/                           # 文档目录
├── config.yaml                     # 主配置文件示例
├── pyproject.toml                  # 项目配置和依赖管理
├── README.md                       # 项目说明文档
├── CLAUDE.md                       # Claude Code 指导文档
└── pytest.ini                      # 测试配置文件
```

## 核心模块结构

### 1. 主程序入口 (`main.py`)
**职责**: 应用程序启动、命令行解析、模块初始化

**核心功能**:
- 命令行参数解析 (monitor, webdav-fix)
- 配置加载和验证
- 日志系统初始化
- 核心组件初始化和依赖注入
- 异步任务协调

**主要流程**:
```python
async def run():
    # 1. 命令行解析
    args = parser.parse_args()

    # 2. 配置管理
    cfg = ConfigManager().load_config(args.config)
    init_logging(cfg)
    init_proxies(cfg)

    # 3. 核心组件初始化
    db = await SubscribeDatabase.create()
    alist_client = Alist(cfg.alist.base_url, cfg.alist.token, cfg.alist.downloader)
    DownloadManager.initialize(...)

    # 4. 业务模块启动
    tasks = [rss_monitor.run()]
    if cfg.notification.enable:
        tasks.append(NotificationSender.run())
    if cfg.bot_assistant.enable:
        tasks.append(bot_assistant.run())

    # 5. 并发执行
    await asyncio.gather(*tasks)
```

### 2. Alist集成模块 (`alist/`)

#### 2.1 API客户端 (`alist/api.py`)
**职责**: Alist服务器API交互

**核心类**:
- `Alist`: 主要API客户端
- `AlistClientError`: 自定义异常类

**主要方法**:
- `add_offline_download_task()`: 创建离线下载任务
- `get_task_list()`: 获取任务列表
- `upload()`: 文件上传
- `list_dir()`: 目录列表
- `cancel_task()`: 取消任务

#### 2.2 任务模型 (`alist/tasks.py`)
**职责**: Alist任务数据模型定义

**核心类**:
- `AlistTask`: 任务基类
- `AlistDownloadTask`: 下载任务
- `AlistTransferTask`: 转移任务
- `AlistTaskState`: 任务状态枚举
- `AlistDownloaderType`: 下载器类型枚举

### 3. 核心业务模块 (`core/`)

#### 3.1 RSS监控器 (`core/rss_monitor.py`)
**职责**: RSS源监控和新资源发现

**核心类**:
- `RssMonitor`: RSS监控主类

**主要功能**:
- 多RSS源并发处理
- 资源过滤和去重
- 种子到磁力链接转换
- 下载任务触发

**关键方法**:
```python
async def get_new_resources() -> List[ResourceInfo]:
    # 并发处理RSS源
    # 应用过滤规则
    # 数据库去重检查
    # 种子转换处理
```

#### 3.2 下载管理器 (`core/download_manager.py`)
**职责**: 下载任务管理和监控

**核心类**:
- `DownloadManager`: 下载管理器 (单例)
- `TaskMonitor`: 任务监控器

**主要功能**:
- 下载任务创建
- 任务状态监控
- 智能路径构建
- 完成后处理

#### 3.3 AI重命名器 (`core/renamer.py`)
**职责**: 文件智能重命名

**核心类**:
- `AnimeRenamer`: 重命名处理器

**重命名格式**:
- 支持模板化命名
- Emby兼容格式
- 季集信息标准化

#### 3.4 WebDAV修复器 (`core/webdav_fixer.py`)
**职责**: WebDAV嵌套目录结构修复

**核心类**:
- `WebDAVNestedFixer`: 修复器主类

**修复策略**:
- 递归目录扫描
- 冲突处理 (跳过/重命名/覆盖)
- 批量文件操作

#### 3.5 其他核心组件
- `core/filter.py`: 正则表达式过滤器
- `core/notification_sender.py`: 通知发送器
- `core/bot_assistant.py`: 机器人助手
- `core/remapper.py`: 自定义映射管理器

### 4. AI提取模块 (`extractor/`)

#### 4.1 提取器基类 (`extractor/base.py`)
**职责**: 提取器抽象基类

#### 4.2 LLM提取器 (`extractor/llm_extractor.py`)
**职责**: 基于LLM的内容提取和分析

**核心功能**:
- 动漫名称分析
- 资源标题解析
- TMDB信息集成

#### 4.3 LLM提供商 (`extractor/llm/`)
**职责**: 多种LLM服务提供商适配

**实现**:
- `openai.py`: OpenAI API集成
- `google.py`: Google Gemini API集成
- `deepseek.py`: DeepSeek API集成
- `base.py`: LLM提供商抽象基类

#### 4.4 提示词管理 (`extractor/llm/prompt/`)
**职责**: AI提示词模板管理

**支持模式**:
- JSON对象模式
- JSON Schema模式

#### 4.5 模型定义 (`extractor/models.py`)
**职责**: 数据模型定义

**核心模型**:
- `ResourceTitleExtractResult`: 资源标题提取结果
- `AnimeNameExtractResult`: 动漫名称分析结果
- `TMDBTvInfo`: TMDB影视信息

### 5. 机器人模块 (`bot/`)

#### 5.1 机器人基类 (`bot/bot_base.py`)
**职责**: 机器人抽象基类

#### 5.2 通知机器人 (`bot/notificationbot.py`)
**职责**: 通知消息封装

#### 5.3 具体实现
- `bot/tgbot.py`: Telegram机器人实现
- `bot/pushplus_bot.py`: PushPlus机器人实现

### 6. RSS解析模块 (`websites/`)

#### 6.1 解析器基类 (`websites/base.py`)
**职责**: RSS源解析抽象基类

#### 6.2 具体实现
- `websites/mikan.py`: 蜜柑计划RSS解析
- `websites/dmhy.py`: 动漫花园RSS解析
- `websites/acgrip.py`: ACG.RIP RSS解析
- `websites/default.py`: 通用RSS解析

#### 6.3 工厂模式 (`websites/factory.py`)
**职责**: RSS解析器工厂

#### 6.4 数据模型 (`websites/models.py`)
**核心模型**:
- `FeedEntry`: RSS条目
- `ResourceInfo`: 资源信息

### 7. 配置管理模块 (`common/config/`)

#### 7.1 主配置 (`common/config/config.py`)
**职责**: 配置加载和管理

**核心类**:
- `AppConfig`: 应用配置总模型
- `ConfigManager`: 配置管理器

#### 7.2 基础配置 (`common/config/basic.py`)
**配置模块**:
- `CommonConfig`: 通用配置
- `AlistConfig`: Alist配置
- `MikanConfig`: RSS订阅配置
- `NotificationConfig`: 通知配置
- `RenameConfig`: 重命名配置
- `WebdavConfig`: WebDAV配置
- `BotAssistantConfig`: 机器人配置
- `DevConfig`: 开发配置

#### 7.3 扩展配置
- `common/config/extractor.py`: AI提取器配置
- `common/config/notifier.py`: 通知器配置
- `common/config/remap.py`: 重映射配置
- `common/config/bot_assistant.py`: 机器人助手配置

### 8. 工具模块 (`utils/`)

#### 8.1 核心工具
- `utils/torrent_converter.py`: 种子转换工具
- `utils/tmdb.py`: TMDB API客户端

### 9. 数据库模块 (`common/database.py`)
**职责**: 数据持久化

**核心类**:
- `SubscribeDatabase`: 订阅数据库

## 测试结构

### 测试目录组织
```
tests/
├── alist/                          # Alist模块测试
├── bot/                            # 机器人模块测试
├── common/                         # 公共模块测试
├── core/                           # 核心模块测试
│   └── download_manager/           # 下载管理器详细测试
├── extractor/                      # 提取器模块测试
└── websites/                       # RSS解析模块测试
```

### 测试配置 (`pytest.ini`)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short
```

### 测试特点
- **异步测试**: 使用pytest-asyncio支持异步测试
- **模拟测试**: 使用aioresponses模拟HTTP响应
- **模块化**: 按功能模块组织测试
- **覆盖率**: 支持代码覆盖率测试

## 代码组织原则

### 1. 模块化设计
- **单一职责**: 每个模块专注于特定功能
- **松耦合**: 模块间依赖最小化
- **高内聚**: 相关功能集中在同一模块

### 2. 分层架构
```
表示层 (CLI/Bot)
    ↓
业务逻辑层 (Core)
    ↓
服务适配层 (Alist/Websites/Bot)
    ↓
基础设施层 (Config/Database/Utils)
```

### 3. 接口抽象
- **抽象基类**: 定义统一接口
- **工厂模式**: 动态创建实现
- **策略模式**: 可替换的算法实现

### 4. 依赖注入
- **初始化参数**: 通过构造函数注入依赖
- **单例模式**: 全局共享组件
- **配置驱动**: 通过配置控制行为

## 命名规范

### 1. 文件命名
- **模块文件**: 小写字母 + 下划线 (`rss_monitor.py`)
- **类文件**: 大驼峰命名 (`DownloadManager.py`)
- **测试文件**: `test_` 前缀 (`test_rss_monitor.py`)

### 2. 类命名
- **类名**: 大驼峰命名 (`RssMonitor`, `DownloadManager`)
- **异常类**: `Error` 后缀 (`AlistClientError`)

### 3. 函数和变量命名
- **函数**: 小写字母 + 下划线 (`get_new_resources`)
- **变量**: 小写字母 + 下划线 (`resource_info`)
- **常量**: 大写字母 + 下划线 (`MAX_RETRY_TIMES`)

### 4. 私有成员
- **私有方法**: `_` 前缀 (`_fetch_remote_tasks`)
- **私有变量**: `_` 前缀 (`_session_lock`)

## 导入组织

### 1. 导入顺序
```python
# 1. 标准库导入
import asyncio
import os
from typing import List, Optional

# 2. 第三方库导入
import aiohttp
from loguru import logger
from pydantic import BaseModel

# 3. 本地导入
from alist_mikananirss.common import config
from .utils import helper_function
```

### 2. 相对导入
- **同级模块**: `from .module import Class`
- **上级模块**: `from ..package import module`
- **子模块**: `from .subpackage import Class`

## 错误处理模式

### 1. 异常层次
```python
# 自定义异常基类
class AlistMikananirssError(Exception):
    """基础异常类"""
    pass

# 具体异常类
class AlistClientError(AlistMikananirssError):
    """Alist客户端错误"""
    pass

class ExtractorError(AlistMikananirssError):
    """提取器错误"""
    pass
```

### 2. 错误处理策略
- **业务异常**: 自定义异常类型
- **系统异常**: 记录日志并重新抛出
- **网络异常**: 重试机制
- **配置错误**: 启动时验证

## 配置管理策略

### 1. 配置文件结构
```yaml
# 分层配置设计
common:           # 通用配置
alist:           # Alist相关配置
mikan:           # RSS订阅配置
rename:          # 重命名配置
notification:    # 通知配置
webdav:          # WebDAV配置
bot_assistant:   # 机器人配置
dev:             # 开发配置
```

### 2. 配置验证
- **Pydantic模型**: 强类型验证
- **默认值**: 合理的默认配置
- **环境变量**: 敏感信息外部化

## 日志系统设计

### 1. 日志配置
```python
logger.add(
    "log/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",        # 每日轮转
    retention="7 days",      # 保留7天
    level="INFO",           # 日志级别
    format="{time} | {level} | {name}:{function}:{line} | {message}"
)
```

### 2. 日志级别使用
- **DEBUG**: 详细调试信息
- **INFO**: 一般信息记录
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

## 扩展点设计

### 1. RSS源扩展
```python
# 实现新的RSS解析器
class NewWebsite(Website):
    async def get_feed_entries(self) -> List[FeedEntry]:
        # 实现解析逻辑
        pass

# 注册到工厂
WebsiteFactory.register('newsite', NewWebsite)
```

### 2. LLM提供商扩展
```python
# 实现新的LLM提供商
class NewLLMProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        # 实现API调用
        pass
```

### 3. 通知渠道扩展
```python
# 实现新的通知机器人
class NewNotificationBot(BotBase):
    async def send_message(self, message: str):
        # 实现消息发送
        pass
```

## 部署相关结构

### 1. Docker支持
```
docker/
├── Dockerfile              # 主镜像构建文件
└── docker-compose.yml      # 容器编排文件
```

### 2. 配置文件
- `config.yaml`: 生产环境配置模板
- `config.example.yaml`: 配置示例

### 3. 脚本文件
- `scripts/`: 部署和维护脚本
- `entrypoint.sh`: 容器入口脚本

这个项目结构设计体现了现代Python应用的最佳实践，包括模块化、可测试性、可扩展性和维护性等方面的考虑。