# Tasks: 纯前后端重构（WebUI 驱动后端服务）

**Input**: Design documents from `/specs/001-webui-backend-refactor/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 为 WebUI 驱动的后端服务梳理基础工程设置与运行方式，统一使用 uv 和 FastAPI WebUI 入口。

- [x] T001 更新项目脚本与文档以推荐使用 `uv run alist-mikananirss-webui` 启动 WebUI 服务（pyproject.toml, specs/001-webui-backend-refactor/quickstart.md）
- [x] T002 [P] 校验并整理 WebUI 相关依赖（fastapi, uvicorn, jinja2, psutil 等）版本范围与分组（pyproject.toml）
- [x] T003 [P] 在 README 中新增“WebUI 驱动模式”简介和快速启动指引（README.md）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 建立 WebUI 后端运行所需的核心基础设施，包括 HTTP 服务器、API 路由、中间件和日志目录等；完成后方可按用户故事实现具体功能。

**⚠️ CRITICAL**: 完成本阶段前不要开始任一用户故事实现。

- [x] T004 配置和整理 FastAPI WebUI 服务器入口，包括应用创建、路由挂载、中间件和模板/静态目录（src/alist_mikananirss/webui/server.py）
- [x] T005 [P] 确认并修正 WebUI 模板与静态资源目录结构（src/alist_mikananirss/webui/templates, src/alist_mikananirss/webui/static）
- [x] T006 [P] 为 WebUI 后端应用配置统一的日志目录与日志格式，确保 LogService 可在默认 `log/` 目录正常工作（src/alist_mikananirss/webui/services/log_service.py）
- [x] T007 建立 WebUI 服务层聚合导出（SystemService、LogService、ConfigService 等），方便 API 层统一引入（src/alist_mikananirss/webui/services/__init__.py）
- [x] T008 配置 WebUI API 模块的统一导出与路由注册（system/logs/config/webdav）（src/alist_mikananirss/webui/api/__init__.py）
- [x] T009 [P] 为 WebUI 后端补充或整理基础 API/服务层单元测试骨架，确保 tests/webui 目录结构完整，并作为后续实现/重构前的最小测试基线（tests/webui/test_api.py）
  > 阻塞：`uv run pytest tests/webui/test_api.py -q` 需构建 `psutil==5.9.8`，当前容器缺少 `gcc/python3-dev` 等构建依赖，等待环境补齐后再执行。

**Checkpoint**: WebUI 后端 FastAPI 应用可通过 `uv run alist-mikananirss-webui` 启动，暴露基础健康检查 `/health` 与空白仪表盘页面。

---

## Phase 3: User Story 1 - 通过浏览器管理订阅系统的日常运行 (Priority: P1) 🎯 MVP

**Goal**: 用户仅通过浏览器访问 WebUI 即可查看系统运行状态，并能在页面上启动/停止/重启订阅系统，无需登录服务器执行 CLI。

**Independent Test**: 在一台全新环境中，仅通过浏览器访问 WebUI，完成一次“启动订阅→查看状态变化→停止订阅”的完整闭环，全程不执行项目 CLI 子命令。

### Implementation for User Story 1

- [x] T014 [US1] 校准并扩充 WebUI 系统 API 测试用例，覆盖状态查询与启停/重启路径，在实现或重构 SystemService 与 system API 前先锁定这些行为的预期（Test-First）（tests/webui/test_api.py）
- [x] T015 [US1] 在 WebUI 集成测试中增加“仅通过浏览器控制订阅系统”的端到端场景，在实现仪表盘模板/脚本与 SystemService 逻辑前先编写并运行预期失败的用例以驱动实现（tests/webui/test_integration.py）
- [x] T010 [P] [US1] 对 SystemService 的进程检测与启动/停止逻辑进行梳理，确保能正确识别主订阅进程并返回资源占用信息（src/alist_mikananirss/webui/services/system_service.py）
- [x] T011 [P] [US1] 完善 `/api/system/status`、`/api/system/start`、`/api/system/stop`、`/api/system/restart` 的路由与返回结构，与 openapi 合约保持一致（src/alist_mikananirss/webui/api/system.py）
- [x] T012 [US1] 在仪表盘模板中接入系统状态展示与启停按钮交互（src/alist_mikananriss/webui/templates/dashboard.html）
- [x] T013 [P] [US1] 为仪表盘页面编写前端脚本，请求系统状态并轮询刷新，同时绑定启停按钮到对应 API（src/alist_mikananirss/webui/static/js/dashboard.js）

**Checkpoint**: 通过浏览器完成“查看状态 + 启停订阅”的闭环，相关 API 和页面都有测试覆盖。

---

## Phase 4: User Story 2 - 通过 WebUI 完成系统的初始配置与重配置 (Priority: P1)

**Goal**: 用户在无现成配置文件的环境中，仅通过 WebUI 填写并保存配置，即可完成系统初始化，并可在 WebUI 中直接启动订阅。

**Independent Test**: 删除或重命名原有 `config.yaml` 后，仅访问 WebUI 配置页面即可完成配置创建、校验及保存，然后直接从仪表盘控制订阅运行。

### Implementation for User Story 2

- [x] T020 [US2] 扩充配置 API 测试用例，覆盖无配置文件、配置损坏、保存时备份与验证失败的路径，在实现或重构 ConfigService 与配置 API 前锁定这些行为的预期（Test-First）（tests/webui/test_api.py）
- [x] T021 [US2] 在 WebUI 集成测试中添加“首次访问进入引导配置模式并完成保存”的端到端场景，在实现配置页面与后端行为前先通过失败用例驱动实现与重构（tests/webui/test_integration.py）
- [x] T016 [P] [US2] 梳理并补充 ConfigService 的默认配置、加载/合并/备份策略，保证缺失或损坏配置文件时能自动回退到安全默认值（src/alist_mikananirss/webui/services/config_service.py）
- [x] T017 [P] [US2] 确认 `/api/config/current`、`/api/config/validate`、`/api/config/save`、`/api/config/schema`、`/api/config/test` 行为与 spec 中 FR-004 描述保持一致（src/alist_mikananirss/webui/api/config.py）
- [x] T018 [US2] 实现/完善配置页面表单结构，将 schema 映射到表单控件并支持增删 RSS 订阅与过滤规则（src/alist_mikananirss/webui/templates/config.html）
- [x] T019 [P] [US2] 为配置页面编写前端脚本：加载当前配置、执行“测试配置”调用、展示验证结果和外部连通性状态（src/alist_mikananirss/webui/static/js/config.js）

**Checkpoint**: 在没有 `config.yaml` 的环境中，用户可以通过 WebUI 完成配置创建、校验、保存与连通性测试。

---

## Phase 5: User Story 3 - 通过 WebUI 诊断问题并执行维护操作 (Priority: P2)

**Goal**: 当下载或重命名异常时，维护者可以在 WebUI 中查看过滤后的日志，并从同一界面触发 WebDAV 嵌套修复任务（预览/执行），获取结构化结果反馈。

**Independent Test**: 通过构造包含错误日志的日志文件和模拟 WebDAV 目录问题，仅使用 WebUI 即可完成“筛选错误日志→触发 WebDAV 修复（预览 + 执行）→查看统计结果”的完整流程。

### Implementation for User Story 3

- [x] T022 [P] [US3] 完善 LogService 的日志解析、过滤与分页能力，支持 level/search 参数并在文件缺失时给出清晰错误（src/alist_mikananirss/webui/services/log_service.py）
- [x] T023 [P] [US3] 校准 `/api/logs/files`、`/api/logs/content`、`/api/logs/recent`、`/api/logs/search`、`/api/logs/stream` 的行为与 openapi 合约和快速开始文档（src/alist_mikananirss/webui/api/logs.py）
- [x] T024 [US3] 实现/完善日志页面模板，包括日志文件选择、级别和关键字过滤、最近活动区域（src/alist_mikananirss/webui/templates/logs.html）
- [x] T025 [P] [US3] 为日志页面编写前端脚本，集成分页加载、搜索与 SSE 实时尾随接口（src/alist_mikananirss/webui/static/js/logs.js）
- [x] T026 [P] [US3] 实现 WebDAV 手动修复服务封装，负责调用底层修复脚本/逻辑并返回结构化结果；对于可能长时间运行的修复过程，以 Job 形式管理并对外暴露 Job 状态（src/alist_mikananirss/webui/services/webdav_service.py）
- [x] T027 [US3] 检查并完善 `/api/webdav/manual-fix` 路由的请求校验、错误映射和响应模型，使其在长任务场景下返回 Job ID，并提供基于 Job ID 的状态查询接口以满足 FR-008 要求（src/alist_mikananirss/webui/api/webdav.py）
- [x] T028 [US3] 为 WebDAV 手动修复页面实现表单与结果展示，包括预览与实际执行模式，并在 UI 中展示 Job 状态与最终结果（src/alist_mikananirss/webui/templates/webdav_manual.html）
- [x] T029 [US3] 在 WebUI 集成测试中增加“WebDAV 嵌套修复（预览+执行）”场景覆盖，验证长时间运行的修复任务以 Job 形式返回 Job ID 且可通过轮询接口查询状态，并优先通过该用例驱动 Job 管理与 UI/API 行为的实现（Test-First）（tests/webui/test_integration.py）
- [x] T039 [P] [US3] 根据 data-model 中 `WebdavManualFixJob` 定义梳理并实现 WebUI 层 Job 模型与状态存储（创建/运行中/完成/失败），并为后续其他长时间操作复用该 Job 管理机制（src/alist_mikananirss/webui/services/webdav_service.py）

**Checkpoint**: 维护者可以通过 WebUI 日志页面和 WebDAV 页面完成问题排查与目录修复，相关路径有自动化测试覆盖。

---

## Phase 6: User Story 4 - 在多终端上安全访问与使用 (Priority: P3)

**Goal**: 多终端（PC/平板/手机）可并行访问 WebUI 查看状态和日志，敏感操作（配置修改、启停订阅、WebDAV 修复）可以通过简单的访问控制或部署层策略进行保护。

**Independent Test**: 在同一局域网内用两台设备访问 WebUI，一台执行订阅启停和配置修改，另一台只读查看状态与日志，验证状态一致性与访问控制策略生效。

### Implementation for User Story 4

- [x] T032 [US4] 在 WebUI 集成测试中增加多终端状态一致性和只读访问的模拟场景，在调整路由前缀、访问控制与前端布局前先锁定多终端行为预期（Test-First）（tests/webui/test_integration.py）
- [x] T030 [P] [US4] 为只读视图和敏感操作 API 划分清晰的 URL 前缀与标签，便于反向代理基于路径做访问控制（src/alist_mikananirss/webui/server.py）
- [x] T031 [P] [US4] 在仪表盘和日志页面中优化响应式布局，确保在手机和平板上展示良好（src/alist_mikananirss/webui/templates/dashboard.html）
- [x] T033 [US4] 在 Quickstart 与 README 中补充关于反向代理/ACL 的推荐配置示例，说明只读与敏感操作路径的保护方式（specs/001-webui-backend-refactor/quickstart.md）

**Checkpoint**: WebUI 在不同终端展示正确，敏感操作的 API 路由约定清晰，文档中给出部署层访问控制建议。

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 跨用户故事的改进，包括错误处理、日志、性能和文档完善。

- [x] T034 [P] 梳理 WebUI 和核心模块中的关键日志点，确保重要操作（启停系统、保存配置、WebDAV 修复等）都有结构化日志（src/alist_mikananirss/webui/services/system_service.py）
- [x] T035 [P] 根据 SC-002 要求，对系统状态与日志接口进行简单性能分析和优化（如分页/limit 默认值），通过编写简易基准/压测脚本多次调用 `/api/system/status` 与日志接口并统计 95% 请求延迟，基于结果调整实现以避免一次请求加载过多数据（src/alist_mikananirss/webui/api/logs.py）
- [x] T036 审查并补充 WebUI 相关测试用例，覆盖主要错误路径与边界条件，例如：后端主进程未启动时 WebUI 行为、`config.yaml` 缺失或损坏时的引导配置模式、长时间运行的 WebDAV Job 执行中/失败/刷新页面后的状态恢复等（tests/webui/test_services.py）
- [x] T037 [P] 将 spec/plan/data-model/quickstart 与实际实现对齐，修正文档中已过期的接口或路径描述（specs/001-webui-backend-refactor/spec.md）
- [x] T038 在仓库根 README 中添加“WebUI 重构完成后的升级指南”，说明从旧 CLI 工作流迁移到 WebUI 的注意事项，并补充如何通过 WebUI 完成日常操作以减少登录 CLI 的需求，以及问题反馈/工单渠道说明，为 SC-003/SC-004 指标的后续统计留出空间（README.md）

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1) → 无前置依赖，可立即开始。
- Foundational (Phase 2) → 依赖 Phase 1 完成，阻塞所有用户故事实现。
- User Stories (Phase 3–6) → 依赖 Phase 2 完成后可按优先级或并行推进。
- Polish (Phase 7) → 依赖所有目标用户故事基本完成后执行。

### User Story Dependencies

- User Story 1 (P1) → 仅依赖基础设施，可最先实现，作为 MVP。
- User Story 2 (P1) → 依赖 US1 已能展示状态，配置完成后可立即联动订阅控制。
- User Story 3 (P2) → 依赖 US1 的系统状态和 US2 的配置持久化。
- User Story 4 (P3) → 依赖前述所有用户故事提供的只读/操作接口。

### Within Each User Story

- 在开始实现前，先为核心 API / 服务与端到端路径编写或更新会失败的测试用例，通过 Test-First 驱动实现与重构。
- 先打通服务层与 API，再联通模板和前端脚本。
- 每个用户故事的端到端路径（API + 页面）都应有至少一条集成测试，并作为行为基线长期维护。
- 实现完成后在本地按 Quickstart 中的命令启动 WebUI，并按各自的 Independent Test 描述进行人工验证。

---

## Parallel Execution Examples

- Setup & Foundational 阶段中所有标记为 [P] 的任务（如依赖整理、目录结构校验、日志目录配置）可以并行完成。
- US1 中 SystemService 改造（T010）与前端仪表盘脚本实现（T013）可并行推进，最终在 API 行为稳定后联调。
- US2 中 ConfigService 行为梳理（T016）与配置页面模板实现（T018）可并行，由集成测试（T021）在后期串联。
- US3 中日志与 WebDAV 路径（T022–T028）可在不同文件上平行开发，仅在集成测试时合流。

---

## Implementation Strategy

- 首先完成 Phase 1–2，确保 WebUI FastAPI 应用可稳定启动并暴露基础路由。
- 然后以 User Story 1 作为 MVP 完整实现并通过测试，再依次实现 US2, US3, US4。
- 每完成一个 User Story，都通过 tests/webui 下的测试和手动浏览器操作进行验证。
- 最后在 Phase 7 中统一收尾：对齐文档、完善日志与错误处理，并更新升级说明。
