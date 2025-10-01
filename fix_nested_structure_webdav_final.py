#!/usr/bin/env python3
"""
修复嵌套目录结构的脚本 - WebDAV版本（最终修复版）
将嵌套在同名目录中的文件移动到指定目录

使用方法：
python fix_nested_structure_webdav_final.py [选项]

功能：
1. 扫描WebDAV目录中的嵌套结构
2. 识别包含同名文件的目录
3. 将文件移动到指定目录
4. 删除空目录
5. 提供详细的操作日志
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import datetime
import hashlib
import json

# 检查webdav4库是否可用
try:
    import webdav4
    from webdav4.client import Client
    # webdav4使用httpx的异常
    import httpx
    ClientError = httpx.HTTPError
    ResourceNotFound = httpx.HTTPStatusError
except ImportError as e:
    print(f"错误: 需要安装 webdav4 库")
    print(f"导入错误: {e}")
    print("请运行: pip install webdav4")
    sys.exit(1)


class WebDAVOperationError(Exception):
    """WebDAV操作异常"""
    pass


class WebDAVNestedFixer:
    """WebDAV嵌套目录修复器"""
    
    def __init__(self, url: str, username: str, password: str, verbose: bool = False):
        """
        初始化WebDAV客户端
        
        Args:
            url: WebDAV服务器URL
            username: 用户名
            password: 密码
            verbose: 是否显示详细输出
        """
        self.url = url
        self.username = username
        self.password = password
        self.verbose = verbose
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        if verbose:
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
        else:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
        
        # 创建WebDAV客户端
        self.client = Client(
            base_url=self.url,
            auth=(self.username, self.password)
        )
        
        # 测试连接
        try:
            self.client.ls('/')
            self.logger.info(f"成功连接到WebDAV服务器: {self.url}")
        except Exception as e:
            self.logger.error(f"连接WebDAV服务器失败: {str(e)}")
            raise WebDAVOperationError(f"连接失败: {str(e)}")
    
    def _normalize_path(self, path: str) -> str:
        """标准化路径 - 完全避免Windows路径转换"""
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
    
    def _handle_webdav_error(self, error: Exception, operation: str, path: str = ""):
        """处理WebDAV错误"""
        error_msg = f"[{operation}] {path}: WebDAV操作失败: {str(error)}"
        self.logger.error(error_msg)
        raise WebDAVOperationError(error_msg)
    
    def scan_nested_directories(self, directory: str) -> List[Tuple[str, str, Dict]]:
        """
        扫描目录，找到需要修复的嵌套结构

        Args:
            directory: 要扫描的目录

        Returns:
            List[Tuple[str, str, Dict]]: [(目录路径, 文件路径, 文件信息), ...]
        """
        nested_pairs = []

        try:
            # 直接使用用户输入的路径，不进行转换
            self.logger.debug(f"使用路径: {directory}")
            items = self.client.ls(directory)
            
            for item in items:
                    # 检查是否是目录
                if isinstance(item, dict):
                    is_dir = item.get('is_dir', False)
                    item_path = item.get('href', '').replace('/dav', '').rstrip('/')  # 使用href并移除/dav前缀和尾部斜杠
                    item_type = item.get('type', '')
                    item_name = item.get('name', '')
                    content_length = item.get('content_length', 0)
                else:
                    # 如果是对象，尝试获取属性
                    is_dir = getattr(item, 'is_dir', False)
                    item_path = getattr(item, 'href', '').replace('/dav', '').rstrip('/')
                    item_type = getattr(item, 'type', '')
                    item_name = getattr(item, 'name', '')
                    content_length = getattr(item, 'content_length', 0)

                # 调试信息
                self.logger.debug(f"项目: {item_name}, 类型: {item_type}, 是否目录: {is_dir}, 大小: {content_length}")

                # 检查是否是错误的嵌套结构：类型是directory但content_length为None，且包含视频扩展名
                video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
                has_video_ext = any(ext in item_name.lower() for ext in video_extensions)

                is_broken_nested = (item_type == 'directory' and content_length is None and has_video_ext)

                if is_broken_nested:
                    # 这是包含视频扩展名的目录，需要检查其内部是否有文件
                    self.logger.debug(f"检查可能的嵌套目录: {item_name}, 路径: {item_path}")

                    # 尝试列出目录内容
                    try:
                        sub_items = self.client.ls(item_path)
                        self.logger.debug(f"目录 {item_name} 下有 {len(sub_items)} 个项目")

                        for sub_item in sub_items:
                            # 检查子项是否是文件
                            if isinstance(sub_item, dict):
                                sub_is_dir = sub_item.get('is_dir', False)
                                sub_item_path = sub_item.get('href', '').replace('/dav', '').rstrip('/')
                                sub_item_size = sub_item.get('content_length', 0)
                                sub_item_name = sub_item.get('name', '')
                            else:
                                sub_is_dir = getattr(sub_item, 'is_dir', False)
                                sub_item_path = getattr(sub_item, 'href', '').replace('/dav', '').rstrip('/')
                                sub_item_size = getattr(sub_item, 'content_length', 0)
                                sub_item_name = getattr(sub_item, 'name', '')

                            # 更准确的文件判断：有content_length的是文件，或者类型是file
                            is_file = (sub_item_size > 0) or (sub_item.get('type') == 'file')

                            if is_file:
                                self.logger.debug(f"  找到文件: {sub_item_name}")
                                nested_pairs.append((item_path, sub_item_path, {
                                    'name': sub_item_name,
                                    'size': sub_item_size,
                                    'modified': sub_item.get('modified')
                                }))
                                break

                    except Exception as e:
                        self.logger.warning(f"无法读取目录 {item_path}: {str(e)}")
                        # 如果无法读取，跳过这个目录
                elif is_dir:
                    dir_path = item_path
                    dir_name = self._basename(dir_path)

                    # 调试信息
                    self.logger.debug(f"检查目录: {dir_name} ({dir_path})")

                    # 查找目录内的文件
                    try:
                        sub_items = self.client.ls(dir_path)
                        self.logger.debug(f"目录 {dir_name} 下有 {len(sub_items)} 个项目")

                        for sub_item in sub_items:
                            # 检查子项是否是文件
                            if isinstance(sub_item, dict):
                                sub_is_dir = sub_item.get('is_dir', False)
                                sub_item_path = sub_item.get('path', '')
                                sub_item_size = sub_item.get('size', 0)
                                sub_item_modified = sub_item.get('modified', None)
                                sub_item_type = sub_item.get('type', '')
                            else:
                                sub_is_dir = getattr(sub_item, 'is_dir', False)
                                sub_item_path = getattr(sub_item, 'path', '')
                                sub_item_size = getattr(sub_item, 'size', 0)
                                sub_item_modified = getattr(sub_item, 'modified', None)
                                sub_item_type = getattr(sub_item, 'type', '')

                            # 更准确的文件判断：有content_length的是文件，或者类型是file
                            is_file = (sub_item_size > 0) or (sub_item_type == 'file')

                            if is_file:
                                file_path = sub_item_path
                                file_name = self._basename(file_name)

                                # 调试信息
                                self.logger.debug(f"  找到文件: {file_name}")

                                # 简化匹配逻辑：如果目录名包含视频扩展名，说明存在嵌套结构
                                video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
                                has_video_ext = any(ext in dir_name.lower() for ext in video_extensions)

                                # 或者检查目录名是否与文件主体部分匹配
                                file_name_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                                name_match = (dir_name in file_name_without_ext or
                                             file_name_without_ext in dir_name)

                                self.logger.debug(f"    匹配检查: ext={has_video_ext}, name={name_match}")

                                if has_video_ext or name_match:
                                    self.logger.debug(f"    ✓ 发现嵌套结构!")

                                    nested_pairs.append((dir_path, file_path, {
                                        'name': file_name,
                                        'size': sub_item_size,
                                        'modified': sub_item_modified
                                    }))

                                    if self.verbose:
                                        self.logger.debug(f"发现嵌套结构: {dir_path} -> {file_path}")
                                    break
                    except Exception as e:
                        self.logger.warning(f"扫描子目录失败 {dir_path}: {str(e)}")
                        
        except Exception as e:
            self._handle_webdav_error(e, "scan_nested_directories", directory)
        
        return nested_pairs
    
    def file_exists(self, path: str) -> bool:
        """
        检查文件是否存在

        Args:
            path: 文件路径

        Returns:
            bool: 文件是否存在
        """
        try:
            result = self.client.exists(path)
            self.logger.debug(f"检查文件是否存在 {path}: {result}")
            return result
            
        except ClientError as e:
            self._handle_webdav_error(e, "file_exists", path)
        except Exception as e:
            self.logger.warning(f"检查文件存在性失败 {path}: {str(e)}")
            return False
    
    def is_directory(self, path: str) -> bool:
        """
        检查路径是否是目录

        Args:
            path: 路径

        Returns:
            bool: 是否是目录
        """
        try:
            result = self.client.is_dir(path)
            self.logger.debug(f"检查是否是目录 {path}: {result}")
            return result
            
        except ClientError as e:
            self._handle_webdav_error(e, "is_directory", path)
        except Exception as e:
            self.logger.warning(f"检查是否是目录失败 {path}: {str(e)}")
            return False
    
    def get_file_size(self, path: str) -> int:
        """
        获取文件大小

        Args:
            path: 文件路径

        Returns:
            int: 文件大小（字节）
        """
        try:
            size = self.client.content_length(path)
            self.logger.debug(f"获取文件大小 {path}: {size}")
            return size
            
        except ClientError as e:
            self._handle_webdav_error(e, "get_file_size", path)
        except Exception as e:
            self.logger.warning(f"获取文件大小失败 {path}: {str(e)}")
            return 0
    
    def rename(self, old_path: str, new_path: str) -> bool:
        """
        重命名文件或目录

        Args:
            old_path: 原路径
            new_path: 新路径

        Returns:
            bool: 操作是否成功
        """
        try:
            # 直接使用原始路径
            
            self.client.move(from_path=old_path, to_path=new_path, overwrite=True)
            self.logger.info(f"重命名: {old_path} -> {new_path}")
            return True
            
        except ClientError as e:
            self._handle_webdav_error(e, "rename", f"{old_path} -> {new_path}")
        except Exception as e:
            self.logger.error(f"重命名失败: {old_path} -> {new_path}: {str(e)}")
            return False
    
    def move_file(self, source_path: str, target_path: str) -> bool:
        """
        移动文件

        Args:
            source_path: 源路径
            target_path: 目标路径

        Returns:
            bool: 操作是否成功
        """
        try:
            # 直接使用原始路径
            if self.verbose:
                self.logger.info(f"WebDAV移动: {source_path} -> {target_path}")

            self.client.move(from_path=source_path, to_path=target_path, overwrite=True)
            self.logger.info(f"移动文件: {source_path} -> {target_path}")
            return True
            
        except ClientError as e:
            self._handle_webdav_error(e, "move_file", f"{source_path} -> {target_path}")
        except Exception as e:
            self.logger.error(f"移动文件失败: {source_path} -> {target_path}: {str(e)}")
            return False
    
    def delete(self, path: str) -> bool:
        """
        删除文件或目录

        Args:
            path: 路径

        Returns:
            bool: 操作是否成功
        """
        try:
            # 直接使用原始路径

            # 尝试删除为目录
            try:
                self.client.remove(path)
                self.logger.info(f"删除目录: {path}")
                return True
            except ClientError:
                # 如果删除目录失败，尝试删除为文件
                try:
                    self.client.remove(path)
                    self.logger.info(f"删除文件: {path}")
                    return True
                except ClientError as e:
                    self.logger.error(f"删除失败: {path}")
                    raise e
            
        except ClientError as e:
            self._handle_webdav_error(e, "delete", path)
        except Exception as e:
            self.logger.error(f"删除失败: {path}: {str(e)}")
            return False
    
    def fix_nested_structure(self, target_dir: str = ".", dry_run: bool = True, 
                           handle_conflicts: str = "skip") -> Dict:
        """
        修复嵌套目录结构
        
        Args:
            target_dir: 要处理的目标目录路径
            dry_run: 如果为True，只显示将要执行的操作，不实际执行
            handle_conflicts: 冲突处理策略 ("skip", "rename", "overwrite")
            
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
            self.logger.info(f"开始扫描嵌套目录结构... {target_dir}")
            
            # 扫描需要修复的目录
            nested_pairs = self.scan_nested_directories(target_dir)
            result['total_found'] = len(nested_pairs)
            
            if not nested_pairs:
                self.logger.info("未发现需要修复的嵌套目录结构")
                return result
            
            self.logger.info(f"发现 {len(nested_pairs)} 个需要修复的嵌套目录:")
            
            # 显示找到的嵌套结构
            for i, (dir_path, file_path, file_info) in enumerate(nested_pairs, 1):
                dir_name = self._basename(dir_path)
                file_name = file_info['name']
                file_size = file_info['size'] / (1024 * 1024)  # MB
                
                self.logger.info(f"{i:2d}. 目录: {dir_name}")
                self.logger.info(f"    文件: {file_name}")
                self.logger.info(f"    大小: {file_size:.1f} MB")
            
            if dry_run:
                self.logger.info("预览模式 - 不会实际执行操作")
                self.logger.info("使用 --force 参数执行实际操作")
                return result
            
            # 执行修复操作
            for dir_path, file_path, file_info in nested_pairs:
                try:
                    dir_name = self._basename(dir_path)
                    file_name = file_info['name']
                    file_size = file_info['size']
                    # 直接使用文件名作为目标路径，因为已经在目标目录中
                    target_path = f"{target_dir.rstrip('/')}/{file_name}" if target_dir != '/' else f"/{file_name}"
                    
                    detail = {
                        'directory': dir_name,
                        'file': file_name,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'status': 'pending',
                        'message': ''
                    }
                    
                    if self.verbose:
                        self.logger.info(f"处理: {dir_name} -> {file_name}")
                    
                    # 检查目标文件是否已存在，排除目录的情况
                    if self.file_exists(target_path) and not self.is_directory(target_path):
                        # 文件大小不同，按照冲突处理策略处理
                        if self.verbose:
                            self.logger.info(f"目标文件已存在: {file_name}")
                        
                        if handle_conflicts == "skip":
                            detail['status'] = 'skipped'
                            detail['message'] = '目标文件已存在，跳过'
                            result['skip_count'] += 1
                            if self.verbose:
                                self.logger.info(f"跳过: {file_name} (目标文件已存在)")
                            result['details'].append(detail)
                            continue
                        
                        elif handle_conflicts == "rename":
                            # 重命名文件
                            base_name = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                            extension = '.' + file_name.rsplit('.', 1)[1] if '.' in file_name else ''
                            counter = 1
                            new_name = f"{base_name}_{counter}{extension}"
                            new_target_path = f"{target_dir.rstrip('/')}/{new_name}" if target_dir != '/' else f"/{new_name}"
                            
                            while self.file_exists(new_target_path):
                                counter += 1
                                new_name = f"{base_name}_{counter}{extension}"
                                new_target_path = f"{target_dir.rstrip('/')}/{new_name}" if target_dir != '/' else f"/{new_name}"
                            
                            target_path = new_target_path
                            detail['new_name'] = new_name
                            detail['message'] = f'重命名为: {new_name}'
                            
                            if self.verbose:
                                self.logger.info(f"重命名: {file_name} -> {new_name}")
                        
                        elif handle_conflicts == "overwrite":
                            detail['message'] = '覆盖现有文件'
                            if self.verbose:
                                self.logger.info(f"覆盖: {file_name}")
                    
                    # 实现真正的嵌套目录修复：将文件移出，删除目录
                    # 策略：先重命名目录，避免冲突
                    temp_dir_name = f"temp_{dir_name}_{hash(dir_path) % 1000}"
                    temp_dir_path = f"{target_dir.rstrip('/')}/{temp_dir_name}" if target_dir != '/' else f"/{temp_dir_name}"

                    if self.verbose:
                        self.logger.info(f"重命名目录: {dir_name} -> {temp_dir_name}")

                    if not self.rename(dir_path, temp_dir_path):
                        raise Exception(f"重命名目录失败: {dir_path}")

                    # 移动文件到目标位置
                    if self.verbose:
                        self.logger.info(f"移动: {file_name}")

                    # 构造源文件路径（在临时目录中）
                    # 从file_path中提取文件名部分，然后与临时目录路径组合
                    source_file_path = f"{temp_dir_path.rstrip('/')}/{file_name}"

                    if self.verbose:
                        self.logger.info(f"源文件路径: {source_file_path}")
                        self.logger.info(f"目标路径: {target_path}")

                    if not self.move_file(source_file_path, target_path):
                        # 恢复目录名称
                        self.rename(temp_dir_path, dir_path)
                        raise Exception(f"移动文件失败: {file_name}")

                    # 删除临时目录
                    if self.verbose:
                        self.logger.info(f"删除临时目录: {temp_dir_name}")

                    if not self.delete(temp_dir_path):
                        self.logger.warning(f"删除临时目录失败: {temp_dir_name}")

                    if self.verbose:
                        self.logger.info(f"OK 完成: {file_name}")

                    detail['status'] = 'success'
                    result['success_count'] += 1
                    
                    result['details'].append(detail)
                    
                except WebDAVOperationError as e:
                    error_msg = f"处理 {file_name} 时出错: {str(e)}"
                    result['errors'].append(error_msg)
                    result['error_count'] += 1
                    
                    if self.verbose:
                        self.logger.error(f"ERROR 失败: {file_name} - {str(e)}")
                    
                    # 添加错误详情
                    detail['status'] = 'error'
                    detail['message'] = error_msg
                    result['details'].append(detail)
                    
                except Exception as e:
                    error_msg = f"处理 {file_name} 时发生未预期错误: {str(e)}"
                    result['errors'].append(error_msg)
                    result['error_count'] += 1
                    
                    if self.verbose:
                        self.logger.error(f"ERROR 失败: {file_name} - {str(e)}")
                    
                    # 添加错误详情
                    detail['status'] = 'error'
                    detail['message'] = error_msg
                    result['details'].append(detail)
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"整体操作失败: {str(e)}")
            self.logger.error(f"严重错误: {str(e)}")
        
        # 最终状态更新
        if result['error_count'] > 0:
            result['success'] = False
        
        self.logger.info(f"操作完成:")
        self.logger.info(f"  总计发现: {result['total_found']}")
        self.logger.info(f"  成功处理: {result['success_count']}")
        self.logger.info(f"  跳过: {result['skip_count']}")
        self.logger.info(f"  错误: {result['error_count']}")
        
        return result


def show_help():
    """显示帮助信息"""
    print("""
修复嵌套目录结构的脚本 - WebDAV版本（最终修复版）

使用方法:
    python fix_nested_structure_webdav_final.py [选项]

选项:
    --help, -h          显示此帮助信息
    --url, -u <URL>     WebDAV服务器URL
    --username, -U <用户> WebDAV用户名
    --password, -P <密码> WebDAV密码
    --dir, -d <目录>    指定要处理的目录路径
    --force, -f         执行实际操作（默认为预览模式）
    --verbose, -v       显示详细输出
    --conflicts, -c <策略>  冲突处理策略 (skip|rename|overwrite)

示例:
    python fix_nested_structure_webdav_final.py -u http://127.0.0.1:5244/dav -U admin -P 1234
    python fix_nested_structure_webdav_final.py -u http://127.0.0.1:5244/dav -U admin -P 1234 -d /path/to/dir
    python fix_nested_structure_webdav_final.py -u http://127.0.0.1:5244/dav -U admin -P 1234 -f
    python fix_nested_structure_webdav_final.py -u http://127.0.0.1:5244/dav -U admin -P 1234 -f -v
    """)


def main():
    """主函数"""
    args = sys.argv[1:]
    
    # 默认值
    url = "http://127.0.0.1:5244/dav"
    username = "admin"
    password = "1234"
    target_dir = "."
    force_mode = False
    verbose_mode = False
    handle_conflicts = "skip"
    
    # 解析命令行参数
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ['--help', '-h']:
            show_help()
            return
        elif arg in ['--url', '-u']:
            if i + 1 < len(args):
                url = args[i + 1]
                i += 1
            else:
                print("错误: --url 参数需要指定URL")
                show_help()
                return
        elif arg in ['--username', '-U']:
            if i + 1 < len(args):
                username = args[i + 1]
                i += 1
            else:
                print("错误: --username 参数需要指定用户名")
                show_help()
                return
        elif arg in ['--password', '-P']:
            if i + 1 < len(args):
                password = args[i + 1]
                i += 1
            else:
                print("错误: --password 参数需要指定密码")
                show_help()
                return
        elif arg in ['--dir', '-d']:
            if i + 1 < len(args):
                target_dir = args[i + 1]
                # 在Windows上保持Unix风格路径
                if os.name == 'nt' and target_dir.startswith('/'):
                    # 确保保持原始路径格式
                    pass
                i += 1
            else:
                print("错误: --dir 参数需要指定目录路径")
                show_help()
                return
        elif arg in ['--force', '-f']:
            force_mode = True
        elif arg in ['--verbose', '-v']:
            verbose_mode = True
        elif arg in ['--conflicts', '-c']:
            if i + 1 < len(args):
                handle_conflicts = args[i + 1]
                if handle_conflicts not in ["skip", "rename", "overwrite"]:
                    print("错误: --conflicts 参数必须是 skip, rename 或 overwrite")
                    show_help()
                    return
                i += 1
            else:
                print("错误: --conflicts 参数需要指定策略")
                show_help()
                return
        elif not arg.startswith('--') and not arg.startswith('-'):
            # 如果是不带连字符的参数，认为是目录路径
            # 防止Windows自动将 /path 转换为驱动器路径
            if os.name == 'nt' and arg.startswith('/'):
                # 保持原始的Unix风格路径
                target_dir = arg
            else:
                target_dir = arg
        else:
            print(f"未知参数: {arg}")
            show_help()
            return
        i += 1
    
    try:
        # 创建WebDAV修复器
        fixer = WebDAVNestedFixer(
            url=url,
            username=username,
            password=password,
            verbose=verbose_mode
        )
        
        # 执行修复
        result = fixer.fix_nested_structure(
            target_dir=target_dir,
            dry_run=not force_mode,
            handle_conflicts=handle_conflicts
        )
        
        # 输出结果
        print(f"\n最终结果: {'成功' if result['success'] else '部分失败'}")
        print(f"总计发现: {result['total_found']}")
        print(f"成功处理: {result['success_count']}")
        print(f"跳过: {result['skip_count']}")
        print(f"错误: {result['error_count']}")
        
        if result['errors']:
            print("\n错误详情:")
            for error in result['errors']:
                print(f"  - {error}")
        
    except KeyboardInterrupt:
        print("\n操作被用户中断")
    except Exception as e:
        print(f"执行过程中发生错误: {str(e)}")
        if verbose_mode:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
