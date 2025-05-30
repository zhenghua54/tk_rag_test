"""文件工具方法"""

import os
import hashlib
from config.settings import Config


def _get_file_info(file: str) -> dict:
    """获取文件信息

    Args:
        file (str): 文件路径

    Returns:
        dict: 文件信息，包含 doc_id、source_document_name、source_document_type 等
    """
    # 获取文件基础名称
    file_base = os.path.basename(file)
    # 获取文件路径
    file_path = os.path.abspath(file)
    # 获取文件类型
    file_type = os.path.splitext(file_base)[-1]
    # 获取文件名称
    file_name = os.path.splitext(file_base)[0]

    # 获取文件 SHA256 哈希值
    file_sha256 = compute_file_hash(file)

    # 构建文件信息数据
    # PDF 文件直接更新 PDF 文件路径
    if file_type == '.pdf':
        file_info = {
            'doc_id': file_sha256,
            'source_document_name': file_name,
            'source_document_type': file_type,
            'source_document_pdf_path': file_path,
        }
    else:
        file_info = {
            'doc_id': file_sha256,
            'source_document_name': file_name,
            'source_document_type': file_type,
            'source_document_path': file_path,
        }

    return file_info

def file_filter(path: str) -> list[dict]:
    """文档过滤, 去除系统文件和配置文件中未指定的文件格式

    Args:
        path (str): 源文件路径

    Returns:
        list[dict]: 文件信息列表
    """
    file_infos = []
    for root, dirs, files in os.walk(path):
        for file in files:
            # 跳过系统文件
            if file.startswith('.'):
                continue
            # 跳过配置文件中未指定格式的文件
            if not file.endswith(tuple(Config.SUPPORTED_FILE_TYPES['all'])):
                continue
            file_info = _get_file_info(os.path.join(root, file))
            file_infos.append(file_info)
        if len(dirs) > 0:
            for d in dirs:
                file_filter(os.path.join(root, d))
    return file_infos


def compute_file_hash(file: str, algo: str = "sha256") -> str:
    """计算文件内容的哈希值

    Args:
        file (str): 文件路径
        algo (str): 哈希算法，默认为 "sha256"

    Returns:
        str: 文件的 SHA256 哈希值
    """
    hasher = hashlib.new(algo)
    with open(file, "rb") as f:
        # 逐块读取文件内容（8K）以避免内存问题
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()



