#!/usr/bin/env python3
"""
简化的WebUI功能测试
"""

import sys
import os
from pathlib import Path

# 添加src到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_basic_imports():
    """测试基本导入"""
    try:
        # 测试模型
        from alist_mikananirss.webui.models import SystemStatus, LogEntry
        print("[OK] Models imported successfully")

        # 测试服务器
        from alist_mikananirss.webui.server import app
        print("[OK] Server imported successfully")
        print(f"   - Title: {app.title}")
        print(f"   - Version: {app.version}")

        return True
    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        return False

def test_file_structure():
    """测试文件结构"""
    base_path = Path("src/alist_mikananirss/webui")

    # 检查关键文件
    required_files = [
        "server.py",
        "models.py",
        "templates/base.html",
        "templates/dashboard.html",
        "static/css/webui.css"
    ]

    all_exist = True
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"[OK] {file_path} exists")
        else:
            print(f"[ERROR] {file_path} missing")
            all_exist = False

    return all_exist

def main():
    print("Starting WebUI functionality test...\n")

    tests = [
        ("Basic Imports", test_basic_imports),
        ("File Structure", test_file_structure)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        result = test_func()
        results.append((test_name, result))
        print()

    print("Test Results:")
    print("-" * 30)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")

    print(f"\nTotal: {total}, Passed: {passed}, Failed: {total - passed}")

    if passed == total:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())