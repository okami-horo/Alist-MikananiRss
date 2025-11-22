# Quickstart: 001-webui-backend-refactor

本指南说明在重构后的版本中，如何使用 WebUI 驱动后端服务完成日常操作。假定你已经安装好 **Python 3.11+**，并使用 **uv** 管理依赖。

## 1. 安装依赖（使用 uv）

```bash
# 在仓库根目录
uv sync  # 安装运行与开发依赖（基于 pyproject.toml 和 uv.lock）
```

> 不再推荐直接使用 `pip install -r requirements.txt`，统一使用 `uv` 管理环境和锁文件。

## 2. 启动 WebUI 后端服务

WebUI 作为一个长期运行的 FastAPI 应用，通过 `alist-mikananirss-webui` 脚本或模块入口启动。

### 2.1 通过脚本启动（推荐）

```bash
# 仓库根目录
uv run alist-mikananirss-webui --host 0.0.0.0 --port 8080
```

关键参数：

- `--host`: 绑定地址，家庭/NAS 场景通常用 `0.0.0.0` 方便局域网访问。
- `--port`: HTTP 端口，默认为 `8080`。
- `--reload`: （可选）开发模式下启用自动重载。
- `--log-level`: 传递给 uvicorn 的日志级别（`info/debug` 等）。

### 2.2 通过模块入口启动（调试用）

```bash
uv run python -m alist_mikananirss.webui -- --host 0.0.0.0 --port 8080
```

## 3. 首次访问与配置向导

1. 启动后端服务后，在浏览器访问：
   - `http://<你的主机 IP>:8080/` 或 `http://localhost:8080/`
2. 首次访问如检测到缺少有效配置，WebUI 会进入“配置引导模式”：
   - 在“配置”页面填写：
     - Alist 地址和 Token（例如 `http://127.0.0.1:5244`）
     - RSS 订阅 URL 列表（蜜柑计划等）
     - 基础运行参数（如 `interval_time`、`log_level`）
3. 点击“测试配置”按钮：
   - 后端会调用 `/api/config/test`，实际访问 Alist 与 RSS 源，返回结构化的连通性结果。
4. 测试通过后“保存配置”：
   - WebUI 通过 `/api/config/save` 写入 YAML 配置文件，并自动创建备份；
   - 后续所有运行与重启都基于该配置。

## 4. 通过 WebUI 控制订阅系统

在“仪表盘”页面，你可以：

1. 查看当前系统状态：
   - `/api/system/status` 提供运行状态、版本、CPU/内存/磁盘等关键指标。
2. 启动订阅循环：
   - 点击“启动订阅”按钮（调用 `/api/system/start`）。
3. 停止订阅循环：
   - 点击“停止订阅”按钮（调用 `/api/system/stop`）。
4. 需要时“重启订阅”：
   - 调用 `/api/system/restart`，在配置更新后特别有用。

整个过程中，后端进程保持常驻，只有订阅循环本身被启停。

## 5. 日志与问题排查

WebUI 提供完整的日志浏览与搜索功能：

- **日志文件列表**：`/api/logs/files`，供前端展示可选日志文件。
- **查看内容**：通过 `/api/logs/content?file=...&limit=...` 分页查看，并支持 `level`、`search` 过滤。
- **最近活动**：`/api/logs/recent` 用于在仪表盘展示最近关键事件。
- **关键字搜索**：`/api/logs/search?q=...&level=...` 支持快速定位问题场景。
- **流式查看**：`/api/logs/stream` 以 SSE 形式尾随日志文件，适合实时观察长任务执行情况。

建议：

- 在调试 WebDAV 修复或下载异常时，先在“日志”页面筛选 ERROR/WARNING 级别记录。

## 6. WebDAV 嵌套修复（手动任务）

WebUI 暴露了一个 WebDAV 手动修复接口：

- 端点：`POST /api/webdav/manual-fix`
- 典型参数：
  - `path`: 需要修复的远程路径，例如 `/115/TV/彻夜之歌 第二季`；
  - `execute_mode`: `false` 表示预览（dry-run），`true` 表示实际执行；
  - `recursive_scan`: 是否递归扫描子目录；
  - `conflict_strategy`: `"skip" | "rename" | "overwrite"`。

WebUI 页面通常提供“预览”与“执行”两种按钮，对应上述参数组合，并在结果中展示总条目数、成功/失败统计等。

## 7. 运行测试（WebUI 相关）

确保依赖已通过 `uv sync` 安装后，可以在仓库根目录运行：

```bash
# 仅跑 WebUI 测试
uv run pytest tests/webui -q

# 或运行整个测试套件
uv run pytest -q
```

WebUI 相关测试覆盖：

- `tests/webui/test_services.py`：系统/日志/配置服务逻辑；
- `tests/webui/test_api.py`：FastAPI 路由与响应格式；
- `tests/webui/test_integration.py`：端到端使用场景（仪表盘、日志、配置、故障排查等）。

## 8. 典型部署建议

- 使用 Docker / systemd 将 `alist-mikananirss-webui` 进程以服务方式长期运行；
- 通过反向代理（如 Nginx、Caddy）实现访问控制与 HTTPS；
- 对“配置修改 / 运维操作”页面提供额外的访问保护，只读查看可以更开放一些。
