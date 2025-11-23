import asyncio
import os
from typing import Optional

from loguru import logger
from tenacity import (
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from alist_mikananirss import utils
from alist_mikananirss.alist import Alist
from alist_mikananirss.alist.tasks import (
    AlistDownloadTask,
    AlistTask,
    AlistTaskState,
    AlistTaskType,
    AlistTransferTask,
)
from alist_mikananirss.common.database import SubscribeDatabase
from alist_mikananirss.utils.torrent_converter import batch_convert_torrents_to_magnets
from alist_mikananirss.websites.models import ResourceInfo

from ..utils import FixedSizeSet, Singleton
from .notification_sender import NotificationSender
from .renamer import AnimeRenamer
from .webdav_fixer import WebDAVNestedFixer


class TaskMonitor:
    NORMAL_STATUS = [
        AlistTaskState.Pending,
        AlistTaskState.Running,
        AlistTaskState.StateBeforeRetry,
        AlistTaskState.StateWaitingRetry,
    ]

    def __init__(
        self,
        alist_client: Alist,
        db: SubscribeDatabase,
        use_renamer: bool,
        need_notification: bool,
        enable_webdav_fix: bool = False,
        webdav_fixer=None,
    ):
        self.alist_client = alist_client
        self.db = db
        self.uuid_set = FixedSizeSet()
        self.use_renamer = use_renamer
        self.need_notification = need_notification
        self.running_tasks: list[AlistTask] = []
        self.task_resource_map: dict[AlistTask, ResourceInfo] = {}
        self._webdav_fix_enabled = enable_webdav_fix
        self.enable_webdav_fix = enable_webdav_fix
        self.webdav_fixer = webdav_fixer
        self._prefetched_transfer_tasks: list[AlistTransferTask] | None = None

        self.lock = asyncio.Lock()
        self.coroutine = None

    async def _fetch_remote_tasks(self):
        """获取远程任务列表"""
        try:
            download_tasks = await self.alist_client.get_task_list(
                AlistTaskType.DOWNLOAD
            )
            transfer_tasks = await self.alist_client.get_task_list(
                AlistTaskType.TRANSFER
            )
            return download_tasks + transfer_tasks
        except Exception as e:
            logger.error(f"Error when getting task list: {e}")
            return []

    def _refresh_task(
        self, old_task_list: list[AlistTask], new_task_list: list[AlistTask]
    ):
        new_tid_map = {task.tid: task for task in new_task_list}
        for task in old_task_list:
            if task.tid not in new_tid_map:
                logger.warning(f"Task {task.tid} not found in remote task list")
                continue

            new_task = new_tid_map[task.tid]
            task.__dict__.update(new_task.__dict__)
            logger.debug(
                f"Checking {task} state: {task.state} progress: {task.progress:.2f}%"
            )

    @retry(
        stop=stop_after_attempt(7),
        wait=wait_exponential(multiplier=0.5, min=1, max=15),
        retry=retry_if_result(lambda x: x is None),
        retry_error_callback=lambda _: None,
    )
    async def _find_transfer_task(
        self, download_task: AlistDownloadTask, transfer_task_list: list[AlistTransferTask] | None = None
    ) -> Optional[AlistTransferTask]:
        """Find the transfer task that is related to the download task

        Args:
            download_task (AlistDownloadTask): The download task to find the transfer task for
            transfer_task_list (list[AlistTransferTask] | None): Optional pre-fetched transfer task list

        Returns:
            Optional[AlistTransferTask]: The transfer task if found, None otherwise
        """
        try:
            if transfer_task_list is None:
                transfer_task_list = self._prefetched_transfer_tasks
            if transfer_task_list is None:
                transfer_task_list = await self.alist_client.get_task_list(AlistTaskType.TRANSFER)
        except Exception as e:
            logger.warning(f"Error when getting transfer task list: {e}")
            return None
        return self._select_transfer_task(download_task, transfer_task_list)

    def _select_transfer_task(
        self, download_task: AlistDownloadTask, transfer_task_list: list[AlistTransferTask]
    ) -> Optional[AlistTransferTask]:
        # Filter out the transfer tasks by start_time and state
        transfer_task_list = [
            task
            for task in transfer_task_list
            if (
                # 1. The transfer task is not already linked
                task.uuid not in self.uuid_set
                # 2. It's a video file
                and utils.is_video(task.target_path)
                # 3. It's created after the download task
                and task.start_time > download_task.start_time
                # 4. The transfer task is in a valid state
                and task.state
                in [
                    AlistTaskState.Pending,
                    AlistTaskState.Running,
                    AlistTaskState.Succeeded,
                ]
                # 5. Same anime, same season
                and download_task.download_path in task.target_path
            )
        ]
        if len(transfer_task_list) == 0:
            return None
        # Sort by start time, the latest one first
        transfer_task_list.sort(key=lambda x: x.start_time, reverse=True)
        matched_tf_task = transfer_task_list[0]
        self.uuid_set.add(matched_tf_task.uuid)
        logger.debug(f"Linked [{download_task.url}] to {matched_tf_task.uuid}")
        return matched_tf_task

    def _find_transfer_task_optimized(
        self, download_task: AlistDownloadTask, all_transfer_tasks: list[AlistTransferTask]
    ) -> Optional[AlistTransferTask]:
        """Optimized version of _find_transfer_task that uses pre-fetched transfer task list

        Args:
            download_task (AlistDownloadTask): The download task to find the transfer task for
            all_transfer_tasks (list[AlistTransferTask]): Pre-fetched list of all transfer tasks

        Returns:
            Optional[AlistTransferTask]: The transfer task if found, None otherwise
        """
        return self._select_transfer_task(download_task, all_transfer_tasks)

    async def _post_process(self, task: AlistTask, resource: ResourceInfo):
        "Something to do after download task success"
        logger.info(f"Download {resource.resource_title} success")
        remote_filepath = None
        if self.use_renamer:
            # Get target path from different task types
            if task.task_type == AlistTaskType.TRANSFER:
                remote_filepath = getattr(task, "target_path", None)
            elif task.task_type == AlistTaskType.DOWNLOAD:
                # For download tasks, construct path from download_path and name
                name = getattr(task, "name", None)
                download_path = getattr(task, "download_path", None)
                if name and download_path:
                    remote_filepath = f"{download_path}/{name}"
                else:
                    logger.warning(
                        f"Cannot determine remote filepath for download task {getattr(task, 'tid', 'unknown')}, skip renaming"
                    )
            else:
                logger.warning(f"Unknown task type: {task.task_type}")

        if self.use_renamer and remote_filepath:
            await AnimeRenamer.rename(remote_filepath, resource)
        if self.need_notification and NotificationSender in Singleton._instances:
            await NotificationSender.add_resource(resource)

    async def _process_successed_tasks(self, task_list: list[AlistTask]):
        """Process the successed tasks

        Args:
            task_list (list[AlistTask]): The task list to process
        """
        # Batch fetch transfer tasks to reduce API calls
        download_tasks = [task for task in task_list if task.task_type == AlistTaskType.DOWNLOAD]
        transfer_tasks = [task for task in task_list if task.task_type == AlistTaskType.TRANSFER]

        # Process transfer tasks directly
        for task in transfer_tasks:
            resource = self.task_resource_map[task]
            await self._post_process(task, resource)

        # Batch process download tasks
        if download_tasks:
            try:
                # Single API call for all download tasks
                all_transfer_tasks = await self.alist_client.get_task_list(AlistTaskType.TRANSFER)
                self._prefetched_transfer_tasks = all_transfer_tasks

                for task in download_tasks:
                    tf_task = await self._find_transfer_task(task)
                    if tf_task is None:
                        # No transfer task found, assume direct download (e.g., 115 Cloud internal storage)
                        resource = self.task_resource_map[task]
                        logger.info(f"No transfer task needed for [{resource.resource_title}], processing directly")
                        await self._post_process(task, resource)
                    else:
                        # Transfer task found, monitor it for completion
                        self.running_tasks.append(tf_task)
                        self.task_resource_map[tf_task] = self.task_resource_map[task]
            except Exception as e:
                logger.error(f"Error when batch processing transfer tasks: {e}")
                # Fallback to individual processing
                for task in download_tasks:
                    resource = self.task_resource_map[task]
                    await self._post_process(task, resource)
            finally:
                self._prefetched_transfer_tasks = None

    async def _process_failed_tasks(self, task_list: list[AlistTask]):
        """Process the failed tasks

        Args:
            task_list (list[AlistTask]): The task list to process
        """
        for task in task_list:
            resource = self.task_resource_map[task]
            logger.error(
                f"{type(task)} of [{resource.resource_title}] failed: {task.error}"
            )
            await self.db.delete_by_resource_title(resource.resource_title)

    async def monitor(self, task: AlistTask, resource_info: ResourceInfo):
        """Start monitor the download task.

        Args:
            task (AlistTask): Download task object
            resource_info (ResourceInfo): The resource info which is related to the task
        """
        async with self.lock:
            self.running_tasks.append(task)
            self.task_resource_map[task] = resource_info
            if (
                self.coroutine is None
                or self.coroutine.done()
                or self.coroutine.cancelled()
            ):
                logger.debug("Createing a new monitor task")
                self.coroutine = asyncio.create_task(self.run())

    async def run(self):
        initial_task_count = len(self.running_tasks)
        logger.debug(f"Task monitor started with {initial_task_count} running task(s)")

        # Adaptive polling interval
        poll_interval = 0.5  # Start with 0.5 seconds for faster response
        consecutive_empty_checks = 0

        while len(self.running_tasks) > 0:
            # 1. Get remote task list
            async with self.lock:
                new_task_list = await self._fetch_remote_tasks()
                if not new_task_list:
                    consecutive_empty_checks += 1
                    # Increase poll interval if we keep getting empty results
                    if consecutive_empty_checks > 3:
                        poll_interval = min(poll_interval * 1.5, 3.0)  # Max 3 seconds
                    await asyncio.sleep(poll_interval)
                    continue

                consecutive_empty_checks = 0
                # Reset poll interval when we get data
                poll_interval = 0.5

                # 2. Update running tasks state
                self._refresh_task(self.running_tasks, new_task_list)

                # 3. Process finished tasks
                successed_task = []
                failed_task = []
                for task in self.running_tasks:
                    if task.state == AlistTaskState.Succeeded:
                        successed_task.append(task)
                    elif task.state not in self.NORMAL_STATUS:
                        failed_task.append(task)

                # 4. update running tasks and log before processing
                tasks_to_remove = successed_task + failed_task
                completed_count = len(successed_task)
                failed_count = len(failed_task)
                remaining_count = len(self.running_tasks) - len(tasks_to_remove)

                # Log batch completion if tasks were processed
                if tasks_to_remove and (completed_count > 0 or failed_count > 0):
                    logger.info(f"Task batch completed: {completed_count} succeeded, {failed_count} failed, {remaining_count} remaining")

                await self._process_successed_tasks(successed_task)
                await self._process_failed_tasks(failed_task)

                for task in tasks_to_remove:
                    self.running_tasks.remove(task)
                    del self.task_resource_map[task]

            # Adaptive sleep: shorter interval when more tasks are running
            base_interval = 0.5 if len(self.running_tasks) > 5 else 1.0
            await asyncio.sleep(base_interval)

        logger.info("All download tasks completed successfully")

        # 执行WebDAV嵌套目录修复（如果启用）
        await self._execute_webdav_fix_if_needed()

    async def has_running_tasks(self) -> bool:
        async with self.lock:
            return len(self.running_tasks) > 0

    async def _execute_webdav_fix_if_needed(self):
        """在所有下载任务完成后执行WebDAV嵌套目录修复（如果启用）"""
        try:
            # 检查全局是否启用webdav-fix
            if not getattr(self, 'enable_webdav_fix', False):
                logger.debug("WebDAV修复功能未启用，跳过嵌套目录修复")
                return

            logger.info("开始执行WebDAV嵌套目录修复...")

            # 使用预初始化的WebDAV修复器
            if not self.webdav_fixer:
                logger.error("WebDAV修复器未初始化，无法执行修复")
                return

            # 设置为详细模式用于执行时的日志输出
            self.webdav_fixer.verbose = True
            fixer = self.webdav_fixer

            # 执行修复（使用配置文件中的设置）
            result = await fixer.fix_nested_structure()

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

    async def wait_finished(self):
        if self.coroutine and not self.coroutine.done():
            await self.coroutine


class DownloadManager(metaclass=Singleton):
    def __init__(
        self,
        alist_client: Alist,
        base_download_path: str,
        use_renamer: bool = False,
        need_notification: bool = False,
        db: SubscribeDatabase = None,
        convert_torrent_to_magnet: bool = False,
        enable_webdav_fix: bool = False,
        webdav=None,
        webdav_fixer=None,
    ):
        self.alist_client = alist_client
        self.base_download_path = base_download_path
        self.db = db
        self.convert_torrent_to_magnet = convert_torrent_to_magnet
        self.enable_webdav_fix = enable_webdav_fix
        self.webdav = webdav  # 保存完整的 webdav 配置对象
        self.webdav_fixer = webdav_fixer  # 预初始化的 WebDAV 修复器
        self.task_monitor = TaskMonitor(
            alist_client=alist_client,
            db=db,
            use_renamer=use_renamer,
            need_notification=need_notification,
            enable_webdav_fix=enable_webdav_fix,
            webdav_fixer=webdav_fixer,
        )

    @classmethod
    def initialize(
        cls,
        alist_client: Alist,
        base_download_path: str,
        use_renamer: bool = False,
        need_notification: bool = False,
        db: SubscribeDatabase = None,
        convert_torrent_to_magnet: bool = False,
        enable_webdav_fix: bool = False,
        webdav=None,
        webdav_fixer=None,
    ) -> None:
        cls(
            alist_client=alist_client,
            base_download_path=base_download_path,
            use_renamer=use_renamer,
            need_notification=need_notification,
            db=db,
            convert_torrent_to_magnet=convert_torrent_to_magnet,
            enable_webdav_fix=enable_webdav_fix,
            webdav=webdav,
            webdav_fixer=webdav_fixer,
        )

    def _build_download_path(self, resource: ResourceInfo) -> str:
        """build the download path based on the anime name and season
        The result looks like this: base_download_path/AnimeName/Season {season} \n
        if the anime name is not available, use the base download path

        Args:
            resource (ResourceInfo)

        Returns:
            str: new download path
        """
        download_path = self.base_download_path
        if resource.anime_name:
            # Replace illegal characters in the anime_name
            illegal_chars = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]
            anime_name = resource.anime_name
            for char in illegal_chars:
                anime_name = anime_name.replace(char, " ")
            download_path = os.path.join(download_path, anime_name)
            # Need to compare with None, or when seaon=0 will be ignored
            if resource.season is not None:
                download_path = os.path.join(download_path, f"Season {resource.season}")
        return download_path

    async def download(
        self, new_resources: list[ResourceInfo]
    ) -> list[AlistDownloadTask]:
        """Create alist offline download task

        Args:
            new_resources (list[ResourceInfo]): resources list

        Returns:
            list[AlistDownloadTask]: Successful download tasks
        """
        # Generate a mapping of download paths to resources
        # facilitating batch creation of download tasks and reducing requests to the Alist API
        ## mapping of {download_path: [torrent_url]}
        path_urls: dict[str, list[str]] = {}
        # Also keep track of resource info for logging
        path_resources: dict[str, list[ResourceInfo]] = {}

        for resource in new_resources:
            download_path = self._build_download_path(resource)
            path_urls.setdefault(download_path, []).append(resource.torrent_url)
            path_resources.setdefault(download_path, []).append(resource)

        # Torrent URLs are already converted to magnet links in RSS monitor
        # Skip redundant conversion to avoid duplicate tasks

        # start to request the Alist Download API
        task_list = []
        for download_path, urls in path_urls.items():
            try:
                task_list += await self.alist_client.add_offline_download_task(
                    download_path, urls
                )
                resources = path_resources.get(download_path, [])
                logger.info(
                    f"Start to download {len(urls)} resources to [{download_path}]"
                )
                # Log which resources are being downloaded
                for resource in resources:
                    logger.debug(f"Downloading: {resource.resource_title}")
            except Exception as e:
                logger.error(f"Error when add offline download task: {e}")
                continue
        return task_list

    @classmethod
    async def add_download_tasks(cls, resources: list[ResourceInfo]):
        instance = cls()
        dl_tasks = await instance.download(resources)
        for dl_task in dl_tasks:
            matched_resource = None
            for resource in resources:
                if resource.torrent_url == dl_task.url:
                    matched_resource = resource
                    break
            if not matched_resource:
                logger.error(f"Can't matched download task [{dl_task.url}] to resource")
                continue
            await instance.db.insert_resource_info(matched_resource)
            await instance.task_monitor.monitor(dl_task, matched_resource)

    async def has_active_tasks(self) -> bool:
        if hasattr(self, "task_monitor") and self.task_monitor:
            return await self.task_monitor.has_running_tasks()
        return False
