"""
文件上传模块
1. 接收上传的文件
2. 提取文件信息
3. 存储到 mysql 数据库
"""

import os
import hashlib
from src.utils.common.logger import logger
from config import Config
from src.utils.database.file_db import insert_file_info


def get_file_hash(file: str) -> str:
    """获取文件的哈希值

    Args:
        file (str): 文件路径

    Returns:
        str: 文件的 SHA256 哈希值
    """
    return hashlib.sha256(open(file, 'rb').read()).hexdigest()


def get_file_info(file: str) -> dict:
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
    file_sha256 = get_file_hash(file)

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
            file_info = get_file_info(os.path.join(root, file))
            file_infos.append(file_info)
        if len(dirs) > 0:
            for dir in dirs:
                file_filter(os.path.join(root, dir))
    return file_infos


def update_file_records_in_db(file_paths: list[dict], debug: bool = False) -> None:
    """上传文件信息到数据库

    Args:
        file_paths (list[dict]): 文件路径列表
        debug (bool): 是否开启调试模式，开启后会打印插入的数据信息
    """
    success_count, fail_count = insert_file_info(file_paths, debug)

    if success_count > 0 or fail_count > 0:
        logger.info(f"批量插入完成: 成功 {success_count} 条, 失败 {fail_count} 条")


if __name__ == '__main__':
    raw_data_path = '/Users/jason/Library/CloudStorage/OneDrive-个人/项目/内部企业知识库/文档资料'

    # 上传文件
    file_infos = upload_files(raw_data_path)
    print(file_infos)

    # 将文件信息存储到数据库中，开启调试模式查看插入的数据
    update_file_records_in_db(file_infos, debug=True)
