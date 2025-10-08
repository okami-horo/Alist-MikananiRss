# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alist-MikananiRss 是一个基于 Python 的自动化动漫下载管理系统，主要用于从蜜柑计划(Mikan Project)或其他动漫RSS订阅源获取番剧更新，并通过Alist集成下载器将文件下载到云存储。项目结合AI技术实现智能重命名，并提供多渠道通知功能。

**版本**: 0.5.5
**Python要求**: >=3.11
**主要维护者**: TwooSix

## Core Architecture

### 模块化架构

项目采用模块化设计，主要组件包括：

#### 核心模块 (`src/alist_mikananirss/core/`)
- **RssMonitor**: RSS监控核心，负责定期检查RSS源并触发下载
- **DownloadManager**: 下载任务管理器，管理Alist下载任务
- **AnimeRenamer**: AI驱动的动漫重命名工具
- **NotificationSender**: 多渠道通知发送器
- **BotAssistant**: Telegram机器人助手
- **RegexFilter**: RSS内容过滤器
- **WebDAVNestedFixer**: WebDAV嵌套目录修复工具

#### Alist集成 (`src/alist_mikananirss/alist/`)
- **API客户端**: 与Alist服务器(v3.42.0+)通信
- **任务监控**: 跟踪下载进度和完成状态
- **支持下载器**: qBittorrent, Aria2, 115 Open

#### 配置系统 (`src/alist_mikananirss/common/config/`)
基于Pydantic的配置管理，支持：
- 基础配置：CommonConfig, AlistConfig, MikanConfig
- 功能配置：RenameConfig, NotificationConfig, WebdavConfig
- Bot配置：BotAssistantConfig
- 开发配置：DevConfig

#### AI集成 (`src/alist_mikananirss/extractor/`)
支持的LLM提供商：
- **OpenAI**: GPT模型支持
- **Google Gemini**: Google AI模型
- **DeepSeek**: 国产AI模型
- **结构化输出**: JSON格式的重命名结果

### 异步架构

项目全面使用asyncio实现高并发：
- 异步HTTP客户端(aiohttp)
- 异步数据库操作(aiosqlite)
- 异步文件操作
- 并发下载任务处理

## Development Commands

### 环境管理
```bash
# 使用uv管理依赖（推荐）
uv sync

# 使用pip安装
pip install -e .

# 开发模式运行
uv run python -m alist_mikananirss --config config.yaml

# 直接运行
python -m alist_mikananirss --config config.yaml
```

### 测试
```bash
# 运行所有测试
pytest

# 运行特定测试模块
pytest tests/core/test_download_manager.py

# 运行带覆盖率的测试
pytest --cov=src/alist_mikananirss

# 异步测试已配置为自动模式 (pytest.ini: asyncio_mode = auto)
```

### 代码质量
```bash
# 代码检查
ruff check src/

# 代码格式化
black src/

# 类型检查（可选）
mypy src/
```

### WebDAV修复工具
```bash
# 查看帮助
uv run alist-mikananirss webdav-fix --help

# 预览模式（不实际执行）
uv run alist-mikananirss webdav-fix --dir "/115/TV/2025-07" --verbose

# 实际执行修复
uv run alist-mikananirss webdav-fix --dir "/115/TV/胆大党 第二季" --force --verbose

# 递归扫描
uv run alist-mikananirss webdav-fix --dir "/115/TV/2025-10/" --recursive --force
```

## Configuration

### 基础配置 (`config.yaml`)

```yaml
common:
  interval_time: 300  # RSS检查间隔（秒）
  proxies: {}         # HTTP/HTTPS代理配置

alist:
  base_url: http://192.168.31.37:5244
  token: alist-xxx
  downloader: 115 Open  # qBittorrent, aria2, 115 Open
  download_path: 115/TV/2025-10
  convert_torrent_to_magnet: true

mikan:
  subscribe_url:
    - https://mikanani.me/RSS/MyBangumi?token=xxx
  filters:
    - 非合集  # 过滤合集内容

rename:
  enable: false
  extractor:
    extractor_type: openai  # openai, google, deepseek
    api_key: xxx
    model: glm-4-flash

webdav:
  url: "http://192.168.31.37:5244/dav"
  username: "admin"
  password: "xxx"
  fixer:
    execute_mode: true        # 是否实际执行修复
    recursive_scan: true      # 递归扫描
    conflict_strategy: "overwrite"  # skip, rename, overwrite

notification:
  telegram:
    enable: false
    bot_token: xxx
    chat_id: xxx
  pushplus:
    enable: false
    token: xxx
```

## Work Flow

1. **RSS监控**: 定期检查配置的RSS源
2. **内容过滤**: 应用正则表达式过滤器
3. **下载任务**: 通过Alist API创建下载任务
4. **任务监控**: 跟踪下载进度
5. **AI重命名**: 使用LLM分析并重命名文件
6. **WebDAV修复**: 自动修复嵌套目录结构
7. **通知发送**: 多渠道发送完成通知

## Key Dependencies

### 核心依赖
- **aiohttp**: 异步HTTP客户端
- **feedparser**: RSS解析
- **loguru**: 结构化日志
- **pydantic**: 数据验证和配置管理
- **PyYAML**: YAML配置文件支持
- **webdav4**: WebDAV客户端
- **aiosqlite**: 异步SQLite数据库

### AI依赖
- **openai**: OpenAI API客户端
- **google-genai**: Google AI API客户端

### 机器人依赖
- **python-telegram-bot**: Telegram机器人API
- **beautifulsoup4**: HTML解析

### 开发依赖
- **pytest**: 测试框架，支持异步测试
- **aioresponses**: HTTP响应模拟
- **ruff**: 快速Python linter
- **black**: 代码格式化
- **coverage**: 代码覆盖率

## Database & Logging

### 数据库
- **类型**: SQLite
- **用途**: 存储订阅历史和下载元数据
- **操作**: 通过`SubscribeDatabase`类处理

### 日志系统
- **库**: loguru
- **轮转**: 每日轮转 (`rotation="00:00"`)
- **保留**: 7天 (`retention="7 days"`)
- **输出**: 文件 (`log/alist_mikanrss_{time:YYYY-MM-DD}.log`) + 控制台
- **级别**: 通过`dev.log_level`配置

## Special Features

### WebDAV嵌套目录修复
专门用于修复WebDAV嵌套目录结构的工具：
- **自动触发**: 下载完成后可自动执行
- **智能扫描**: 递归扫描嵌套目录
- **冲突处理**: 支持跳过、重命名、覆盖策略
- **详细日志**: 完整的操作过程记录

### AI智能重命名
使用LLM分析文件名并重命名为Emby兼容格式：
```
原文件名: [桜都字幕组] 小城日常 [01][1080p][简体内嵌].mp4
重命名后: 小城日常 S01E01.mp4
```

### 多RSS源支持
- **蜜柑计划**: 主要支持的动漫RSS源
- **动漫花园**: DMHY动漫资源
- **ACG.RIP**: 高质量动漫资源
- **通用RSS**: 支持标准RSS格式

### Telegram机器人助手
- **远程管理**: 通过Telegram管理下载任务
- **状态查询**: 查看下载进度和RSS更新
- **配置管理**: 修改部分配置项
- **日志查看**: 获取系统运行日志

## Deployment

### Docker部署
```bash
# 多平台构建 (linux/amd64, linux/arm64)
docker build -f docker/Dockerfile -t alist-mikananirss .

# 运行容器
docker run -v /path/to/config.yaml:/config.yaml okami-horo/alist-mikananirss:latest
```

### 源码部署
```bash
# 安装依赖
pip install alist-mikananirss

# 运行应用
python -m alist_mikananirss --config config.yaml
```

## CI/CD

### GitHub Actions工作流
1. **Docker发布** (`publish_docker.yml`): 多平台构建并推送到Docker Hub
2. **PyPI发布** (`publish_pypi.yml`): 自动构建并发布到Python包索引

## Testing Strategy

### 测试结构
```
tests/
├── alist/           # Alist客户端测试
├── bot/             # 机器人模块测试
├── common/          # 公共模块测试
├── core/            # 核心功能测试
├── extractor/       # AI提取器测试
└── websites/        # RSS解析器测试
```

### 测试配置
- **异步测试**: pytest-asyncio (自动模式)
- **Mock支持**: aioresponses用于HTTP响应模拟
- **测试顺序**: pytest-order控制测试执行顺序

## Security Considerations

- **API认证**: Alist API使用Token认证
- **HTTPS支持**: 支持HTTPS通信
- **代理支持**: 支持HTTP/HTTPS代理
- **配置验证**: Pydantic模型验证配置合法性
- **敏感信息**: 支持环境变量注入

## Performance Optimization

- **异步架构**: 全面采用异步编程，支持高并发
- **连接池**: HTTP客户端使用连接池
- **批量处理**: 支持批量文件操作和种子转换
- **内存管理**: 使用固定大小集合避免内存泄漏