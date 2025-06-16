"""文件工具方法"""

import requests
import hashlib
import shutil
from pathlib import Path
from typing import List

from config.settings import Config
from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.utils.common.logger import logger


def get_doc_output_path(doc_path: str) -> dict:
    """
    获取文档的输出目录

    Args:
        doc_path (str): 源文档的路径

    Returns:
        dict: 包含以下字段的字典：
            - output_path (str): 该文档的输出根目录
            - output_image_path (str): markdown 的图片文件目录
    """
    doc_path = Path(doc_path)
    # 项目文件处理输出目录
    output_data_dir = Path(Config.PATHS["processed_data"])

    # 根据文件名称,在输出目录下构建自己的输出子目录
    output_path = output_data_dir / doc_path.stem
    output_image_path = output_path / "images"

    return {
        "output_path": str(output_path),
        "output_image_path": str(output_image_path),
        "doc_name": doc_path.stem,
    }


def compute_file_hash(doc_path: str, add_title: bool = True, algo: str = "sha256") -> str:
    """计算文件内容的哈希值

    Args:
        doc_path (str): 文件路径
        add_title (bool): 是否添加标题哈希值, 默认为 True（前期避免重复处理）
        algo (str): 哈希算法，默认为 "sha256"

    Returns:
        str: 文件的 SHA256 哈希值
    """
    hasher = hashlib.new(algo)
    with open(doc_path, "rb") as f:
        # 逐块读取文件内容（8K）以避免内存问题
        while chunk := f.read(8192):
            hasher.update(chunk)

    # 如果需要添加文件名到哈希计算中
    if add_title:
        doc_path = Path(doc_path)
        # 将文件名转换为字节并添加到哈希计算中
        hasher.update(str(doc_path.name).encode('utf-8'))

    return hasher.hexdigest()


def generate_seg_id(content: str) -> str:
    """生成片段ID

    Args:
        content (str): 片段内容

    Returns:
        str: 片段ID（SHA256哈希值）
    """
    return hashlib.sha256(content.encode()).hexdigest()


def truncate_summary(text: str, max_length: int = 4096) -> str:
    """截断摘要文本，确保不超过最大长度

    Args:
        text: 原始文本
        max_length: 最大长度限制，默认4096字符

    Returns:
        截断后的文本
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    # 在最大长度处截断，并添加省略号
    return text[:max_length - 3] + "..."


def delete_path_safely(doc_path: str, error_code: ErrorCode):
    """文件或目录的硬删除"""
    if not doc_path or not isinstance(doc_path, str):
        return
    path = Path(doc_path)
    if not path.exists():
        logger.warning(f"[文件已不存在] path={path}")
        return
    try:
        if path.is_file():
            path.unlink()
            logger.info(f"[硬删除] file={path}")
        elif path.is_dir():
            shutil.rmtree(path)
            logger.info(f"[硬删除] dir={path}")
    except Exception as e:
        logger.error(f"[硬删除失败] path={path}, error_code={error_code.value}, error={str(e)}")
        raise APIException(error_code, str(e)) from e


def download_file_step_by_step(url: str, local_path: str = None, chunk_size: int = 8192):
    """逐步下载网络文档并保存为本地文件

    Args:
        url (str): 网络文档的 URL
        local_path (str): 本地保存路径
        chunk_size (int): 每次下载的字节数，默认 8KB

    Returns:
        local_path (str): 本地保存的文件路径
    """

    try:
        # 从 URL 中获取文件名
        file_name = url.split('/')[-1]
        if not file_name:
            raise APIException(ErrorCode.HTTP_FILE_NOT_FOUND, "无法从URL中获取文件名")

        # 设置本地保存路径
        if local_path is None:
            local_path = str(Path(Config.PATHS["origin_data"]) / file_name)
        else:
            local_path = str(Path(local_path) / file_name)

        # 确保目录存在
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"开始下载文件: {url}")
        logger.debug(f"保存到本地路径: {local_path}")

        with requests.get(url, stream=True, timeout=10) as response:
            response.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:  # 过滤掉 keep-alive 块
                        f.write(chunk)
        logger.debug(f"文件下载完成，保存到: {local_path}")
        return local_path
    except Exception as e:
        raise APIException(ErrorCode.HTTP_FILE_NOT_FOUND, str(e)) from e


def convert_permission_ids_to_list(perm_ids: str) -> List[str]:
    """处理权限ID字符串

    Args:
        perm_ids: 权限ID字符串，可能是 "1" 或 "1,2" 或 None

    Returns:
        List[str]: 处理后的权限ID列表
    """
    if not perm_ids:
        return []
    return [p.strip() for p in perm_ids.split(',') if p.strip()]
