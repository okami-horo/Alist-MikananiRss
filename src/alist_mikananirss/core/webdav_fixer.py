"""
WebDAV嵌套目录修复模块

完全采用fix_nested_structure_webdav_final.py的方案，确保稳定可靠。
"""

import asyncio
import hashlib
import json
import os
import random
import time
from typing import Dict, List, Optional, Tuple

from loguru import logger
import yaml

# 检查webdav4库是否可用
try:
    import webdav4
    from webdav4.client import Client
    # webdav4使用httpx的异常
    import httpx
    ClientError = httpx.HTTPError
    ResourceNotFound = httpx.HTTPStatusError
except ImportError as e:
    logger.error(f"错误: 需要安装 webdav4 库")
    logger.error(f"导入错误: {e}")
    logger.error("请运行: pip install webdav4")
    raise ImportError("需要安装webdav4库")


class WebDAVOperationError(Exception):
    """WebDAV操作异常"""
    pass


class WebDAVNestedFixer:
    """WebDAV嵌套目录修复器 - 完全基于final脚本"""

    def __init__(self, alist_client=None, verbose: bool = False, url: str = None, username: str = None, password: str = None, config=None):
        """
        初始化WebDAV修复器 - 使用传入的配置参数

        Args:
            alist_client: Alist客户端，用于获取download_path
            verbose: 是否显示详细输出
            url: WebDAV服务器URL
            username: WebDAV用户名
            password: WebDAV密码
            config: 配置对象，用于获取修复工具配置
        """
        self.verbose = verbose
        self.alist_client = alist_client  # 用于获取download_path

        # 使用直接传入的WebDAV参数
        if url:
            self.url = url
        else:
            derived_url = None
            if config and hasattr(config, "alist") and hasattr(config.alist, "base_url"):
                derived_url = config.alist.base_url
            elif alist_client and hasattr(alist_client, "base_url"):
                derived_url = getattr(alist_client, "base_url")

            if derived_url:
                self.url = f"{derived_url.rstrip('/')}/dav"
            else:
                # 默认值
                self.url = "http://127.0.0.1:5244/dav"

        self.username = username or 'admin'
        self.password = password or ''

        # 获取timeout配置
        self.timeout = 60  # 默认60秒
        if config and hasattr(config, 'webdav') and hasattr(config.webdav, 'timeout'):
            self.timeout = config.webdav.timeout
        elif config:
            logger.debug("配置对象中未找到timeout设置，使用默认值")

        # 从配置或alist_client获取download_path
        self.download_path = None
        if config:
            self.download_path = config.alist.download_path
        elif alist_client:
            try:
                # 尝试从配置获取download_path
                from alist_mikananirss.common.config import ConfigManager
                cfg_manager = ConfigManager()
                cfg = cfg_manager.get_config()
                self.download_path = cfg.alist.download_path
            except Exception:
                logger.debug("无法从配置获取download_path，将使用默认路径")

        # 获取WebDAV修复工具配置
        if config:
            # 使用传入的配置对象
            self.enable = config.webdav.fixer.enable
            self.execute_mode = config.webdav.fixer.execute_mode
            self.recursive_scan = config.webdav.fixer.recursive_scan
            self.conflict_strategy = config.webdav.fixer.conflict_strategy
            logger.info(f"成功加载WebDAV修复工具配置: enable={self.enable}, execute_mode={self.execute_mode}, recursive_scan={self.recursive_scan}, conflict_strategy={self.conflict_strategy}")
        else:
            # 尝试从ConfigManager获取配置
            try:
                from alist_mikananirss.common.config import ConfigManager
                cfg_manager = ConfigManager()
                cfg = cfg_manager.get_config()
                self.enable = cfg.webdav.fixer.enable
                self.execute_mode = cfg.webdav.fixer.execute_mode
                self.recursive_scan = cfg.webdav.fixer.recursive_scan
                self.conflict_strategy = cfg.webdav.fixer.conflict_strategy
                logger.info(f"成功加载WebDAV修复工具配置: enable={self.enable}, execute_mode={self.execute_mode}, recursive_scan={self.recursive_scan}, conflict_strategy={self.conflict_strategy}")
            except Exception as e:
                # 使用配置模型中的默认值
                from alist_mikananirss.common.config.basic import WebdavFixerConfig
                default_config = WebdavFixerConfig()
                self.enable = default_config.enable
                self.execute_mode = default_config.execute_mode
                self.recursive_scan = default_config.recursive_scan
                self.conflict_strategy = default_config.conflict_strategy
                logger.warning(f"加载WebDAV修复工具配置失败，使用默认配置: {str(e)}")
                logger.info(f"使用默认配置: enable={self.enable}, execute_mode={self.execute_mode}, recursive_scan={self.recursive_scan}, conflict_strategy={self.conflict_strategy}")

        logger.info(f"WebDAV认证信息: {self.username}@{self.url}")
        if self.download_path:
            logger.info(f"使用download_path作为默认处理路径: {self.download_path}")
        logger.info(f"修复工具配置: execute_mode={self.execute_mode}, recursive_scan={self.recursive_scan}, conflict_strategy={self.conflict_strategy}")

        # 创建WebDAV客户端
        self.client = Client(
            base_url=self.url,
            auth=(self.username, self.password),
            timeout=float(self.timeout)  # 使用配置的超时时间，默认60秒
        )
        logger.info(f"WebDAV客户端超时设置: {self.timeout}秒")

        # 连接测试将在第一次使用时进行
        self._connection_tested = False

  
    async def _ensure_connection_tested(self):
        """确保连接测试已完成（如果需要）"""
        if not self._connection_tested:
            await self._test_connection()
            self._connection_tested = True

    async def _test_connection(self):
        """测试WebDAV连接 - 基于final脚本"""
        try:
            # 使用WebDAV客户端测试连接
            self.client.ls('/')
            logger.info(f"成功连接到WebDAV服务器: {self.url}")
        except Exception as e:
            logger.error(f"连接WebDAV服务器失败: {str(e)}")
            raise WebDAVOperationError(f"连接失败: {str(e)}")

    def _normalize_path(self, path: str) -> str:
        """标准化路径 - 完全避免Windows路径转换，采用final脚本"""
        # 纯字符串处理，不使用任何os.path函数
        if not path:
            return '/'

        # 如果路径看起来像 Windows 绝对路径（如 C:\），我们需要将其转换为WebDAV路径
        if len(path) > 1 and path[1] == ':':
            # 移除驱动器号，只保留后面的路径
            path = path[2:]
            # 将反斜杠转换为正斜杠
            path = path.replace('\\', '/')

        # 确保以 / 开头
        if not path.startswith('/'):
            path = '/' + path

        # 移除重复的斜杠
        while '//' in path:
            path = path.replace('//', '/')

        return path

    def _basename(self, path: str) -> str:
        """获取文件名/目录名（避免Windows路径转换）"""
        # 纯字符串处理，避免路径转换
        path = path.rstrip('/')
        parts = path.split('/')
        return parts[-1] if parts else ''

    def _join_path(self, *parts) -> str:
        """连接路径（避免Windows路径转换）"""
        # 纯字符串处理，避免路径转换
        result = '/'.join(str(part).strip('/') for part in parts if part)
        return '/' + result if result.startswith('/') else result

    def _strip_dav_prefix(self, path: str) -> str:
        path = path or ''
        if path.startswith(self.url):
            path = path[len(self.url):]
        if path.startswith('/dav'):
            path = path[4:]
        if not path.startswith('/') and path:
            path = '/' + path
        return path or '/'

    def _parse_item(self, item) -> Dict:
        if isinstance(item, dict):
            name = item.get('name', '')
            href = item.get('href') or item.get('path') or ''
            item_type = item.get('type', '')
            size = item.get('size') if item.get('size') is not None else item.get('content_length')
            modified = item.get('modified') or item.get('last_modified')
            is_dir = item.get('is_dir', False)
        else:
            name = getattr(item, 'name', '')
            href = getattr(item, 'href', '') or getattr(item, 'path', '')
            item_type = getattr(item, 'type', '')
            size = getattr(item, 'size', None)
            if size is None:
                size = getattr(item, 'content_length', None)
            modified = getattr(item, 'modified', None) or getattr(item, 'last_modified', None)
            is_dir = getattr(item, 'is_dir', False)

        if not is_dir and item_type == 'directory':
            is_dir = True
        if is_dir and size is None:
            size = 0
        if size is None:
            size = 0

        path = self._strip_dav_prefix(href)
        if is_dir and path.endswith('/') and path != '/':
            path = path.rstrip('/')

        return {
            'name': name,
            'path': path,
            'type': item_type,
            'size': size,
            'modified': modified,
            'is_dir': bool(is_dir),
        }

    def _list_directory_items(self, path: str) -> List[Dict]:
        try:
            raw_items = self.client.ls(path)
        except Exception as e:
            logger.warning(f"无法读取目录 {path}: {str(e)}")
            return []
        return [self._parse_item(raw) for raw in raw_items]

    def _handle_webdav_error(self, error: Exception, operation: str, path: str = ""):
        """处理WebDAV错误"""
        error_msg = f"[{operation}] {path}: WebDAV操作失败: {str(error)}"
        logger.error(error_msg)
        raise WebDAVOperationError(error_msg)

    async def scan_nested_directories(self, directory: str, recursive: bool = False) -> List[Tuple[str, str, Dict]]:
        """
        扫描目录，找到需要修复的嵌套结构 - 完全基于final脚本

        Args:
            directory: 要扫描的目录

        Returns:
            List[Tuple[str, str, Dict]]: [(目录路径, 文件路径, 文件信息), ...]
        """
        nested_pairs = []

        try:
            # 确保连接已测试
            await self._ensure_connection_tested()

            # 直接使用用户输入的路径，不进行转换
            directory = self._normalize_path(directory)
            if self.verbose:
                logger.info(f"扫描路径: {directory}")

            items = self.client.ls(directory)
        except Exception as e:
            self._handle_webdav_error(e, "scan_nested_directories", directory)
            return nested_pairs

        for item in items:
            parsed_item = self._parse_item(item)
            is_dir = parsed_item['is_dir']
            item_path = parsed_item['path']
            item_type = parsed_item['type']
            item_name = parsed_item['name']
            content_length = parsed_item['size']

            if item_path == directory:
                continue

            # 调试信息
            if self.verbose:
                logger.info(f"项目: {item_name}, 类型: {item_type}, 是否目录: {is_dir}, 大小: {content_length}")

            # 改进的目录判断逻辑：使用多种方法判断是否为目录
            # 1. 首先使用is_dir字段
            # 2. 如果is_dir为False，检查type字段是否为'directory'
            # 3. 如果还是不确定，使用WebDAV的is_dir方法检查
            # 4. 最后，如果content_length为None，可能是目录
            if not is_dir:
                if item_type == 'directory':
                    is_dir = True
                    if self.verbose:
                        logger.info(f"  -> 根据type字段修正为目录")
                elif item_path and item_path != directory:
                    try:
                        is_dir = self.client.is_dir(item_path)
                        if self.verbose and is_dir:
                            logger.info(f"  -> 根据WebDAV检查修正为目录")
                    except Exception:
                        # 如果检查失败，使用content_length判断
                        if content_length is None:
                            is_dir = True
                            if self.verbose:
                                logger.info(f"  -> 根据content_length为None修正为目录")

            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
            has_video_ext = any(ext in item_name.lower() for ext in video_extensions)

            # 检查是否是错误的嵌套结构：类型是directory但content_length为None，且包含视频扩展名
            is_broken_nested = (item_type == 'directory' and content_length is None and has_video_ext)

            if not is_dir and not is_broken_nested:
                continue

            sub_items = self._list_directory_items(item_path)
            if self.verbose:
                logger.debug(f"目录 {item_name} 下有 {len(sub_items)} 个项目")

            matching_files = [p for p in sub_items if not p['is_dir'] and p['name'] == item_name]
            clean_matching = [p for p in matching_files if not p['name'].endswith('.aria2')]
            extra_dirs = [p for p in sub_items if p['is_dir']]
            extra_files = [p for p in sub_items if (not p['is_dir']) and p['name'] != item_name and not p['name'].endswith('.aria2')]

            if clean_matching and not extra_dirs and not extra_files:
                file_info = clean_matching[0]
                if self.verbose:
                    logger.debug(f"  找到文件: {file_info['name']}")
                nested_pairs.append((item_path, file_info['path'], {
                    'name': file_info['name'],
                    'size': file_info['size'],
                    'modified': file_info['modified']
                }))
                if self.verbose:
                    logger.debug(f"发现嵌套结构: {item_path} -> {file_info['path']}")
                continue

            if not is_dir:
                continue

            dir_path = item_path
            dir_name = self._basename(dir_path)

            # 调试信息
            if self.verbose:
                logger.info(f"检查目录: {dir_name} ({dir_path})")

            for sub_item in sub_items:
                if sub_item['is_dir']:
                    continue

                file_path = sub_item['path']
                file_name = self._basename(file_path)

                if file_name.endswith('.aria2'):
                    continue

                # 调试信息
                if self.verbose:
                    logger.debug(f"  找到文件: {file_name}")

                # 简化匹配逻辑：如果目录名包含视频扩展名，说明存在嵌套结构
                dir_has_video_ext = any(ext in dir_name.lower() for ext in video_extensions)

                # 或者检查目录名是否与文件主体部分匹配
                file_name_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                name_match = (dir_name in file_name_without_ext or
                              file_name_without_ext in dir_name)

                if self.verbose:
                    logger.debug(f"    匹配检查: ext={dir_has_video_ext}, name={name_match}")

                if dir_has_video_ext or name_match:
                    if self.verbose:
                        logger.debug(f"    ✓ 发现嵌套结构!")

                    nested_pairs.append((dir_path, file_path, {
                        'name': file_name,
                        'size': sub_item['size'],
                        'modified': sub_item['modified']
                    }))

                    if self.verbose:
                        logger.debug(f"发现嵌套结构: {dir_path} -> {file_path}")
                    break

        return nested_pairs

    async def get_all_directories(self, directory: str) -> List[str]:
        """
        递归获取指定目录下的所有子目录

        Args:
            directory: 要扫描的根目录

        Returns:
            List[str]: 所有子目录的路径列表
        """
        all_dirs = []

        try:
            directory = self._normalize_path(directory)

            # 获取当前目录下的所有项目
            items = self.client.ls(directory)

            for item in items:
                parsed_item = self._parse_item(item)
                item_path = parsed_item['path']
                item_type = parsed_item['type']

                # 判断是否为目录
                is_dir = False
                if item_type == 'directory':
                    is_dir = True
                elif item_path and item_path != directory:
                    try:
                        is_dir = self.client.is_dir(item_path)
                    except:
                        pass

                if is_dir and item_path and item_path != directory:
                    all_dirs.append(item_path)
                    if self.verbose:
                        logger.info(f"找到子目录: {item_path}")

                    # 递归获取子目录下的所有目录
                    sub_dirs = await self.get_all_directories(item_path)
                    all_dirs.extend(sub_dirs)

        except Exception as e:
            logger.warning(f"获取目录列表失败 {directory}: {str(e)}")

        return all_dirs

    async def file_exists(self, path: str) -> bool:
        """
        检查文件是否存在 - 基于final脚本

        Args:
            path: 文件路径

        Returns:
            bool: 文件是否存在
        """
        try:
            result = self.client.exists(path)
            if self.verbose:
                logger.debug(f"检查文件是否存在 {path}: {result}")
            return result

        except ClientError as e:
            self._handle_webdav_error(e, "file_exists", path)
        except Exception as e:
            logger.warning(f"检查文件存在性失败 {path}: {str(e)}")
            return False

    async def is_directory(self, path: str) -> bool:
        """
        检查路径是否是目录 - 基于final脚本

        Args:
            path: 路径

        Returns:
            bool: 是否是目录
        """
        try:
            result = self.client.is_dir(path)
            if self.verbose:
                logger.debug(f"检查是否是目录 {path}: {result}")
            return result

        except ClientError as e:
            self._handle_webdav_error(e, "is_directory", path)
        except Exception as e:
            logger.warning(f"检查是否是目录失败 {path}: {str(e)}")
            return False

    async def get_file_size(self, path: str) -> int:
        """
        获取文件大小 - 基于final脚本

        Args:
            path: 文件路径

        Returns:
            int: 文件大小（字节）
        """
        try:
            size = self.client.content_length(path)
            if self.verbose:
                logger.debug(f"获取文件大小 {path}: {size}")
            return size

        except ClientError as e:
            self._handle_webdav_error(e, "get_file_size", path)
        except Exception as e:
            logger.warning(f"获取文件大小失败 {path}: {str(e)}")
            return 0

    async def rename(self, old_path: str, new_path: str) -> bool:
        """
        重命名文件或目录 - 基于final脚本

        Args:
            old_path: 原路径
            new_path: 新路径

        Returns:
            bool: 操作是否成功
        """
        try:
            # 直接使用原始路径 - 基于final脚本
            if self.verbose:
                logger.info(f"WebDAV重命名: {old_path} -> {new_path}")

            self.client.move(from_path=old_path, to_path=new_path, overwrite=True)
            logger.info(f"重命名: {old_path} -> {new_path}")
            return True

        except ClientError as e:
            self._handle_webdav_error(e, "rename", f"{old_path} -> {new_path}")
        except Exception as e:
            logger.error(f"重命名失败: {old_path} -> {new_path}: {str(e)}")
            return False

    async def move_file(self, source_path: str, target_path: str) -> bool:
        """
        移动文件 - 基于final脚本

        Args:
            source_path: 源路径
            target_path: 目标路径

        Returns:
            bool: 操作是否成功
        """
        try:
            # 直接使用原始路径 - 基于final脚本
            if self.verbose:
                logger.info(f"WebDAV移动: {source_path} -> {target_path}")

            self.client.move(from_path=source_path, to_path=target_path, overwrite=True)
            logger.info(f"移动文件: {source_path} -> {target_path}")
            return True

        except ClientError as e:
            self._handle_webdav_error(e, "move_file", f"{source_path} -> {target_path}")
        except Exception as e:
            logger.error(f"移动文件失败: {source_path} -> {target_path}: {str(e)}")
            return False

    async def delete(self, path: str) -> bool:
        """
        删除文件或目录 - 基于final脚本

        Args:
            path: 路径

        Returns:
            bool: 操作是否成功
        """
        try:
            # 直接使用原始路径 - 基于final脚本
            if self.verbose:
                logger.info(f"WebDAV删除: {path}")

            # 尝试删除为目录
            try:
                self.client.remove(path)
                logger.info(f"删除目录: {path}")
                return True
            except ClientError:
                # 如果删除目录失败，尝试删除为文件
                try:
                    self.client.remove(path)
                    logger.info(f"删除文件: {path}")
                    return True
                except ClientError as e:
                    logger.error(f"删除失败: {path}")
                    raise e

        except ClientError as e:
            self._handle_webdav_error(e, "delete", path)
        except Exception as e:
            logger.error(f"删除失败: {path}: {str(e)}")
            return False

    async def fix_nested_structure(self, target_dir: str = None, dry_run: bool = None,
                                   handle_conflicts: str = None, recursive: bool = None) -> Dict:
        """
        修复嵌套目录结构 - 完全基于final脚本

        Args:
            target_dir: 要处理的目标目录路径，如果为None则使用配置中的download_path
            dry_run: 如果为True，只显示将要执行的操作，不实际执行，如果为None则使用配置中的execute_mode
            handle_conflicts: 冲突处理策略 ("skip", "rename", "overwrite")，如果为None则使用配置中的conflict_strategy
            recursive: 是否递归扫描子目录，如果为None则使用配置中的recursive_scan

        Returns:
            Dict: 操作结果
        """
        # 使用配置中的默认值
        if target_dir is None:
            target_dir = self.download_path or "."
            if self.download_path:
                logger.info(f"使用配置中的download_path: {target_dir}")

        if dry_run is None:
            dry_run = not self.execute_mode  # execute_mode=True意味着dry_run=False
            logger.info(f"使用配置中的execute_mode: {'实际执行' if not dry_run else '预览模式'}")

        if handle_conflicts is None:
            handle_conflicts = self.conflict_strategy
            logger.info(f"使用配置中的conflict_strategy: {handle_conflicts}")

        if recursive is None:
            recursive = self.recursive_scan
            logger.info(f"使用配置中的recursive_scan: {recursive}")
        result = {
            'success': True,
            'total_found': 0,
            'success_count': 0,
            'skip_count': 0,
            'error_count': 0,
            'details': [],
            'errors': []
        }

        try:
            logger.info(f"开始扫描嵌套目录结构... {target_dir}")

            # 确定要扫描的目录列表
            seen_directories = set()

            def _add_directory(path: str):
                normalized = self._normalize_path(path).rstrip('/') or '/'
                if normalized not in seen_directories:
                    seen_directories.add(normalized)
                    directories_to_scan.append(normalized)

            directories_to_scan = []
            _add_directory(target_dir)

            if recursive:
                if self.verbose:
                    logger.info("递归扫描模式下，获取所有子目录...")
                for sub_dir in await self.get_all_directories(target_dir):
                    _add_directory(sub_dir)
                if self.verbose:
                    logger.info(f"找到 {len(directories_to_scan) - 1} 个子目录需要扫描")

            # 扫描所有目录中的嵌套结构
            all_nested_pairs = []
            for directory in directories_to_scan:
                if self.verbose:
                    logger.info(f"扫描目录: {directory}")

                nested_pairs = await self.scan_nested_directories(directory)
                all_nested_pairs.extend(nested_pairs)

            result['total_found'] = len(all_nested_pairs)

            if not all_nested_pairs:
                logger.info("未发现需要修复的嵌套目录结构")
                return result

            logger.info(f"发现 {len(all_nested_pairs)} 个需要修复的嵌套目录:")

            # 显示找到的嵌套结构
            for i, (dir_path, file_path, file_info) in enumerate(all_nested_pairs, 1):
                dir_name = self._basename(dir_path)
                file_name = file_info['name']
                file_size = file_info['size'] / (1024 * 1024)  # MB

                logger.info(f"{i:2d}. 目录: {dir_name}")
                logger.info(f"    文件: {file_name}")
                logger.info(f"    大小: {file_size:.1f} MB")

            if dry_run:
                logger.info("预览模式 - 不会实际执行操作")
                logger.info("使用 --force 参数执行实际操作")
                return result

            # 执行修复操作 - 基于final脚本
            for dir_path, file_path, file_info in all_nested_pairs:
                try:
                    dir_name = self._basename(dir_path)
                    file_name = file_info['name']
                    file_size = file_info['size']

                    # 目标路径应该是嵌套问题所在的目录 + 文件名
                    # 这样每个子目录的修复任务都是独立的
                    parent_dir = self._normalize_path(dir_path).rstrip('/').rsplit('/', 1)[0] if '/' in self._normalize_path(dir_path).rstrip('/') else '/'
                    pure_file_name = self._basename(file_path)
                    target_path = f"{parent_dir}/{pure_file_name}" if parent_dir != '/' else f"/{pure_file_name}"

                    detail = {
                        'directory': dir_name,
                        'file': file_name,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'status': 'pending',
                        'message': ''
                    }

                    if self.verbose:
                        logger.info(f"处理嵌套问题: {dir_path}")
                        logger.info(f"  -> 目标父目录: {parent_dir}")
                        logger.info(f"  -> 目标文件: {target_path}")

                    # 检查目标文件是否已存在，排除目录的情况
                    if await self.file_exists(target_path) and not await self.is_directory(target_path):
                        if self.verbose:
                            logger.info(f"目标文件已存在: {file_name}")

                        if handle_conflicts == "skip":
                            detail['status'] = 'skipped'
                            detail['message'] = '目标文件已存在，跳过'
                            result['skip_count'] += 1
                            if self.verbose:
                                logger.info(f"跳过: {file_name} (目标文件已存在)")
                            result['details'].append(detail)
                            continue

                        elif handle_conflicts == "rename":
                            # 重命名文件
                            base_name = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                            extension = '.' + file_name.rsplit('.', 1)[1] if '.' in file_name else ''
                            counter = 1
                            new_name = f"{base_name}_{counter}{extension}"
                            new_target_path = f"{parent_dir.rstrip('/')}/{new_name}" if parent_dir != '/' else f"/{new_name}"

                            while await self.file_exists(new_target_path):
                                counter += 1
                                new_name = f"{base_name}_{counter}{extension}"
                                new_target_path = f"{parent_dir.rstrip('/')}/{new_name}" if parent_dir != '/' else f"/{new_name}"

                            target_path = new_target_path
                            detail['new_name'] = new_name
                            detail['message'] = f'重命名为: {new_name}'

                            if self.verbose:
                                logger.info(f"重命名: {file_name} -> {new_name}")

                        elif handle_conflicts == "overwrite":
                            detail['message'] = '覆盖现有文件'
                            if self.verbose:
                                logger.info(f"覆盖: {file_name}")

                    # 实现真正的嵌套目录修复：将文件移出，删除目录
                    # 策略：先重命名目录，避免冲突 - 基于final脚本
                    # 临时目录也创建在嵌套问题所在的目录，保持独立性
                    temp_dir_name = f"temp_{dir_name}_{hash(dir_path) % 1000}"
                    parent_dir = self._normalize_path(dir_path).rstrip('/').rsplit('/', 1)[0] if '/' in self._normalize_path(dir_path).rstrip('/') else '/'
                    temp_dir_path = f"{parent_dir}/{temp_dir_name}" if parent_dir != '/' else f"/{temp_dir_name}"

                    if self.verbose:
                        logger.info(f"重命名目录: {dir_path} -> {temp_dir_path}")

                    if not await self.rename(dir_path, temp_dir_path):
                        raise Exception(f"重命名目录失败: {dir_name}")

                    # 移动文件到目标位置
                    if self.verbose:
                        logger.info(f"移动: {file_name}")

                    # 构造源文件路径（在临时目录中）
                    # 使用纯文件名，不包含路径
                    pure_file_name = self._basename(file_path)
                    source_file_path = f"{temp_dir_path.rstrip('/')}/{pure_file_name}"

                    if self.verbose:
                        logger.info(f"源文件路径: {source_file_path}")
                        logger.info(f"目标路径: {target_path}")

                    if not await self.move_file(source_file_path, target_path):
                        # 恢复目录名称
                        await self.rename(temp_dir_path, dir_path)
                        raise Exception(f"移动文件失败: {file_name}")

                    # 删除临时目录
                    if self.verbose:
                        logger.info(f"删除临时目录: {temp_dir_name}")

                    if not await self.delete(temp_dir_path):
                        logger.warning(f"删除临时目录失败: {temp_dir_name}")

                    if self.verbose:
                        logger.info(f"OK 完成: {file_name}")

                    detail['status'] = 'success'
                    result['success_count'] += 1

                    result['details'].append(detail)

                except WebDAVOperationError as e:
                    error_msg = f"处理 {file_name} 时出错: {str(e)}"
                    result['errors'].append(error_msg)
                    result['error_count'] += 1

                    if self.verbose:
                        logger.error(f"ERROR 失败: {file_name} - {str(e)}")

                    # 添加错误详情
                    detail = {
                        'directory': dir_name,
                        'file': file_name,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'status': 'error',
                        'message': error_msg
                    }
                    result['details'].append(detail)

                except Exception as e:
                    error_msg = f"处理 {file_name} 时发生未预期错误: {str(e)}"
                    result['errors'].append(error_msg)
                    result['error_count'] += 1

                    if self.verbose:
                        logger.error(f"ERROR 失败: {file_name} - {str(e)}")

                    # 添加错误详情
                    detail = {
                        'directory': dir_name,
                        'file': file_name,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'status': 'error',
                        'message': error_msg
                    }
                    result['details'].append(detail)

        except Exception as e:
            result['success'] = False
            result['errors'].append(f"整体操作失败: {str(e)}")
            logger.error(f"严重错误: {str(e)}")

        # 最终状态更新
        if result['error_count'] > 0:
            result['success'] = False

        logger.info(f"操作完成:")
        logger.info(f"  总计发现: {result['total_found']}")
        logger.info(f"  成功处理: {result['success_count']}")
        logger.info(f"  跳过: {result['skip_count']}")
        logger.info(f"  错误: {result['error_count']}")

        return result