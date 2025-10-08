import asyncio

from loguru import logger

from alist_mikananirss import SubscribeDatabase
from alist_mikananirss.websites import Website, WebsiteFactory
from alist_mikananirss.websites.models import ResourceInfo
from alist_mikananirss.utils.torrent_converter import batch_convert_torrents_to_magnets

from .download_manager import DownloadManager
from .filter import RegexFilter
from .remapper import (
    RemapperManager,
)


class RssMonitor:
    def __init__(
        self,
        subscribe_urls: list[str],
        filter: RegexFilter,
        db: SubscribeDatabase,
        use_extractor: bool = False,
        convert_torrent_to_magnet: bool = False,
    ) -> None:
        """The rss feed manager"""
        self.subscribe_urls = subscribe_urls
        self.websites = [
            WebsiteFactory.get_website_parser(url) for url in subscribe_urls
        ]
        self.filter = filter
        self.db = db
        self.use_extractor = use_extractor
        self.convert_torrent_to_magnet = convert_torrent_to_magnet

        self.interval_time = 300

    def set_interval_time(self, interval_time: int):
        self.interval_time = interval_time

    async def get_new_resources(
        self,
        m_websites: list[Website],
        m_filter: RegexFilter,
    ) -> list[ResourceInfo]:
        """Parse all rss url and get the filtered, unique resource info list"""

        async def process_entry(self, website: Website, entry):
            """Parse all rss url and get the filtered, unique resource info list"""
            async with asyncio.Semaphore(8):
                try:
                    resource_info = await website.extract_resource_info(
                        entry, self.use_extractor
                    )
                except Exception as e:
                    logger.error(f"Pass {entry.resource_title} because of error: {e}")
                    return None
                remapper = RemapperManager.match(resource_info)
                if remapper:
                    remapper.remap(resource_info)
                return resource_info

        new_resources_set: set[ResourceInfo] = set()

        for website in m_websites:
            feed_entries = await website.get_feed_entries()
            feed_entries_filted = filter(
                lambda entry: m_filter.filt_single(entry.resource_title),
                feed_entries,
            )
            tasks = []
            for entry in feed_entries_filted:
                if await self.db.is_resource_title_exist(entry.resource_title):
                    continue
                task = asyncio.create_task(process_entry(self, website, entry))
                tasks.append(task)
            results = await asyncio.gather(*tasks)
            for resource_info in results:
                if not resource_info:
                    continue
                new_resources_set.add(resource_info)
                logger.info(f"Find new resource: {resource_info}")

        new_resources = list(new_resources_set)

        # Convert torrent URLs to magnet links if enabled
        if self.convert_torrent_to_magnet:
            logger.info("Converting torrent files to magnet links in RSS monitor...")
            torrent_urls = [resource.torrent_url for resource in new_resources]
            magnet_links = await batch_convert_torrents_to_magnets(torrent_urls)

            # Update resources with magnet links
            for i, resource in enumerate(new_resources):
                if i < len(magnet_links) and magnet_links[i]:
                    old_url = resource.torrent_url
                    resource.torrent_url = magnet_links[i]
                    logger.info(f"Converted {old_url} to magnet link for {resource.resource_title}")
                    logger.debug(f"Original torrent URL: {old_url}")
                    logger.debug(f"New magnet URL: {magnet_links[i]}")
                else:
                    logger.error(f"Failed to convert torrent to magnet for {resource.resource_title}")
                    logger.error(f"Original torrent URL: {resource.torrent_url}")

        return new_resources

    async def run(self):
        while 1:
            logger.info("Start update checking")
            new_resources = await self.get_new_resources(self.websites, self.filter)
            if not new_resources:
                logger.info("No new resources")
                # 没有新资源时，执行一次WebDAV修复检查，处理可能遗漏的问题
                await self._execute_webdav_fix_if_enabled()
                logger.info(f"RSS check completed, next check in {self.interval_time} seconds")
            else:
                resource_count = len(new_resources)
                logger.info(f"Found {resource_count} new resource(s), adding download tasks")
                await DownloadManager.add_download_tasks(new_resources)
                logger.info(f"RSS check completed, download tasks added, next check in {self.interval_time} seconds")
                logger.info("WebDAV修复将在所有下载任务完成后自动执行")
            await asyncio.sleep(self.interval_time)

    async def run_once_with_url(self, url: str):
        logger.info(f"Start update checking for {url}")
        website = WebsiteFactory.get_website_parser(url)
        new_resources = await self.get_new_resources([website], self.filter)
        if not new_resources:
            logger.info("No new resources")
        else:
            await DownloadManager.add_download_tasks(new_resources)
        return new_resources

    async def _execute_webdav_fix_if_enabled(self):
        """执行WebDAV修复（如果启用）"""
        try:
            # 获取DownloadManager实例
            download_manager = DownloadManager()

            # 检查是否启用了WebDAV修复功能
            if not hasattr(download_manager, 'webdav_fixer') or not download_manager.webdav_fixer:
                logger.debug("WebDAV修复器未初始化，跳过嵌套目录修复")
                return

            if not hasattr(download_manager, 'enable_webdav_fix') or not download_manager.enable_webdav_fix:
                logger.debug("WebDAV修复功能未启用，跳过嵌套目录修复")
                return

            logger.info("开始执行WebDAV嵌套目录修复...")

            # 设置为详细模式用于执行时的日志输出
            download_manager.webdav_fixer.verbose = True

            # 执行修复
            result = await download_manager.webdav_fixer.fix_nested_structure()

            # 输出结果
            if result['success']:
                logger.info(f"WebDAV嵌套目录修复完成: 发现{result['total_found']}个问题，成功修复{result['success_count']}个")
                if result['skip_count'] > 0:
                    logger.info(f"跳过{result['skip_count']}个文件")
                if result['error_count'] > 0:
                    logger.warning(f"修复过程中发生{result['error_count']}个错误")
            else:
                logger.error(f"WebDAV嵌套目录修复部分失败: 发现{result['total_found']}个问题，成功修复{result['success_count']}个，错误{result['error_count']}个")
                if result['errors']:
                    logger.error("错误详情:")
                    for error in result['errors'][:3]:  # 只显示前3个错误
                        logger.error(f"  - {error}")
                        if len(result['errors']) > 3:
                            logger.error(f"  ... 还有{len(result['errors']) - 3}个错误")
                            break

        except Exception as e:
            logger.error(f"执行WebDAV嵌套目录修复时发生错误: {str(e)}")
            logger.debug(f"WebDAV修复错误详情: {e}", exc_info=True)
