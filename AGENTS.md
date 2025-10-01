# Alist-MikananiRss 项目功能结构文档

## 项目概述

**项目名称**: Alist-MikananiRss  
**版本**: 0.5.5  
**Python版本**: >=3.11  

### 项目目标
从蜜柑计划或其他动漫番剧相关的RSS订阅源中自动获取番剧更新，通过Alist离线下载至对应网盘，并结合ChatGPT分析资源名，将资源重命名为Emby可解析的格式。

### 主要功能
- ✅ 自动获取番剧更新并下载至对应网盘
- ✅ 通过PushPlus、Telegram等渠道发送更新通知
- ✅ 自动重命名为emby可识别格式
- ✅ 支持自定义重映射，提高重命名准确性
- ✅ 支持多种RSS订阅源
- ✅ 种子文件转磁力链接功能
- ✅ Telegram机器人助手

### 技术栈
- **异步框架**: asyncio, aiohttp
- **网络请求**: aiohttp, feedparser, beautifulsoup4
- **AI集成**: OpenAI, Google GenAI, DeepSeek
- **数据处理**: pyyaml, aiosqlite, bencodepy
- **日志记录**: loguru
- **消息通知**: python-telegram-bot
- **测试框架**: pytest, pytest-asyncio
- **代码质量**: ruff, black

## 核心架构

项目采用模块化设计，主要分为以下几个核心模块：

```
src/alist_mikananirss/
├── main.py              # 主程序入口
├── alist/               # Alist集成模块
├── bot/                 # 机器人模块
├── common/              # 通用配置和数据库
├── core/                # 核心业务逻辑
├── extractor/           # 信息提取模块
├── utils/               # 工具函数
└── websites/            # 网站解析模块
```

## 功能模块详解

### 1. RSS监控模块 (`core/rss_monitor.py`)

**职责**: 监控RSS订阅源，发现新资源

**核心功能**:
- 支持多个RSS订阅源
- 支持多种动漫网站（蜜柑计划、动漫花园、ACG.RIP等）
- 过滤机制（正则表达式、预定义过滤器）
- 防重复下载机制
- 种子转磁力链接

**关键类**: `RssMonitor`

### 2. 资源提取模块 (`extractor/`)

**职责**: 从资源标题中提取动漫信息

**子模块**:
- `extractor.py`: 基础提取器
- `llm_extractor.py`: LLM智能提取器
- `regex.py`: 正则表达式提取器
- `llm/`: LLM提供者（OpenAI、Google、DeepSeek）

**核心功能**:
- 动漫名称识别
- 季数和集数提取
- 字幕组识别
- 画质和语言信息提取
- TMDB集成获取动漫信息

### 3. 重命名模块 (`core/renamer.py`)

**职责**: 将下载的文件重命名为Emby可识别的格式

**核心功能**:
- 自定义重命名格式
- 版本控制（v1, v2等）
- 文件夹结构管理
- 重映射机制（修正识别错误）

### 4. Alist集成模块 (`alist/`)

**职责**: 与Alist服务器交互

**核心功能**:
- Alist API客户端
- 离线下载任务管理（支持qBittorrent和Aria2）
- 文件系统操作
- 下载任务状态监控

**关键类**: `Alist`, `AlistDownloadTask`

### 5. 通知系统 (`core/notification_sender.py`, `bot/`)

**职责**: 发送下载通知

**支持的机器人**:
- PushPlus机器人
- Telegram机器人
- 基础通知机器人接口

**核心功能**:
- 下载成功/失败通知
- 资源更新通知
- 自定义通知内容

### 6. 数据库管理 (`common/database.py`)

**职责**: 数据持久化

**核心功能**:
- SQLite数据库（异步）
- 已下载资源记录
- 防重复机制
- 数据库迁移支持

**关键类**: `SubscribeDatabase`

### 7. 机器人助手 (`core/bot_assistant.py`)

**职责**: 提供交互式机器人助手

**核心功能**:
- Telegram机器人集成
- 手动触发RSS检查
- 系统状态查询
- 配置管理

### 8. 网站解析模块 (`websites/`)

**职责**: 解析不同动漫网站的RSS和页面

**支持的网站**:
- 蜜柑计划 (Mikanani)
- 动漫花园 (DMHY)
- ACG.RIP
- 通用RSS源

**核心功能**:
- RSS解析
- 页面信息提取
- 资源链接获取
- 网站特定适配

### 9. 工具模块 (`utils/`)

**职责**: 提供通用工具函数

**核心功能**:
- 磁力链接转换
- TMDB API客户端
- 单例模式支持
- 通用工具函数

## 工作流程

### 主要工作流程

1. **初始化阶段**
   - 加载配置文件
   - 初始化数据库
   - 连接Alist服务器
   - 设置LLM提供者
   - 配置通知系统

2. **监控循环**
   ```
   while True:
       1. 获取RSS订阅更新
       2. 过滤新资源
       3. 提取资源信息
       4. 应用重映射规则
       5. 创建下载任务
       6. 等待间隔时间
   ```

3. **下载处理**
   - 通过Alist API创建离线下载任务
   - 监控下载状态
   - 下载完成后重命名文件
   - 发送通知

4. **信息提取流程**
   ```
   原始标题 → 正则提取 → LLM优化 → TMDB验证 → 最终信息
   ```

### 数据流

```
RSS源 → 资源发现 → 信息提取 → 过滤去重 → 下载任务 → Alist下载 → 重命名 → 通知
```

## 配置和扩展

### 配置文件结构
```yaml
common:          # 通用配置
alist:           # Alist配置
mikan:           # RSS订阅配置
rename:          # 重命名配置
notification:    # 通知配置
bot_assistant:   # 机器人助手配置
```

### 扩展能力

1. **新的RSS源支持**: 通过继承`Website`基类添加
2. **新的LLM提供者**: 通过继承`LLMProvider`基类添加
3. **新的通知渠道**: 通过继承`NotificationBot`基类添加
4. **新的提取器**: 通过继承`ExtractorBase`基类添加

### 环境要求

- **Alist版本**: >=3.42.0
- **Python版本**: >=3.11
- **网络支持**: 需要访问相关动漫网站和AI服务

## 开发和测试

### 测试结构
```
tests/
├── alist/         # Alist相关测试
├── bot/           # 机器人相关测试
├── common/        # 通用功能测试
├── core/          # 核心业务逻辑测试
├── extractor/     # 提取器测试
└── websites/      # 网站解析测试
```

### 运行方式
1. **源码运行**: `python -m alist_mikananirss --config config.yaml`
2. **Docker运行**: 使用提供的Dockerfile
3. **pip安装**: `pip install alist-mikananirss`

## 项目特点

1. **高度模块化**: 各模块职责清晰，便于维护和扩展
2. **异步设计**: 全异步架构，性能优异
3. **智能提取**: 结合正则表达式和LLM进行信息提取
4. **多源支持**: 支持多个RSS源和动漫网站
5. **丰富的通知**: 支持多种通知渠道
6. **容错性强**: 完善的错误处理和重试机制
7. **配置灵活**: 丰富的配置选项和自定义能力

## 未来发展方向

1. 支持更多的动漫网站
2. 增强AI提取能力
3. 添加更多通知渠道
4. 优化重命名算法
5. 增加Web管理界面
6. 支持批量操作
7. 增强监控和统计功能

use uv instead of pip

测试用webdav配置：
- url:http://127.0.0.1:5244/dav
- username:admin
- passwd:1234
- path:/115/TV/彻夜之歌 第二季

python fix_nested_structure_webdav_improved.py --url http://127.0.0.1:5244/dav --username admin --password 1234 --dir "/115/TV/彻夜之歌 第二季" --verbose
