import argparse
import asyncio
import os
import sys

from loguru import logger

from alist_mikananirss import (
    AnimeRenamer,
    AppConfig,
    BotAssistant,
    ConfigManager,
    DownloadManager,
    NotificationSender,
    RegexFilter,
    RemapperManager,
    RssMonitor,
    SubscribeDatabase,
)
from alist_mikananirss.alist import Alist
from alist_mikananirss.bot import BotFactory, NotificationBot
from alist_mikananirss.core.webdav_fixer import WebDAVNestedFixer
from alist_mikananirss.extractor import Extractor, LLMExtractor, create_llm_provider


def init_logging(cfg: AppConfig):
    log_level = cfg.dev.log_level
    logger.remove()

    # 确保日志目录存在
    os.makedirs("log", exist_ok=True)

    # 使用loguru的动态日期格式化功能
    log_filename = "log/alist_mikanrss_{time:YYYY-MM-DD}.log"
    logger.add(
        log_filename, rotation="00:00", retention="7 days", level=log_level, mode="a"
    )
    logger.add(sys.stderr, level=log_level)


def init_proxies(cfg: AppConfig):
    proxies = cfg.common.proxies
    if not proxies:
        return
    if "http" in proxies:
        os.environ["HTTP_PROXY"] = proxies["http"]
    if "https" in proxies:
        os.environ["HTTPS_PROXY"] = proxies["https"]


def init_notification(cfg: AppConfig):
    notification_bots = []
    if not cfg.notification.enable:
        return

    for bot_cfg in cfg.notification.bots:
        bot_kwargs = bot_cfg.model_dump(exclude={"bot_type"})

        try:
            bot = BotFactory.create_bot(bot_cfg.bot_type, **bot_kwargs)
            notification_bots.append(NotificationBot(bot))
        except ValueError as e:
            logger.error(f"Failed to create notification bot: {e}")

    if not notification_bots:
        logger.warning(
            "Notification enabled but no valid bots were configured or created."
        )
        cfg.notification.enable = False
        return

    NotificationSender.initialize(notification_bots, cfg.notification.interval_time)


async def run_webdav_fix(args, cfg):
    """运行WebDAV修复功能"""
    logger.info("启动WebDAV嵌套目录修复工具")

    # alist
    alist_client = Alist(cfg.alist.base_url, cfg.alist.token, cfg.alist.downloader)
    alist_ver = await alist_client.get_alist_ver()
    if alist_ver < "3.42.0":
        raise ValueError(f"Unsupported Alist version: {alist_ver}")

    # 检查WebDAV修复器是否启用
    if not cfg.webdav.fixer.enable:
        logger.warning("WebDAV修复功能未启用，请在配置文件中设置 webdav.fixer.enable: true")
        return False

    # 创建WebDAV修复器，使用配置文件中的WebDAV设置
    try:
        fixer = WebDAVNestedFixer(
            alist_client=alist_client,
            verbose=args.verbose,
            url=cfg.webdav.url,
            username=cfg.webdav.username,
            password=cfg.webdav.password,
            config=cfg
        )
    except Exception as e:
        logger.error(f"WebDAV修复器初始化失败: {str(e)}")
        raise

    try:
        # 确定使用的参数值：命令行参数优先，配置文件作为默认值
        target_dir = args.dir  # 如果用户未指定，则为None，将使用配置文件的download_path
        dry_run = None if args.force else None  # 如果指定了force，则dry_run=False，否则使用配置文件设置
        handle_conflicts = args.conflicts  # 如果用户未指定，则为None，将使用配置文件的conflict_strategy
        recursive = args.recursive if args.recursive else None  # 如果用户指定了递归，则使用该值，否则使用配置文件设置

        # 执行修复
        result = await fixer.fix_nested_structure(
            target_dir=target_dir,
            dry_run=dry_run,
            handle_conflicts=handle_conflicts,
            recursive=recursive
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

        return result['success']

    finally:
        await alist_client.close()


async def run_webui(args, cfg):
    """运行WebUI服务器"""
    logger.info("启动WebUI服务器")

    try:
        import uvicorn
        from alist_mikananirss.webui.server import app

        # 优先使用命令行参数，其次使用配置文件
        host = args.host if hasattr(args, 'host') and args.host else cfg.webui.host
        port = args.port if hasattr(args, 'port') and args.port else cfg.webui.port
        debug = args.verbose if hasattr(args, 'verbose') else cfg.webui.debug

        # 设置Uvicorn配置
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info" if debug else "warning",
            access_log=debug,
            reload=debug  # 调试模式下启用热重载
        )

        server = uvicorn.Server(config)

        logger.info(f"WebUI服务器启动成功: http://{host}:{port}")
        if debug:
            logger.info("调试模式已启用，支持热重载")
        logger.info("按 Ctrl+C 停止服务器")

        await server.serve()

    except ImportError:
        logger.error("WebUI依赖未安装，请安装: pip install fastapi uvicorn jinja2 python-multipart")
        return False
    except Exception as e:
        logger.error(f"WebUI服务器启动失败: {str(e)}")
        return False

    return True


async def run_monitor_only(args, cfg):
    """仅运行RSS监控功能（原有逻辑）"""
    logger.info("启动RSS监控功能")

    # proxy
    init_proxies(cfg)

    # database
    db = await SubscribeDatabase.create()

    # alist
    alist_client = Alist(cfg.alist.base_url, cfg.alist.token, cfg.alist.downloader)
    alist_ver = await alist_client.get_alist_ver()
    if alist_ver < "3.42.0":
        raise ValueError(f"Unsupported Alist version: {alist_ver}")

    # WebDAV fixer
    webdav_fixer = None
    if cfg.webdav.fixer.enable:
        try:
            webdav_fixer = WebDAVNestedFixer(
                alist_client=alist_client,
                verbose=False,  # 启动时不显示详细输出
                url=cfg.webdav.url,
                username=cfg.webdav.username,
                password=cfg.webdav.password,
                config=cfg
            )
            logger.info("WebDAV修复器初始化成功")
        except Exception as e:
            logger.error(f"WebDAV修复器初始化失败: {str(e)}")
            # 如果配置错误但启用了修复功能，应该抛出异常
            if cfg.webdav.fixer.execute_mode:
                raise

    # download manager
    DownloadManager.initialize(
        alist_client=alist_client,
        base_download_path=cfg.alist.download_path,
        use_renamer=cfg.rename.enable,
        need_notification=cfg.notification.enable,
        db=db,
        convert_torrent_to_magnet=cfg.alist.convert_torrent_to_magnet,
        enable_webdav_fix=cfg.webdav.fixer.enable,
        webdav=cfg.webdav,
        webdav_fixer=webdav_fixer,
    )

    # extractor
    if cfg.rename.enable:
        extractor_cfg = cfg.rename.extractor
        provider_kwargs = extractor_cfg.model_dump(
            exclude={"extractor_type", "output_type"}
        )
        try:
            llm_provider = create_llm_provider(
                extractor_cfg.extractor_type, **provider_kwargs
            )
            extractor = LLMExtractor(llm_provider, extractor_cfg.output_type)
        except ValueError as e:
            logger.error(f"Failed to create LLM provider: {e}")
            raise
        Extractor.initialize(extractor)

        AnimeRenamer.initialize(alist_client, cfg.rename.rename_format)

    # remapper
    if cfg.rename.remap.enable:
        cfg_path = cfg.rename.remap.cfg_path
        RemapperManager.load_remappers_from_cfg(cfg_path)

    # rss monitor
    regex_filter = RegexFilter()
    filters_name = cfg.mikan.filters
    regex_pattern = cfg.mikan.regex_pattern
    regex_filter.update_regex(regex_pattern)
    for name in filters_name:
        regex_filter.add_pattern(name)

    subscribe_url = cfg.mikan.subscribe_url
    rss_monitor = RssMonitor(
        subscribe_urls=subscribe_url,
        db=db,
        filter=regex_filter,
        use_extractor=cfg.rename.enable,
        convert_torrent_to_magnet=cfg.alist.convert_torrent_to_magnet,
    )
    rss_monitor.set_interval_time(cfg.common.interval_time)

    tasks = []
    tasks.append(rss_monitor.run())
    # notification
    if cfg.notification.enable:
        init_notification(cfg)
        tasks.append(NotificationSender.run())

    # Initialize bot assistant
    if cfg.bot_assistant.enable:
        # Only telegram bot is supported now
        if cfg.bot_assistant.bots[0].bot_type == "telegram":
            bot_assistant = BotAssistant(cfg.bot_assistant.bots[0].token, rss_monitor)
            tasks.append(bot_assistant.run())

    try:
        await asyncio.gather(*tasks)
    finally:
        # cleanup after program exit
        await db.close()
        await alist_client.close()
        if cfg.bot_assistant.enable:
            await bot_assistant.stop()


async def run():
    parser = argparse.ArgumentParser(description="Alist Mikanani RSS 工具集")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # RSS监控命令（默认）
    monitor_parser = subparsers.add_parser('monitor', help='启动RSS监控（默认命令）')
    monitor_parser.add_argument(
        "--config",
        default="config.yaml",
        help="配置文件路径",
    )

    # WebUI命令
    webui_parser = subparsers.add_parser('webui', help='启动WebUI服务器')
    webui_parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="配置文件路径",
    )
    webui_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="WebUI服务器绑定地址 (默认: 0.0.0.0)",
    )
    webui_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="WebUI服务器端口 (默认: 8080)",
    )
    webui_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="启用详细日志输出",
    )

    # WebDAV修复命令
    webdav_parser = subparsers.add_parser('webdav-fix', help='修复WebDAV嵌套目录结构')
    webdav_parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="配置文件路径",
    )
    webdav_parser.add_argument(
        "--dir", "-d",
        default=None,
        help="指定要处理的目录路径（如果未指定，将使用配置文件中的download_path）",
    )
    webdav_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="执行实际操作（默认为预览模式，或使用配置文件中的execute_mode设置）",
    )
    webdav_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细输出",
    )
    webdav_parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="递归扫描子目录（默认使用配置文件中的recursive_scan设置）",
    )
    webdav_parser.add_argument(
        "--conflicts", "-C",
        choices=["skip", "rename", "overwrite"],
        default=None,
        help="冲突处理策略 (skip|rename|overwrite，默认使用配置文件中的conflict_strategy设置)",
    )

    args = parser.parse_args()

    # 如果没有指定命令，默认启动监控（向后兼容）
    if args.command is None:
        args.command = 'monitor'
        # 为monitor命令创建默认args
        args.config = getattr(args, 'config', 'config.yaml')

    cfg_manager = ConfigManager()
    cfg = cfg_manager.load_config(args.config)
    # logger
    init_logging(cfg)

    logger.info("Loaded config Successfully")
    logger.info(f"Config: \n{cfg}")

    # 根据命令执行不同功能
    if args.command == 'webdav-fix':
        # WebDAV修复功能
        return await run_webdav_fix(args, cfg)
    elif args.command == 'webui':
        # WebUI服务器功能
        return await run_webui(args, cfg)
    elif args.command == 'monitor':
        # RSS监控功能（默认或monitor命令）
        return await run_monitor_only(args, cfg)
    else:
        # 默认启动监控（向后兼容）
        return await run_monitor_only(args, cfg)


def main():
    asyncio.run(run())
