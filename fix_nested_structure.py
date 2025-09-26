#!/usr/bin/env python3
"""
修复嵌套目录结构的脚本
将嵌套在同名目录中的文件移动到指定目录

使用方法：
python fix_nested_structure.py [目录路径] [选项]

功能：
1. 扫描指定目录（默认为当前目录）
2. 识别包含同名文件的目录
3. 将文件移动到指定目录
4. 删除空目录
5. 提供详细的操作日志
6. 新增：递归处理所有子目录
7. 新增：仅处理子目录模式
"""

import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple, Dict


def scan_nested_directories(directory: str = ".") -> List[Tuple[str, str]]:
    """
    扫描目录，找到需要修复的嵌套结构

    返回: [(目录路径, 文件路径), ...]
    """
    nested_pairs = []

    for item in Path(directory).iterdir():
        if item.is_dir():
            # 查找目录内的文件
            for file_item in item.iterdir():
                if file_item.is_file():
                    # 检查是否是同名文件（去除扩展名）
                    dir_name = item.name
                    file_name = file_item.name

                    # 去除文件扩展名进行比较
                    file_name_without_ext = Path(file_name).stem

                    # 检查是否目录名包含文件名的主体部分
                    # 处理编码问题和可能的格式差异
                    if (dir_name == file_name_without_ext or
                        file_name_without_ext in dir_name or
                        dir_name.replace('.mp4', '') == file_name_without_ext):
                        nested_pairs.append((str(item), str(file_item)))
                        break

    return nested_pairs


def get_subdirectories(directory: str) -> List[str]:
    """
    获取指定目录下的所有子目录

    Args:
        directory: 父目录路径

    Returns:
        List[str]: 子目录路径列表
    """
    subdirs = []
    path = Path(directory)

    if not path.exists() or not path.is_dir():
        return subdirs

    for item in path.iterdir():
        if item.is_dir():
            subdirs.append(str(item))

    return subdirs


def fix_nested_structure(target_dir: str = ".", dry_run: bool = True) -> None:
    """
    修复嵌套目录结构

    Args:
        target_dir: 要处理的目标目录路径
        dry_run: 如果为True，只显示将要执行的操作，不实际执行
    """
    print(f"开始扫描嵌套目录结构... {target_dir}")

    # 扫描需要修复的目录
    nested_pairs = scan_nested_directories(target_dir)

    if not nested_pairs:
        print("未发现需要修复的嵌套目录结构")
        return

    print(f"\n发现 {len(nested_pairs)} 个需要修复的嵌套目录：")
    print("-" * 80)

    for i, (dir_path, file_path) in enumerate(nested_pairs, 1):
        dir_name = Path(dir_path).name
        file_name = Path(file_path).name
        file_size = Path(file_path).stat().st_size / (1024 * 1024)  # MB

        print(f"{i:2d}. 目录: {dir_name}")
        print(f"    文件: {file_name}")
        print(f"    大小: {file_size:.1f} MB")
        print()

    if dry_run:
        print("预览模式 - 不会实际执行操作")
        print("使用 --force 参数执行实际操作")
        return

    # 确认操作
    if not dry_run:
        print("即将执行以下操作：")
        print("1. 将文件移动到当前目录")
        print("2. 删除空目录")
        print("3. 处理文件名冲突")
        print("开始执行操作...")

    # 执行修复操作
    success_count = 0
    skip_count = 0

    for dir_path, file_path in nested_pairs:
        try:
            dir_name = Path(dir_path).name
            file_name = Path(file_path).name
            target_path = Path(target_dir) / file_name

            # 检查目标文件是否已存在（排除目录）
            if target_path.exists() and target_path.is_file():
                print(f"跳过: {file_name} (目标文件已存在)")
                skip_count += 1
                continue

            # 策略：先重命名目录，避免冲突
            temp_dir_name = f"temp_{dir_name}_{hash(dir_path) % 1000}"
            temp_dir_path = Path(target_dir) / temp_dir_name

            print(f"重命名目录: {dir_name} -> {temp_dir_name}")
            Path(dir_path).rename(temp_dir_path)

            # 移动文件到目标位置
            print(f"移动: {file_name}")
            new_file_path = temp_dir_path / file_name
            shutil.move(str(new_file_path), target_path)

            # 删除临时目录
            print(f"删除临时目录: {temp_dir_name}")
            temp_dir_path.rmdir()

            success_count += 1
            print(f"OK 完成: {file_name}")

        except Exception as e:
            print(f"ERROR 失败: {file_name} - {str(e)}")
            skip_count += 1

    print("\n操作完成:")
    print(f"OK 成功: {success_count} 个")
    print(f"ERROR 跳过: {skip_count} 个")


def fix_nested_subdirectories(root_directory: str, force_execute: bool = False,
                              verbose: bool = False, handle_conflicts: str = "skip") -> Dict:
    """
    批量修复目录下所有子目录的嵌套结构

    Args:
        root_directory: 根目录路径
        force_execute: 是否强制执行操作（False为预览模式）
        verbose: 是否显示详细输出
        handle_conflicts: 冲突处理策略 ("skip", "rename", "overwrite")

    Returns:
        Dict: 包含所有子目录处理结果的汇总字典
            {
                'success': bool,
                'total_subdirs': int,
                'processed_subdirs': int,
                'total_found': int,
                'total_success': int,
                'total_skipped': int,
                'total_errors': int,
                'subdir_results': list,
                'errors': list
            }
    """
    result = {
        'success': True,
        'total_subdirs': 0,
        'processed_subdirs': 0,
        'total_found': 0,
        'total_success': 0,
        'total_skipped': 0,
        'total_errors': 0,
        'subdir_results': [],
        'errors': []
    }

    try:
        # 获取所有子目录
        subdirs = get_subdirectories(root_directory)
        result['total_subdirs'] = len(subdirs)

        if not subdirs:
            if verbose:
                print(f"在 {root_directory} 中未发现子目录")
            return result

        if verbose:
            print(f"开始处理 {len(subdirs)} 个子目录...")

        # 处理每个子目录
        for subdir_path in subdirs:
            subdir_name = Path(subdir_path).name

            if verbose:
                print(f"\n处理子目录: {subdir_name}")

            try:
                # 对每个子目录调用修复函数
                subdir_result = fix_nested_structure_complete(
                    subdir_path,
                    force_execute=force_execute,
                    verbose=verbose,
                    handle_conflicts=handle_conflicts
                )

                # 记录子目录结果
                subdir_summary = {
                    'subdir_path': subdir_path,
                    'subdir_name': subdir_name,
                    'success': subdir_result['success'],
                    'total_found': subdir_result['total_found'],
                    'success_count': subdir_result['success_count'],
                    'skip_count': subdir_result['skip_count'],
                    'error_count': subdir_result['error_count']
                }

                result['subdir_results'].append(subdir_summary)
                result['processed_subdirs'] += 1
                result['total_found'] += subdir_result['total_found']
                result['total_success'] += subdir_result['success_count']
                result['total_skipped'] += subdir_result['skip_count']
                result['total_errors'] += subdir_result['error_count']

                # 如果子目录处理失败，记录错误
                if not subdir_result['success']:
                    result['success'] = False
                    result['errors'].extend([f"{subdir_name}: {error}" for error in subdir_result['errors']])

            except Exception as e:
                error_msg = f"处理子目录 {subdir_name} 时发生错误: {str(e)}"
                result['errors'].append(error_msg)
                result['total_errors'] += 1
                result['success'] = False

                # 添加失败的子目录结果
                result['subdir_results'].append({
                    'subdir_path': subdir_path,
                    'subdir_name': subdir_name,
                    'success': False,
                    'total_found': 0,
                    'success_count': 0,
                    'skip_count': 0,
                    'error_count': 1,
                    'error': error_msg
                })

                if verbose:
                    print(f"  错误: {error_msg}")

        # 显示汇总结果
        if verbose:
            print(f"\n批量处理完成:")
            print(f"  子目录总数: {result['total_subdirs']}")
            print(f"  已处理子目录: {result['processed_subdirs']}")
            print(f"  总计发现嵌套结构: {result['total_found']}")
            print(f"  总计成功修复: {result['total_success']}")
            print(f"  总计跳过: {result['total_skipped']}")
            print(f"  总计错误: {result['total_errors']}")

    except Exception as e:
        result['success'] = False
        result['errors'].append(f"批量处理失败: {str(e)}")
        if verbose:
            print(f"严重错误: {str(e)}")

    return result


def fix_nested_structure_complete(directory_path: str, force_execute: bool = False,
                                 verbose: bool = False, handle_conflicts: str = "skip") -> dict:
    """
    完整的嵌套目录结构修复方法

    Args:
        directory_path: 要处理的目录路径
        force_execute: 是否强制执行操作（False为预览模式）
        verbose: 是否显示详细输出
        handle_conflicts: 冲突处理策略 ("skip", "rename", "overwrite")

    Returns:
        dict: 包含操作结果的字典
            {
                'success': bool,
                'total_found': int,
                'success_count': int,
                'skip_count': int,
                'error_count': int,
                'details': list,
                'errors': list
            }
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
        # 验证目录路径
        path = Path(directory_path)
        if not path.exists():
            raise FileNotFoundError(f"目录不存在: {directory_path}")
        if not path.is_dir():
            raise NotADirectoryError(f"路径不是目录: {directory_path}")

        if verbose:
            print(f"开始扫描目录: {directory_path}")

        # 扫描嵌套结构
        nested_pairs = scan_nested_directories(directory_path)
        result['total_found'] = len(nested_pairs)

        if not nested_pairs:
            if verbose:
                print("未发现需要修复的嵌套目录结构")
            return result

        if verbose:
            print(f"发现 {len(nested_pairs)} 个需要修复的嵌套目录:")

        # 处理每个嵌套结构
        for dir_path, file_path in nested_pairs:
            try:
                dir_name = Path(dir_path).name
                file_name = Path(file_path).name
                file_size = Path(file_path).stat().st_size / (1024 * 1024)
                target_path = path / file_name

                detail = {
                    'directory': dir_name,
                    'file': file_name,
                    'size_mb': round(file_size, 2),
                    'status': 'pending',
                    'message': ''
                }

                if verbose:
                    print(f"处理: {dir_name} -> {file_name} ({file_size:.1f} MB)")

                # 检查文件冲突
                if target_path.exists() and target_path.is_file():
                    if handle_conflicts == "skip":
                        detail['status'] = 'skipped'
                        detail['message'] = '目标文件已存在，跳过'
                        result['skip_count'] += 1
                        if verbose:
                            print(f"  跳过: {file_name} (目标文件已存在)")

                    elif handle_conflicts == "rename":
                        # 重命名文件
                        base_name = Path(file_name).stem
                        extension = Path(file_name).suffix
                        counter = 1
                        new_name = f"{base_name}_{counter}{extension}"
                        new_target = path / new_name

                        while new_target.exists():
                            counter += 1
                            new_name = f"{base_name}_{counter}{extension}"
                            new_target = path / new_name

                        target_path = new_target
                        detail['new_name'] = new_name
                        detail['message'] = f'重命名为: {new_name}'

                        if verbose:
                            print(f"  重命名: {file_name} -> {new_name}")

                    elif handle_conflicts == "overwrite":
                        detail['message'] = '覆盖现有文件'
                        if verbose:
                            print(f"  覆盖: {file_name}")

                # 执行实际操作（如果不是预览模式）
                if force_execute:
                    # 创建临时目录名称
                    temp_dir_name = f"temp_{dir_name}_{hash(dir_path) % 1000}"
                    temp_dir_path = path / temp_dir_name

                    # 重命名原目录
                    Path(dir_path).rename(temp_dir_path)

                    # 移动文件
                    new_file_path = temp_dir_path / file_name
                    shutil.move(str(new_file_path), target_path)

                    # 删除临时目录
                    temp_dir_path.rmdir()

                    detail['status'] = 'success'
                    result['success_count'] += 1

                    if verbose:
                        print(f"  成功: {file_name}")
                else:
                    detail['status'] = 'preview'
                    detail['message'] = '预览模式，未执行操作'
                    if verbose:
                        print(f"  预览: {file_name}")

                result['details'].append(detail)

            except Exception as e:
                error_msg = f"处理 {file_name} 时出错: {str(e)}"
                result['errors'].append(error_msg)
                result['error_count'] += 1

                if verbose:
                    print(f"  错误: {error_msg}")

                # 添加错误详情
                detail['status'] = 'error'
                detail['message'] = error_msg
                result['details'].append(detail)

        # 最终状态更新
        if result['error_count'] > 0:
            result['success'] = False

        if verbose:
            print(f"\n操作完成:")
            print(f"  总计发现: {result['total_found']}")
            print(f"  成功处理: {result['success_count']}")
            print(f"  跳过: {result['skip_count']}")
            print(f"  错误: {result['error_count']}")

    except Exception as e:
        result['success'] = False
        result['errors'].append(f"整体操作失败: {str(e)}")
        if verbose:
            print(f"严重错误: {str(e)}")

    return result


def show_help():
    """显示帮助信息"""
    print("""
修复嵌套目录结构的脚本

使用方法:
    python fix_nested_structure.py [目录路径] [选项]

选项:
    --help, -h          显示此帮助信息
    --force, -f         执行实际操作（默认为预览模式）
    --verbose, -v       显示详细输出
    --dir, -d <目录>    指定要处理的目录路径
    --recursive, -r     递归处理所有子目录
    --subdirs, -s       仅处理子目录（不处理主目录）

示例:
    python fix_nested_structure.py                    # 预览模式（当前目录）
    python fix_nested_structure.py --force           # 执行操作（当前目录）
    python fix_nested_structure.py /path/to/dir      # 预览模式（指定目录）
    python fix_nested_structure.py /path/to/dir -f  # 执行操作（指定目录）
    python fix_nested_structure.py --dir /path/to/dir  # 使用 --dir 参数指定目录
    python fix_nested_structure.py -f -v            # 执行操作并显示详细信息
    python fix_nested_structure.py --recursive       # 递归处理当前目录的所有子目录
    python fix_nested_structure.py -r -f            # 递归处理并执行操作
    python fix_nested_structure.py --subdirs         # 仅处理子目录（不处理主目录）
    """)


def main():
    """主函数"""
    args = sys.argv[1:]

    # 解析命令行参数
    force_mode = False
    verbose_mode = False
    recursive_mode = False
    subdirs_only = False
    target_dir = "."

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ['--help', '-h']:
            show_help()
            return
        elif arg in ['--force', '-f']:
            force_mode = True
        elif arg in ['--verbose', '-v']:
            verbose_mode = True
        elif arg in ['--recursive', '-r']:
            recursive_mode = True
        elif arg in ['--subdirs', '-s']:
            subdirs_only = True
        elif arg == '--dir' or arg == '-d':
            if i + 1 < len(args):
                target_dir = args[i + 1]
                i += 1
            else:
                print("错误: --dir 参数需要指定目录路径")
                show_help()
                return
        elif not arg.startswith('--') and not arg.startswith('-'):
            # 如果是不带连字符的参数，认为是目录路径
            target_dir = arg
        else:
            print(f"未知参数: {arg}")
            show_help()
            return
        i += 1

    # 检查目录是否存在
    if not Path(target_dir).exists():
        print(f"错误: 目录不存在 - {target_dir}")
        return

    if not Path(target_dir).is_dir():
        print(f"错误: 路径不是目录 - {target_dir}")
        return

    try:
        if recursive_mode:
            # 递归处理所有子目录
            print(f"递归处理模式: {target_dir}")
            result = fix_nested_subdirectories(
                target_dir,
                force_execute=force_mode,
                verbose=verbose_mode
            )

            if verbose_mode:
                print(f"\n最终结果: {'成功' if result['success'] else '部分失败'}")
                print(f"处理的子目录: {result['processed_subdirs']}/{result['total_subdirs']}")
                print(f"总计修复: {result['total_success']} 个嵌套结构")

        elif subdirs_only:
            # 仅处理子目录，不处理主目录
            print(f"仅处理子目录模式: {target_dir}")
            result = fix_nested_subdirectories(
                target_dir,
                force_execute=force_mode,
                verbose=verbose_mode
            )

            if verbose_mode:
                print(f"\n最终结果: {'成功' if result['success'] else '部分失败'}")
                print(f"处理的子目录: {result['processed_subdirs']}/{result['total_subdirs']}")
                print(f"总计修复: {result['total_success']} 个嵌套结构")

        else:
            # 标准模式：仅处理指定目录
            print(f"标准模式: {target_dir}")
            fix_nested_structure(target_dir, dry_run=not force_mode)

    except KeyboardInterrupt:
        print("\n操作被用户中断")
    except Exception as e:
        print(f"执行过程中发生错误: {str(e)}")
        if verbose_mode:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()