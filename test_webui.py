#!/usr/bin/env python3
"""
WebUI功能测试脚本

验证WebUI模块的导入和基本功能
"""

import sys
import os
import traceback
from pathlib import Path

# 添加src到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")

    try:
        # 测试模型导入
        from alist_mikananirss.webui.models import (
            LogLevel, SystemStatusEnum, SystemStatusInfo, LogEntry,
            ConfigValidationResult, ApiResponse
        )
        print("[OK] 模型导入成功")

        # 测试服务导入
        from alist_mikananirss.webui.services.system_service import SystemService
        from alist_mikananirss.webui.services.log_service import LogService
        from alist_mikananirss.webui.services.config_service import ConfigService
        print("[OK] 服务导入成功")

        # 测试API导入
        from alist_mikananirss.webui.api.system import router as system_router
        from alist_mikananirss.webui.api.logs import router as logs_router
        from alist_mikananirss.webui.api.config import router as config_router
        print("[OK] API路由导入成功")

        # 测试服务器导入
        from alist_mikananirss.webui.server import app
        print("[OK] FastAPI服务器导入成功")
        print(f"   - 应用标题: {app.title}")
        print(f"   - 版本: {app.version}")

        return True

    except Exception as e:
        print(f"❌ 导入失败: {e}")
        traceback.print_exc()
        return False

def test_models():
    """测试数据模型"""
    print("\n🔍 测试数据模型...")

    try:
        from alist_mikananirss.webui.models import (
            LogLevel, SystemStatusInfo, LogEntry, ConfigValidationResult
        )

        # 测试系统状态模型
        system_status = SystemStatusInfo(
            status="running",
            uptime=3600,
            version="0.5.5",
            python_version="3.11.0"
        )
        print("✅ 系统状态模型创建成功")

        # 测试日志条目模型
        log_entry = LogEntry(
            timestamp="2025-10-10T10:00:00",
            level=LogLevel.INFO,
            message="测试日志消息"
        )
        print("✅ 日志条目模型创建成功")

        # 测试配置验证结果模型
        validation_result = ConfigValidationResult(
            valid=True,
            message="配置验证通过"
        )
        print("✅ 配置验证结果模型创建成功")

        return True

    except Exception as e:
        print(f"❌ 模型测试失败: {e}")
        traceback.print_exc()
        return False

def test_config_integration():
    """测试配置集成"""
    print("\n🔍 测试配置集成...")

    try:
        from alist_mikananirss.common.config.basic import WebUIConfig
        from alist_mikananirss.common.config.config import AppConfig

        # 测试WebUI配置
        webui_config = WebUIConfig()
        print("✅ WebUI配置模型创建成功")
        print(f"   - 默认主机: {webui_config.host}")
        print(f"   - 默认端口: {webui_config.port}")

        # 测试应用配置
        app_config = AppConfig()
        print("✅ 应用配置模型创建成功")
        print(f"   - WebUI启用: {app_config.webui.enable}")
        print(f"   - WebUI端口: {app_config.webui.port}")

        return True

    except Exception as e:
        print(f"❌ 配置集成测试失败: {e}")
        traceback.print_exc()
        return False

def test_server_creation():
    """测试服务器创建"""
    print("\n🔍 测试服务器创建...")

    try:
        from alist_mikananirss.webui.server import create_app

        app = create_app()
        print("✅ FastAPI应用创建成功")
        print(f"   - 应用标题: {app.title}")
        print(f"   - 版本: {app.version}")
        print(f"   - 路由数量: {len(app.routes)}")

        # 检查路由
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        expected_routes = ["/", "/health", "/dashboard", "/logs", "/config"]

        for route in expected_routes:
            if any(route in r for r in routes):
                print(f"   ✅ 路由 {route} 存在")
            else:
                print(f"   ❌ 路由 {route} 缺失")

        return True

    except Exception as e:
        print(f"❌ 服务器创建测试失败: {e}")
        traceback.print_exc()
        return False

def test_template_files():
    """测试模板文件存在性"""
    print("\n🔍 测试模板文件...")

    template_dir = Path("src/alist_mikananirss/webui/templates")
    required_templates = [
        "base.html",
        "dashboard.html",
        "logs.html",
        "config.html"
    ]

    all_exist = True
    for template in required_templates:
        template_path = template_dir / template
        if template_path.exists():
            print(f"   ✅ {template} 存在")
        else:
            print(f"   ❌ {template} 不存在")
            all_exist = False

    return all_exist

def test_static_files():
    """测试静态文件存在性"""
    print("\n🔍 测试静态文件...")

    static_dir = Path("src/alist_mikananirss/webui/static")

    # 检查目录结构
    css_dir = static_dir / "css"
    js_dir = static_dir / "js"
    images_dir = static_dir / "images"

    dirs_exist = True
    for dir_name, dir_path in [("CSS", css_dir), ("JavaScript", js_dir), ("Images", images_dir)]:
        if dir_path.exists():
            print(f"   ✅ {dir_name}目录存在")
        else:
            print(f"   ❌ {dir_name}目录不存在")
            dirs_exist = False

    # 检查CSS文件
    css_file = css_dir / "webui.css"
    if css_file.exists():
        print(f"   ✅ webui.css 存在")
    else:
        print(f"   ❌ webui.css 不存在")
        dirs_exist = False

    return dirs_exist

def main():
    """主测试函数"""
    print("开始WebUI功能验证测试\n")

    tests = [
        ("模块导入", test_imports),
        ("数据模型", test_models),
        ("配置集成", test_config_integration),
        ("服务器创建", test_server_creation),
        ("模板文件", test_template_files),
        ("静态文件", test_static_files)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))

    # 输出测试结果
    print("\n" + "="*50)
    print("📊 测试结果汇总:")
    print("="*50)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:15} : {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print("-"*50)
    print(f"总计: {len(results)}  |  通过: {passed}  |  失败: {failed}")

    if failed == 0:
        print("\n🎉 所有WebUI功能测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查相关功能")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)