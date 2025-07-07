"""文档状态同步工具:
- 提供文档处理状态同步功能,将本地文档处理状态同步到外部系统.
- 采用关键里程碑策略, 同步成功和失败的关键节点状态.
"""
import time
from typing import Optional

import requests
from requests.exceptions import RequestException, Timeout

from config.global_config import GlobalConfig
from utils.log_utils import logger


class StatusSyncClient:
    """状态同步客户端

    负责将文档处理状态同步到外部系统，支持重试机制和错误处理。
    采用关键里程碑策略，同步成功和失败的关键节点状态。
    """

    def __init__(self):
        """初始化状态同步客户端"""
        self.config = GlobalConfig.STATUS_SYNC_CONFIG
        self.base_url = self.config['base_url'].rstrip('/')
        self.api_path = self.config['api_path']
        self.timeout = self.config['timeout']
        self.retry_attempts = self.config['retry_attempts']
        self.retry_delay = self.config['retry_delay']

        # 获取需要同步的状态映射
        self.status_mapping = GlobalConfig.EXTERNAL_STATUS_MAPPING
        self.failure_statuses = GlobalConfig.FAILURE_STATUSES

    def should_sync_status(self, internal_status: str) -> bool:
        """判断是否需要同步该状态

        Args:
            internal_status (str): 内部状态名称

        Returns:
            bool: 是否需要同步该状态
        """
        return internal_status in self.status_mapping

    def get_external_status(self, internal_status: str) -> Optional[str]:
        """获取对应的外部状态

        Args:
            internal_status (str): 内部状态名称

        Returns:
            Optional[str]: 外部状态名称, 如果不存在则返回None
        """
        return self.status_mapping.get(internal_status)

    def is_failure_status(self, internal_status: str) -> bool:
        """判断是否为失败状态

        Args:
            internal_status (str): 内部状态名称

        Returns:
            bool: 是否为失败状态
        """
        return internal_status in self.failure_statuses

    def sync_document_status(self, doc_id: str, status: str, request_id: str = None) -> bool:
        """同步文档状态到外部系统

        Args:
            doc_id (str): 文档ID
            status (str): 文档状态
            request_id (str, optional): 请求ID,用于追踪请求,默认为None

        Returns:
            bool: 是否同步成功

        Raises:
            ValueError: 参数错误
            RequestException: 网络请求异常, 包括网络错误和超时
        """

        # 检查是否启用状态同步
        if not self.config['enabled']:
            logger.info(
                f"[StatusSyncClient] 状态同步未启用, 跳过同步: request_id={request_id}, doc_id={doc_id}, status={status}")
            return True

        # 参数验证
        if not doc_id or not status:
            raise ValueError("[StatusSyncClient] 参数错误: doc_id 和 status 不能为空")

        # 检查是否需要同步该状态
        if not self.should_sync_status(status):
            logger.info(f"[StatusSyncClient] 状态无需同步: request_id={request_id}, doc_id={doc_id}, status={status}")
            return True

        # 获取外部状态
        external_status = self.get_external_status(status)
        if not external_status:
            logger.warning(
                f"[StatusSyncClient] 未找到外部状态映射: request_id={request_id}, doc_id={doc_id}, status={status}")
            return False

        # 判断是否为失败状态
        is_failure = self.is_failure_status(status)
        status_type = "失败状态" if is_failure else "成功状态"

        # 构建请求 URL
        url = f"{self.base_url}{self.api_path}"

        # 构建请求数据
        payload = {
            "docId": doc_id,
            "status": external_status,
        }

        # 设置请求头
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        logger.info(
            f"[StatusSyncClient] 开始同步{status_type}, request_id={request_id}, doc_id={doc_id}, internal_status={status}, external_status={external_status}, url={url}")

        # 执行请求，支持重试
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )

                # 检查响应状态码
                if response.status_code == 200:
                    response_data = response.json()
                    status_code = response_data.get("statusCode")

                    if status_code == "000000":
                        logger.info(
                            f"[StatusSyncClient] {status_type}同步成功, request_id={request_id}, doc_id={doc_id}, internal_status={status}, external_status={external_status}")
                        return True
                    else:
                        error_msg = response_data.get("message", "未知错误")
                        logger.warning(
                            f"[StatusSyncClient] {status_type}同步失败(业务错误), request_id={request_id}, doc_id={doc_id}, internal_status={status}, external_status={external_status}, error={error_msg}")
                        # 失败状态同步失败时，需要特殊处理，避免前端一直等待
                        if is_failure:
                            logger.error(
                                f"[StatusSyncClient] 失败状态同步失败，前端可能一直处于等待状态, request_id={request_id}, doc_id={doc_id}")
                        return False
                else:
                    logger.warning(
                        f"[StatusSyncClient] {status_type}同步失败(HTTP错误), request_id={request_id}, doc_id={doc_id}, internal_status={status}, external_status={external_status}, status_code={response.status_code}")
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return False

            except Timeout:
                logger.warning(
                    f"[StatusSyncClient] {status_type}同步超时, request_id={request_id}, doc_id={doc_id}, internal_status={status}, external_status={external_status}, attempt={attempt + 1}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                return False

            except RequestException as e:
                logger.error(
                    f"[StatusSyncClient] {status_type}同步请求异常, request_id={request_id}, doc_id={doc_id}, internal_status={status}, external_status={external_status}, error={str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                return False

            except Exception as e:
                logger.error(
                    f"[StatusSyncClient] {status_type}同步未知异常, request_id={request_id}, doc_id={doc_id}, internal_status={status}, external_status={external_status}, error={str(e)}")
                return False

        return False

    def sync_status_safely(self, doc_id: str, status: str, request_id: str = None) -> None:
        """安全同步文档状态(不抛出异常), 包含异常处理和重试机制

        Args:
            doc_id (str): 文档ID
            status (str): 文档状态
            request_id (str, optional): 请求ID,用于追踪请求,默认为None
        """
        try:
            success = self.sync_document_status(doc_id, status, request_id)
            if not success:
                is_failure = self.is_failure_status(status)
                status_type = "失败状态" if is_failure else "成功状态"
                logger.error(
                    f"[StatusSyncClient] {status_type}同步失败, request_id={request_id}, doc_id={doc_id}, status={status}")
        except Exception as e:
            is_failure = self.is_failure_status(status)
            status_type = "失败状态" if is_failure else "成功状态"
            logger.error(
                f"[StatusSyncClient] {status_type}同步异常, request_id={request_id}, doc_id={doc_id}, status={status}, error={str(e)}")


# 全局状态同步客户端实例
_status_sync_client = None


def get_status_sync_client() -> StatusSyncClient:
    """获取状态同步客户端实例(单例模式)

    Returns:
        StatusSyncClient: 状态同步客户端实例
    """
    global _status_sync_client
    if _status_sync_client is None:
        _status_sync_client = StatusSyncClient()
    return _status_sync_client


def sync_status_safely(doc_id: str, status: str, request_id: str = None) -> None:
    """安全同步文档状态(不抛出异常), 包含异常处理和重试机制

    Args:
        doc_id (str): 文档ID
        status (str): 文档状态
        request_id (str, optional): 请求ID,用于追踪请求,默认为None

    Returns:
        bool: 是否同步成功
    """
    client = get_status_sync_client()
    client.sync_status_safely(doc_id, status, request_id)
