# Research: 001-webui-backend-refactor

## 1. 后端 HTTP 框架选择

- **Decision**: 使用 FastAPI 作为统一的 HTTP 后端框架。
- **Rationale**:
  - 代码中已有成熟的 FastAPI 集成（`alist_mikananirss.webui.server`、`api/*.py` 和 `tests/webui/test_api.py` 等），包括路由、中间件、模板和静态资源挂载。
  - 与现有异步栈（aiohttp、aiosqlite 等）兼容良好，生态完善（Pydantic、OpenAPI、依赖注入等）。
  - 集成测试已经依赖 `fastapi.testclient`，继续沿用可降低迁移与维护成本。
- **Alternatives considered**:
  - **aiohttp.web**: 更贴近底层的 HTTP 服务器，灵活但需要自行处理更多样板和生态集成；当前项目已拥有 FastAPI 代码和测试，切换会引入不必要的重写成本与复杂度。

## 2. 前端技术栈选择

- **Decision**: 继续采用 Jinja2 模板 + 原生 HTML/JS/CSS 的服务端渲染 WebUI，不在当前特性中引入 React/Vite 等重型 SPA 框架。
- **Rationale**:
  - 现有 `templates/` 与 `static/` 目录已经提供了仪表盘、日志、配置、WebDAV 手动修复等页面，配合 FastAPI 的模板渲染即可满足当前用户故事（US1–US3）。
  - 部署目标主要是 NAS / 个人服务器，优先考虑“简单部署 + 易维护”，避免在本阶段增加 Node 构建链路与复杂前端栈。
  - 性能目标（SC-002：95% 请求 < 2s）对前端框架无强制要求，主要取决于后端 API 与日志/任务查询实现质量。
- **Alternatives considered**:
  - **React + Vite + TailwindCSS**: 适合复杂交互和长远扩展，为 SPA 提供良好的 DX，但会引入新的工具链（Node、打包配置、路由状态管理），增加上手成本和 CI/CD 复杂度；在当前“单机、自托管”场景下收益有限。
  - **其他轻量前端框架（如 HTMX、Alpine.js）**: 可以提升局部交互体验，但不属于本次重构的必要条件，可在后续迭代中按需引入。

## 3. WebUI 测试策略

- **Decision**: 以 pytest + pytest-asyncio + fastapi.testclient 为主，覆盖 WebUI 的 API 与集成行为；不在当前特性中引入浏览器级 E2E 框架。
- **Rationale**:
  - 现有 `tests/webui/test_api.py`、`test_services.py`、`test_integration.py` 已经使用 pytest 和 FastAPI 测试客户端，对系统状态、日志、配置等核心路径提供端到端级别的 HTTP 覆盖。
  - FastAPI TestClient 能够在不启动真实服务器的前提下完成绝大多数 WebUI 功能验证，更适合快速、稳定的 CI 运行。
  - 浏览器级 E2E（Playwright/Selenium）需要独立运行环境、浏览器驱动与更复杂的 CI 配置，在当前项目体量下维护成本偏高。
- **Alternatives considered**:
  - **Playwright / Selenium 等浏览器自动化**: 可以验证真实 DOM 与样式交互，但测试编写和维护成本高，对当前以 API 为主的 WebUI 来说性价比有限，暂定为后续增强选项。
  - **仅单元测试，不做端到端 API 测试**: 会削弱对整体流程的保障，违背宪章中“Integration Testing”的要求，因此被否决。
