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
            else:
                await DownloadManager.add_download_tasks(new_resources)
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
