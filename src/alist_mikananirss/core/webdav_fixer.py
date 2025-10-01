"""
WebDAV嵌套目录修复模块

提供修复WebDAV嵌套目录结构的功能，与主项目架构统一。
"""

import asyncio
import hashlib
import json
import random
import time
from typing import Dict, List, Optional, Tuple

from loguru import logger

from alist_mikananirss.alist.api import Alist


class WebDAVOperationError(Exception):
    """WebDAV操作异常"""
    pass


class WebDAVNestedFixer:
    """WebDAV嵌套目录修复器 - 集成版本"""

    def __init__(self, alist_client: Alist, verbose: bool = False):
        """
        初始化WebDAV修复器

        Args:
            alist_client: Alist客户端实例
            verbose: 是否显示详细输出
        """
        self.client = alist_client
        self.verbose = verbose

        # 设置速率限制 - 每秒最多2个请求
        self.request_delay_min = 0.5  # 最小延迟 500ms
        self.request_delay_max = 0.6  # 最大延迟 600ms，添加小随机范围
        self.last_request_time = 0

        # 测试连接
        asyncio.create_task(self._test_connection())

    async def _test_connection(self):
        """测试Alist连接"""
        try:
            await self.client._api_call('GET', '/api/fs/list', params={'path': '/'})
            logger.info(f"成功连接到Alist服务器: {self.client.base_url}")
        except Exception as e:
            logger.error(f"连接Alist服务器失败: {str(e)}")
            raise WebDAVOperationError(f"连接失败: {str(e)}")

    def _rate_limit_delay(self):
        """
        实现速率限制，在请求之间添加随机延迟
        """
        current_time = time.time()
        if self.last_request_time > 0:
            elapsed = current_time - self.last_request_time
            # 如果距离上次请求时间太短，则等待
            min_delay = self.request_delay_min + random.uniform(0, self.request_delay_max - self.request_delay_min)
            if elapsed < min_delay:
                sleep_time = min_delay - elapsed
                if self.verbose:
                    logger.debug(f"速率限制延迟: {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _normalize_path(self, path: str) -> str:
        """标准化路径"""
        if not path:
            return '/'

        # 确保以 / 开头
        if not path.startswith('/'):
            path = '/' + path

        # 移除重复的斜杠
        while '//' in path:
            path = path.replace('//', '/')

        return path

    def _basename(self, path: str) -> str:
        """获取文件名/目录名"""
        path = path.rstrip('/')
        parts = path.split('/')
        return parts[-1] if parts else ''

    async def scan_nested_directories(self, directory: str, recursive: bool = False) -> List[Tuple[str, str, Dict]]:
        """
        扫描目录，找到需要修复的嵌套结构

        Args:
            directory: 要扫描的目录
            recursive: 是否递归扫描子目录

        Returns:
            List[Tuple[str, str, Dict]]: [(目录路径, 文件路径, 文件信息), ...]
        """
        nested_pairs = []

        try:
            directory = self._normalize_path(directory)
            logger.debug(f"扫描目录: {directory}")

            # 应用速率限制
            self._rate_limit_delay()

            # 使用Alist API获取目录内容
            response = await self.client._api_call(
                'GET',
                '/api/fs/list',
                params={'path': directory, 'per_page': 0}
            )

            if not response.get('content'):
                return nested_pairs

            items = response['content']

            for item in items:
                item_name = item.get('name', '')
                item_path = f"{directory.rstrip('/')}/{item_name}" if directory != '/' else f"/{item_name}"
                is_dir = item.get('is_dir', False)
                file_size = item.get('size', 0)

                # 调试信息
                logger.debug(f"项目: {item_name}, 是否目录: {is_dir}, 大小: {file_size}")

                # 检查是否是错误的嵌套结构：类型是directory但size为0，且包含视频扩展名
                video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
                has_video_ext = any(ext in item_name.lower() for ext in video_extensions)

                if is_dir and has_video_ext:
                    # 这是包含视频扩展名的目录，需要检查其内部是否有文件
                    logger.debug(f"检查可能的嵌套目录: {item_name}, 路径: {item_path}")

                    try:
                        # 应用速率限制
                        self._rate_limit_delay()

                        sub_response = await self.client._api_call(
                            'GET',
                            '/api/fs/list',
                            params={'path': item_path, 'per_page': 0}
                        )

                        if sub_response.get('content'):
                            logger.debug(f"目录 {item_name} 下有 {len(sub_response['content'])} 个项目")

                            for sub_item in sub_response['content']:
                                sub_item_name = sub_item.get('name', '')
                                sub_item_size = sub_item.get('size', 0)
                                sub_item_path = f"{item_path.rstrip('/')}/{sub_item_name}"

                                # 检查是否是文件（size > 0）
                                if sub_item_size > 0:
                                    actual_filename = sub_item_name
                                    logger.debug(f"  找到文件: {actual_filename}")

                                    nested_pairs.append((item_path, sub_item_path, {
                                        'name': actual_filename,
                                        'size': sub_item_size,
                                        'modified': sub_item.get('modified_time')
                                    }))
                                    break

                    except Exception as e:
                        logger.warning(f"无法读取目录 {item_path}: {str(e)}")
                        continue

                elif is_dir:
                    # 普通目录，检查是否包含同名文件
                    try:
                        # 应用速率限制
                        self._rate_limit_delay()

                        sub_response = await self.client._api_call(
                            'GET',
                            '/api/fs/list',
                            params={'path': item_path, 'per_page': 0}
                        )

                        if sub_response.get('content'):
                            logger.debug(f"目录 {item_name} 下有 {len(sub_response['content'])} 个项目")

                            for sub_item in sub_response['content']:
                                sub_item_name = sub_item.get('name', '')
                                sub_item_size = sub_item.get('size', 0)
                                sub_item_path = f"{item_path.rstrip('/')}/{sub_item_name}"

                                if sub_item_size > 0:
                                    file_name = sub_item_name

                                    # 调试信息
                                    logger.debug(f"  找到文件: {file_name}")

                                    # 简化匹配逻辑：如果目录名包含视频扩展名，说明存在嵌套结构
                                    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
                                    has_video_ext = any(ext in item_name.lower() for ext in video_extensions)

                                    # 或者检查目录名是否与文件主体部分匹配
                                    file_name_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                                    name_match = (item_name in file_name_without_ext or
                                                 file_name_without_ext in item_name)

                                    logger.debug(f"    匹配检查: ext={has_video_ext}, name={name_match}")

                                    if has_video_ext or name_match:
                                        logger.debug(f"    ✓ 发现嵌套结构!")

                                        nested_pairs.append((item_path, sub_item_path, {
                                            'name': file_name,
                                            'size': sub_item_size,
                                            'modified': sub_item.get('modified_time')
                                        }))

                                        if self.verbose:
                                            logger.debug(f"发现嵌套结构: {item_path} -> {sub_item_path}")
                                        break

                    except Exception as e:
                        logger.warning(f"扫描子目录失败 {item_path}: {str(e)}")

            # 如果启用递归扫描，遍历所有子目录
            if recursive:
                logger.debug(f"开始递归扫描 {directory} 的子目录...")
                for item in items:
                    item_name = item.get('name', '')
                    item_path = f"{directory.rstrip('/')}/{item_name}" if directory != '/' else f"/{item_name}"
                    is_dir = item.get('is_dir', False)

                    if is_dir and item_path != directory:
                        try:
                            logger.debug(f"递归扫描子目录: {item_name}")
                            sub_nested_pairs = await self.scan_nested_directories(item_path, recursive=True)
                            nested_pairs.extend(sub_nested_pairs)
                        except Exception as e:
                            logger.warning(f"递归扫描失败 {item_path}: {str(e)}")

        except Exception as e:
            logger.error(f"扫描目录失败 {directory}: {str(e)}")
            raise WebDAVOperationError(f"扫描失败: {str(e)}")

        return nested_pairs

    async def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        try:
            await self.client._api_call('GET', '/api/fs/stat', params={'path': path})
            logger.debug(f"检查文件是否存在 {path}: True")
            return True

        except Exception as e:
            logger.debug(f"检查文件存在性失败 {path}: {str(e)}")
            return False

    async def is_directory(self, path: str) -> bool:
        """检查路径是否是目录"""
        try:
            response = await self.client._api_call('GET', '/api/fs/stat', params={'path': path})
            is_dir = response.get('is_dir', False)
            logger.debug(f"检查是否是目录 {path}: {is_dir}")
            return is_dir

        except Exception as e:
            logger.warning(f"检查是否是目录失败 {path}: {str(e)}")
            return False

    async def move_file(self, source_path: str, target_path: str) -> bool:
        """
        移动文件

        Args:
            source_path: 源路径
            target_path: 目标路径

        Returns:
            bool: 操作是否成功
        """
        try:
            if self.verbose:
                logger.info(f"Alist移动: {source_path} -> {target_path}")

            # 应用速率限制
            self._rate_limit_delay()

            # 使用Alist的rename/移动API
            await self.client._api_call(
                'POST',
                '/api/fs/move',
                json={
                    'src_dir': self._basename(source_path).rsplit('.', 1)[0] if '.' in self._basename(source_path) else self._basename(source_path),
                    'dst_dir': self._basename(target_path).rsplit('.', 1)[0] if '.' in self._basename(target_path) else self._basename(target_path),
                    'src_dir_path': source_path.rsplit('/', 1)[0],
                    'dst_dir_path': target_path.rsplit('/', 1)[0]
                }
            )

            logger.info(f"移动文件: {source_path} -> {target_path}")
            return True

        except Exception as e:
            logger.error(f"移动文件失败: {source_path} -> {target_path}: {str(e)}")
            return False

    async def delete(self, path: str) -> bool:
        """
        删除文件或目录

        Args:
            path: 路径

        Returns:
            bool: 操作是否成功
        """
        try:
            # 应用速率限制
            self._rate_limit_delay()

            # 使用Alist删除API
            await self.client._api_call(
                'POST',
                '/api/fs/remove',
                json={
                    'names': [self._basename(path)],
                    'dir': path.rsplit('/', 1)[0]
                }
            )

            logger.info(f"删除: {path}")
            return True

        except Exception as e:
            logger.error(f"删除失败: {path}: {str(e)}")
            return False

    async def fix_nested_structure(self, target_dir: str = ".", dry_run: bool = True,
                                   handle_conflicts: str = "skip", recursive: bool = False) -> Dict:
        """
        修复嵌套目录结构

        Args:
            target_dir: 要处理的目标目录路径
            dry_run: 如果为True，只显示将要执行的操作，不实际执行
            handle_conflicts: 冲突处理策略 ("skip", "rename", "overwrite")
            recursive: 是否递归扫描子目录

        Returns:
            Dict: 操作结果
        """
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
            # 扫描需要修复的目录
            mode_text = "递归" if recursive else "当前"
            logger.info(f"开始{mode_text}扫描嵌套目录结构... {target_dir}")

            nested_pairs = await self.scan_nested_directories(target_dir, recursive=recursive)
            result['total_found'] = len(nested_pairs)

            if not nested_pairs:
                logger.info("未发现需要修复的嵌套目录结构")
                return result

            logger.info(f"发现 {len(nested_pairs)} 个需要修复的嵌套目录:")

            # 显示找到的嵌套结构
            for i, (dir_path, file_path, file_info) in enumerate(nested_pairs, 1):
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

            # 执行修复操作
            for dir_path, file_path, file_info in nested_pairs:
                try:
                    dir_name = self._basename(dir_path)
                    file_name = file_info['name']
                    file_size = file_info['size']

                    # 提取 dir_path 的父目录作为目标目录
                    import os.path as path_os
                    parent_dir = path_os.dirname(dir_path.rstrip('/'))
                    if parent_dir == '':
                        parent_dir = '/'

                    # 构建正确的目标路径
                    target_path = f"{parent_dir.rstrip('/')}/{file_name}" if parent_dir != '/' else f"/{file_name}"

                    if self.verbose:
                        logger.info(f"调试: dir_path = {dir_path}")
                        logger.info(f"调试: 提取的父目录 = {parent_dir}")
                        logger.info(f"调试: 构建的目标路径 = {target_path}")

                    detail = {
                        'directory': dir_name,
                        'file': file_name,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'status': 'pending',
                        'message': ''
                    }

                    if self.verbose:
                        logger.info(f"处理: {dir_name} -> {file_name}")

                    # 检查目标文件是否已存在
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
                            new_target_path = f"{target_dir.rstrip('/')}/{new_name}" if target_dir != '/' else f"/{new_name}"

                            while await self.file_exists(new_target_path):
                                counter += 1
                                new_name = f"{base_name}_{counter}{extension}"
                                new_target_path = f"{target_dir.rstrip('/')}/{new_name}" if target_dir != '/' else f"/{new_name}"

                            target_path = new_target_path
                            detail['new_name'] = new_name
                            detail['message'] = f'重命名为: {new_name}'

                            if self.verbose:
                                logger.info(f"重命名: {file_name} -> {new_name}")

                        elif handle_conflicts == "overwrite":
                            detail['message'] = '覆盖现有文件'
                            if self.verbose:
                                logger.info(f"覆盖: {file_name}")

                    # 执行修复：重命名目录，移动文件，删除目录
                    temp_dir_name = f"temp_{dir_name}_{hash(dir_path) % 1000}"
                    temp_dir_path = f"{target_dir.rstrip('/')}/{temp_dir_name}" if target_dir != '/' else f"/{temp_dir_name}"

                    if self.verbose:
                        logger.info(f"重命名目录: {dir_name} -> {temp_dir_name}")

                    # 重命名目录
                    await self.client._api_call(
                        'POST',
                        '/api/fs/rename',
                        json={
                            'name': dir_name,
                            'new_name': temp_dir_name,
                            'path': dir_path.rsplit('/', 1)[0]
                        }
                    )

                    # 移动文件到目标位置
                    if self.verbose:
                        logger.info(f"移动: {file_name}")

                    source_file_path = f"{temp_dir_path.rstrip('/')}/{file_name}"

                    if not await self.move_file(source_file_path, target_path):
                        # 恢复目录名称
                        await self.client._api_call(
                            'POST',
                            '/api/fs/rename',
                            json={
                                'name': temp_dir_name,
                                'new_name': dir_name,
                                'path': temp_dir_path.rsplit('/', 1)[0]
                            }
                        )
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

                    detail['status'] = 'error'
                    detail['message'] = error_msg
                    result['details'].append(detail)

                except Exception as e:
                    error_msg = f"处理 {file_name} 时发生未预期错误: {str(e)}"
                    result['errors'].append(error_msg)
                    result['error_count'] += 1

                    if self.verbose:
                        logger.error(f"ERROR 失败: {file_name} - {str(e)}")

                    detail['status'] = 'error'
                    detail['message'] = error_msg
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