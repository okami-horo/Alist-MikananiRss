"""
FastAPI应用主服务器

提供WebUI功能的HTTP服务器入口，集成所有API路由和中间件配置。
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..common.config.config import AppConfig, ConfigManager
from .api import (
    ADMIN_API_ROUTERS,
    LEGACY_API_ROUTERS,
    PUBLIC_API_ROUTERS,
    register_api_routes,
)
from .services import refresh_service_registry
from .services.system_service import get_system_service, system_service

logger = logging.getLogger(__name__)
def _get_package_root() -> Path:
    """Return the base path for bundled resources.

    When running as a PyInstaller onefile binary, resources are extracted
    into the temporary directory referenced by ``sys._MEIPASS``. We bundle
    ``static`` and ``templates`` under ``alist_mikananirss/webui``.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass) / "alist_mikananirss" / "webui"
        return base
    return Path(__file__).resolve().parent


PACKAGE_ROOT = _get_package_root()
STATIC_DIR = PACKAGE_ROOT / "static"
TEMPLATE_DIR = PACKAGE_ROOT / "templates"


def _resolve_config_path() -> Path:
    return Path(os.environ.get("ALIST_MIKAN_CONFIG", "config.yaml"))


def _load_app_config(config_path: Path) -> AppConfig:
    manager = ConfigManager()
    try:
        return manager.load_config(config_path)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to load config from %s, falling back to defaults", config_path)
        return AppConfig()


def _default_origins(webui_cfg) -> list[str]:
    if getattr(webui_cfg, "cors_origins", None):
        return list(webui_cfg.cors_origins)
    port = getattr(webui_cfg, "port", 8080)
    return [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]


def _allowed_hosts(webui_cfg) -> list[str]:
    hosts = set(getattr(webui_cfg, "allowed_hosts", []) or [])
    host_value = getattr(webui_cfg, "host", None)
    port_value = getattr(webui_cfg, "port", None)
    if host_value in {"0.0.0.0", "0.0.0.0/0", "::"} or "*" in hosts:
        hosts = {"*"}
    elif host_value:
        hosts.add(host_value)
        if port_value:
            hosts.add(f"{host_value}:{port_value}")
    if port_value:
        hosts.update({f"localhost:{port_value}", f"127.0.0.1:{port_value}"})
    hosts.update({"localhost", "127.0.0.1"})
    return list(hosts or {"localhost"})


def _extract_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def build_auth_dependency(app: FastAPI):
    async def require_auth(request: Request):
        cfg = getattr(app.state, "webui_config", None)
        if not cfg or not getattr(cfg, "auth_enabled", False):
            return
        expected = getattr(cfg, "secret_key", "")
        token = (
            request.headers.get(getattr(cfg, "auth_header", "X-API-Key"))
            or request.headers.get("X-API-Key")
            or _extract_bearer_token(request.headers.get("Authorization"))
            or request.cookies.get("webui_token")
        )
        if not expected or token != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")

    return require_auth


def _template_context(request: Request) -> dict[str, object]:
    webui_cfg = getattr(request.app.state, "webui_config", None)
    auth_header = getattr(webui_cfg, "auth_header", "X-API-Key") if webui_cfg else "X-API-Key"
    return {
        "request": request,
        "api_token": getattr(request.app.state, "webui_auth_token", ""),
        "auth_header": auth_header,
    }


def _attach_auth_cookie(app: FastAPI, response: Response) -> None:
    cfg = getattr(app.state, "webui_config", None)
    token = getattr(app.state, "webui_auth_token", "")
    if not cfg or not getattr(cfg, "auth_enabled", False) or not token:
        return
    response.set_cookie(
        "webui_token",
        token,
        httponly=True,
        samesite="lax",
        secure=not getattr(cfg, "debug", False),
        max_age=getattr(cfg, "session_timeout", 3600),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时执行
    logger.info("WebUI server starting up...")
    if getattr(app.state, "auto_start_monitor", False):
        result = await system_service.start_system()
        if not result.get("success"):
            logger.warning("Failed to auto-start subscription service: %s", result.get("message"))
    yield
    # 关闭时执行
    logger.info("WebUI server shutting down...")
    try:
        await system_service.stop_system()
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to stop subscription service during shutdown")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    # 创建FastAPI应用
    app = FastAPI(
        title="Alist-MikananiRss WebUI",
        description="动漫下载管理系统Web界面",
        version="0.5.5",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan
    )

    config_path = _resolve_config_path()
    app_config = _load_app_config(config_path)
    webui_cfg = app_config.webui
    os.environ.setdefault("ALIST_MIKAN_CONFIG", str(config_path))
    app.state.config_path = config_path
    app.state.app_config = app_config
    app.state.webui_config = webui_cfg
    app.state.webui_auth_token = webui_cfg.secret_key if webui_cfg.auth_enabled else ""
    app.state.webui_use_cdn = bool(getattr(webui_cfg, "use_cdn_assets", False))
    app.state.auto_start_monitor = bool(getattr(webui_cfg, "auto_start_monitor", False))
    get_system_service(config_path)

    # 添加中间件
    setup_middleware(app)

    # 添加路由
    setup_api_routes(app)

    # 添加静态文件服务
    setup_static_files(app)

    # 设置模板引擎
    templates = setup_templates(app)
    app.state.templates = templates

    return app


def setup_middleware(app: FastAPI) -> None:
    """配置中间件"""
    webui_cfg = getattr(app.state, "webui_config", None)
    allowed_origins = _default_origins(webui_cfg) if webui_cfg else ["http://127.0.0.1:8080"]
    allowed_hosts = _allowed_hosts(webui_cfg) if webui_cfg else ["localhost", "127.0.0.1"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts,
    )


def setup_api_routes(app: FastAPI) -> None:
    """配置API路由并刷新服务注册表"""

    refresh_service_registry()
    auth_dependency = build_auth_dependency(app)
    register_api_routes(app, routers=PUBLIC_API_ROUTERS)
    register_api_routes(app, routers=ADMIN_API_ROUTERS, dependencies=[Depends(auth_dependency)])
    register_api_routes(app, routers=LEGACY_API_ROUTERS, dependencies=[Depends(auth_dependency)])


def setup_static_files(app: FastAPI) -> None:
    """配置静态文件服务"""
    if STATIC_DIR.exists():
        try:
            app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        except RuntimeError:
            logger.exception("Failed to mount static directory: %s", STATIC_DIR)
    else:
        logger.warning("Static files directory not found: %s", STATIC_DIR)


def setup_templates(app: FastAPI) -> Optional[Jinja2Templates]:
    """配置模板引擎"""
    if TEMPLATE_DIR.exists():
        try:
            return Jinja2Templates(directory=str(TEMPLATE_DIR))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to load templates directory %s: %s", TEMPLATE_DIR, exc)
            return None
    logger.error("Template directory not found: %s", TEMPLATE_DIR)
    return None


# 创建应用实例
app = create_app()

FAVICON_PATH = STATIC_DIR / "images" / "favicon.ico"


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """根路径，直接返回仪表盘页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    response = templates.TemplateResponse("dashboard.html", _template_context(request))
    _attach_auth_cookie(app, response)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """仪表板页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    response = templates.TemplateResponse("dashboard.html", _template_context(request))
    _attach_auth_cookie(app, response)
    return response


@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request):
    """日志查看页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    response = templates.TemplateResponse("logs.html", _template_context(request))
    _attach_auth_cookie(app, response)
    return response


@app.get("/config", response_class=HTMLResponse)
async def config(request: Request):
    """配置管理页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    response = templates.TemplateResponse("config.html", _template_context(request))
    _attach_auth_cookie(app, response)
    return response


@app.get("/webdav/manual", response_class=HTMLResponse)
async def webdav_manual(request: Request):
    """WebDAV手动修复页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    response = templates.TemplateResponse("webdav_manual.html", _template_context(request))
    _attach_auth_cookie(app, response)
    return response


@app.get("/health")
async def health_check():
    """健康检查端点"""
    status = await system_service.get_system_status()
    return {
        "status": "healthy",
        "service": "webui",
        "subscription": status.status,
        "uptime": status.uptime,
        "last_error": status.last_error,
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """网站图标"""
    if FAVICON_PATH.exists():
        return FileResponse(FAVICON_PATH)
    return Response(status_code=404)


if __name__ == "__main__":
    import uvicorn

    # 开发模式运行
    uvicorn.run(
        "src.alist_mikananirss.webui.server:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
