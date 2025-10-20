"""
FastAPI应用主服务器

提供WebUI功能的HTTP服务器入口，集成所有API路由和中间件配置。
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from alist_mikananirss.webui.api.system import router as system_router
from alist_mikananirss.webui.api.logs import router as logs_router
from alist_mikananirss.webui.api.config import router as config_router
from alist_mikananirss.webui.api.webdav import router as webdav_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时执行
    logger.info("WebUI server starting up...")
    yield
    # 关闭时执行
    logger.info("WebUI server shutting down...")


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

    # 添加中间件
    setup_middleware(app)

    # 添加路由
    setup_routers(app)

    # 添加静态文件服务
    setup_static_files(app)

    # 设置模板引擎
    templates = setup_templates(app)
    app.state.templates = templates

    return app


def setup_middleware(app: FastAPI) -> None:
    """配置中间件"""
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 受信任主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # 生产环境应该限制具体主机
    )


def setup_routers(app: FastAPI) -> None:
    """配置路由"""
    # API路由
    app.include_router(
        system_router,
        prefix="/api/system",
        tags=["System"]
    )

    app.include_router(
        logs_router,
        prefix="/api/logs",
        tags=["Logs"]
    )

    app.include_router(
        config_router,
        prefix="/api/config",
        tags=["Configuration"]
    )

    app.include_router(
        webdav_router,
        prefix="/api/webdav",
        tags=["WebDAV"]
    )


def setup_static_files(app: FastAPI) -> None:
    """配置静态文件服务"""
    try:
        # 挂载静态文件
        app.mount("/static", StaticFiles(directory="src/alist_mikananirss/webui/static"), name="static")
    except RuntimeError:
        # 静态文件目录不存在时的处理
        logger.warning("Static files directory not found, static file serving disabled")


def setup_templates(app: FastAPI) -> Optional[Jinja2Templates]:
    """配置模板引擎"""
    try:
        templates = Jinja2Templates(directory="src/alist_mikananirss/webui/templates")
        return templates
    except Exception as e:
        logger.error(f"Template directory not found: {e}")
        return None


# 创建应用实例
app = create_app()

FAVICON_PATH = Path(__file__).resolve().parent / "static" / "images" / "favicon.ico"


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """根路径，直接返回仪表盘页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """仪表板页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request):
    """日志查看页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/config", response_class=HTMLResponse)
async def config(request: Request):
    """配置管理页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/webdav/manual", response_class=HTMLResponse)
async def webdav_manual(request: Request):
    """WebDAV手动修复页面"""
    templates = app.state.templates
    if not templates:
        return HTMLResponse(content="Template engine not available", status_code=500)

    return templates.TemplateResponse("webdav_manual.html", {"request": request})


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "webui"}


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