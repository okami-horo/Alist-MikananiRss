# Implementation Plan: 纯前后端重构（WebUI 驱动后端服务）

**Branch**: `[001-webui-backend-refactor]` | **Date**: 2025-11-22 | **Spec**: `/specs/001-webui-backend-refactor/spec.md`
**Input**: Feature specification from `/specs/001-webui-backend-refactor/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

本特性将 Alist-MikananiRss 从“命令行驱动的长驻进程”重构为“HTTP API + WebUI 驱动的后端服务”。  
后端作为单体服务常驻运行，统一暴露订阅监控、配置管理、日志检索与 WebDAV 修复等 API；  
前端通过浏览器提供仪表盘、配置和运维界面，使典型用户在日常使用中不再需要直接调用 CLI。  
现有抓取 / 下载 / 重命名 / 通知等核心业务逻辑在保持行为兼容的前提下抽象为可复用的库，  
并通过新的 HTTP API 层与仍保留的 CLI 入口共享同一套核心实现。

## Technical Context

<!--
  Technical context for the web-backend refactor feature.
-->

**Language/Version**: Python 3.11+（沿用现有异步架构）  
**Primary Dependencies**:  
- 现有核心：asyncio、aiohttp、aiosqlite、feedparser、beautifulsoup4、bencodepy、loguru、python-telegram-bot 等  
- 后端 HTTP 框架：FastAPI（已在 `webui.server` 中使用）  
- 前端技术栈：Jinja2 模板 + 原生 HTML/JS/CSS（后续是否引入 SPA 框架视需求再评估）  
**Storage**: aiosqlite + SQLite 本地文件，沿用 `SubscribeDatabase` 等现有封装  
**Testing**: pytest + pytest-asyncio + fastapi.testclient，用于 API 与 WebUI 集成测试；暂不引入浏览器级 E2E 框架，未来根据需要再评估  
**Target Platform**: Linux 服务器 / NAS，Docker 部署为主，浏览器访问 WebUI（桌面 + 移动端）  
**Project Type**: web（单体后端 + 服务器渲染 WebUI），后端同时提供 API 与前端静态资源  
**Performance Goals**: 满足 SC-002：常规家庭/NAS 环境下，仪表盘状态与日志查询 95% 请求 < 2s  
**Constraints**: 单机部署、资源有限（内存 < 1–2GB，CPU 低核数）；不引入重型分布式组件，优先简化部署与运维  
**Scale/Scope**: 单用户 / 小规模家庭环境；RSS 源数量在几十级别，任务队列规模中等

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Scope**: 本特性聚焦于将现有核心能力（RSS 监控、下载/重命名、WebDAV 修复、配置管理、日志查看）统一通过长期运行的 HTTP 后端和 WebUI 暴露出来。  
  直接受影响模块：`core/rss_monitor.py`、`core/renamer.py`、`core/webdav_*`、`common/config`、`common/database`、`alist/` 集成、`webui/` 模块及其测试。  
  不在本次范围内的模块仅限于：新增网站解析器、LLM 提取器能力扩展等与“控制平面”无关的功能。
- **Architecture fit**: 保持单体 Python 3.11+ 异步架构，继续使用现有的 `src/alist_mikananirss` 包结构，在其中扩展 `webui` 模块而非引入独立微服务或额外运行时。HTTP 层基于 FastAPI，与现有异步模型（aiohttp、aiosqlite 等）兼容；不新增 Redis / 消息队列等分布式基础设施，符合“简单优先”的宪章要求。
- **Testing discipline**: 为 WebUI 引入系统级与模块级测试：  
  - 单元测试：`tests/webui/test_services.py` 覆盖新服务层逻辑；  
  - API 测试：`tests/webui/test_api.py` 使用 FastAPI 测试客户端覆盖主要端点（状态、启停、配置、日志、WebDAV 预览/执行等）；  
  - 集成测试：`tests/webui/test_integration.py` 通过真实配置和数据库、模拟 Alist/WebDAV 交互，验证从 HTTP 调用到核心逻辑的完整链路。  
  测试按 Test-First 原则推进，计划中不豁免核心路径测试。
- **Observability & failure handling**: 延续 `loguru` 日志体系，在新 HTTP 端点中：  
  - 对关键操作（启停订阅、保存配置、WebDAV 修复任务）记录结构化日志，包含调用方、目标资源、结果统计和错误摘要；  
  - 对外部依赖（Alist、WebDAV、RSS/TMDB、LLM）调用失败时提供明确的错误码与人类可读信息，并保证 HTTP 层返回可供前端展示的结构化错误；  
  - 为长时间任务统一以“任务 ID + 状态”形式暴露给前端，避免单请求长时间挂起。  
  监控和告警仍主要依赖外部部署环境，本特性仅负责良好日志与状态接口。
- **Breaking changes & migration**: 这是一次“交互方式”级别的重大变更：  
  - 旧有仅 CLI 驱动的工作流被 WebUI/HTTP API 所取代，但仍保留核心 CLI 入口作为库的包装层，以遵守“每个库有 CLI”原则；  
  - `config.yaml` 不再保证与旧版完全兼容，推荐用户通过 WebUI 重新创建配置，并在计划中明确文档化升级路径（包括：如何备份旧配置、如何在 WebUI 中导入/参考旧值）；  
  - 该特性将以语义化版本中的 MAJOR 或 MINOR 提升体现（例如 `0.5.x -> 0.6.0` 或之后），并在发布说明中标记为“有意识接受的行为变更”，满足宪章对版本化和 breaking change 的要求。

## Project Structure

### Documentation (this feature)

```text
specs/001-webui-backend-refactor/
├── spec.md              # Feature specification (user stories & requirements)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command; OpenAPI/HTTP contracts)
```

### Source Code (repository root)
<!--
  Concrete layout for this repository and this feature.
-->

```text
src/
└── alist_mikananirss/
    ├── main.py           # 现有主入口（CLI / 进程启动集成）
    ├── core/             # RSS 监控、重命名、通知等核心业务逻辑
    ├── common/           # 配置、数据库等通用基础设施
    ├── alist/            # 与 Alist / WebDAV 的集成
    ├── extractor/        # 标题解析、LLM/正则提取模块
    ├── utils/            # 工具函数与通用帮助
    ├── websites/         # 网站特定解析与 RSS 适配
    └── webui/            # 本特性主要改动区域：FastAPI WebUI + HTML 模板 + 静态资源

tests/
└── webui/               # WebUI 相关测试
    ├── test_api.py       # FastAPI API 层测试
    ├── test_services.py  # WebUI 服务层测试
    └── test_integration.py # WebUI 与核心模块的集成测试
```

**Structure Decision**: 采用单一 Python 包 `alist_mikananirss` 的结构，在其中通过 `webui` 子模块实现 WebUI 与 HTTP API；不拆分独立后端/前端仓库，由同一进程同时提供 API 与静态资源，符合“简单优先”和现有部署模式。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
