"""文件工具方法"""

import os
import hashlib
import shutil
from pathlib import Path
from typing import Optional

from config.settings import Config
from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.utils.common.logger import logger


def get_file_info(doc_path: str) -> dict:
    """获取文件信息

    Args:
        doc_path (str): 文件路径

    Returns:
        dict: 文件信息，包含 doc_id、source_document_name、source_document_type 等
    """
    doc_path = Path(doc_path)

    # 获取文件 SHA256 哈希值
    file_sha256 = compute_file_hash(str(doc_path.resolve()))

    # 构建文件信息数据
    # PDF 文件直接更新 PDF 文件路径
    if doc_path.suffix == '.pdf':
        file_info = {
            'doc_id': file_sha256,
            'source_document_name': doc_path.stem,
            'source_document_type': doc_path.suffix,
            'source_document_pdf_path': str(doc_path.resolve()),
        }
    else:
        file_info = {
            'doc_id': file_sha256,
            'source_document_name': doc_path.stem,
            'source_document_type': doc_path.suffix,
            'source_document_path': str(doc_path.resolve()),
        }

    return file_info

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


def file_filter(doc_dir: str) -> list[dict]:
    """文档过滤, 去除系统文件和配置文件中未指定的文件格式

    Args:
        doc_dir (str): 源文件路径

    Returns:
        list[dict]: 文件信息列表
    """
    file_infos = []
    doc_dir = Path(doc_dir)
    # 递归获取指定目录下的所有文件及文件夹
    for file in doc_dir.rglob("*"):
        # 非文件或以 '.' 开头的文件（如隐藏文件）直接跳过
        if not file.is_file() or file.name.startswith('.'):
            continue
        if file.suffix not in Config.SUPPORTED_FILE_TYPES["all"]:
            continue
        file_info = get_file_info(str(file.resolve()))
        file_infos.append(file_info)
    return file_infos

def compute_file_hash(doc_path: str, algo: str = "sha256") -> str:
    """计算文件内容的哈希值

    Args:
        doc_path (str): 文件路径
        algo (str): 哈希算法，默认为 "sha256"

    Returns:
        str: 文件的 SHA256 哈希值
    """
    hasher = hashlib.new(algo)
    with open(doc_path, "rb") as f:
        # 逐块读取文件内容（8K）以避免内存问题
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()



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