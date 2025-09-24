import asyncio
import aiohttp
import bencodepy
import hashlib
import base64
import struct
from typing import Optional
from urllib.parse import quote
from loguru import logger


class TorrentToMagnetConverter:
    """Convert torrent files to magnet links"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def convert_torrent_to_magnet(self, torrent_url: str) -> Optional[str]:
        """Convert torrent file URL to magnet link

        Args:
            torrent_url: URL of the torrent file

        Returns:
            Magnet link if successful, None otherwise
        """
        try:
            # Download torrent file
            torrent_data = await self._download_torrent(torrent_url)
            if not torrent_data:
                return None

            # Parse torrent data
            magnet_link = self._create_magnet_from_torrent_data(torrent_data)
            if magnet_link:
                logger.debug(f"Converted {torrent_url} to magnet link")

            return magnet_link
        except Exception as e:
            logger.error(f"Error converting torrent to magnet: {e}")
            return None

    async def _download_torrent(self, torrent_url: str) -> Optional[bytes]:
        """Download torrent file content"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                )

            async with self.session.get(torrent_url) as response:
                response.raise_for_status()
                return await response.read()
        except Exception as e:
            logger.error(f"Error downloading torrent from {torrent_url}: {e}")
            return None

    def _create_magnet_from_torrent_data(self, torrent_data: bytes) -> Optional[str]:
        """Create magnet link from torrent data"""
        try:
            # Decode torrent data
            torrent_info = bencodepy.decode(torrent_data)

            # Get info hash
            info = torrent_info[b"info"]
            info_hash = hashlib.sha1(bencodepy.encode(info)).hexdigest()

            # Build magnet link
            magnet_parts = [f"magnet:?xt=urn:btih:{info_hash}"]

            # Add display name if available
            if b"name" in info:
                name = info[b"name"].decode("utf-8", errors="ignore")
                magnet_parts.append(f"&dn={quote(name)}")

            # Add trackers if available
            if b"announce" in torrent_info:
                tracker = torrent_info[b"announce"].decode("utf-8", errors="ignore")
                magnet_parts.append(f"&tr={quote(tracker)}")

            # Add tracker list if available
            if b"announce-list" in torrent_info:
                for tracker_list in torrent_info[b"announce-list"]:
                    for tracker in tracker_list:
                        tracker_str = tracker.decode("utf-8", errors="ignore")
                        magnet_parts.append(f"&tr={quote(tracker_str)}")

            return "".join(magnet_parts)

        except Exception as e:
            logger.error(f"Error creating magnet from torrent data: {e}")
            return None

    async def batch_convert(self, torrent_urls: list[str]) -> list[str]:
        """Convert multiple torrent URLs to magnet links

        Args:
            torrent_urls: List of torrent URLs

        Returns:
            List of magnet links (None for failed conversions)
        """
        tasks = []
        for url in torrent_urls:
            tasks.append(self.convert_torrent_to_magnet(url))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        magnet_links = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error converting {torrent_urls[i]}: {result}")
                magnet_links.append(None)
            else:
                magnet_links.append(result)

        return magnet_links


async def convert_torrent_to_magnet(
    torrent_url: str, timeout: int = 30
) -> Optional[str]:
    """Convenience function to convert single torrent to magnet"""
    async with TorrentToMagnetConverter(timeout) as converter:
        return await converter.convert_torrent_to_magnet(torrent_url)


async def batch_convert_torrents_to_magnets(
    torrent_urls: list[str], timeout: int = 30
) -> list[str]:
    """Convenience function to convert multiple torrents to magnets"""
    async with TorrentToMagnetConverter(timeout) as converter:
        return await converter.batch_convert(torrent_urls)
