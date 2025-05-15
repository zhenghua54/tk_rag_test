"""
文件上传模块
1. 接收上传的文件
2. 提取文件信息
3. 存储到 mysql 数据库
"""

import os
import sys

sys.path.append("/")

import hashlib
from rich import print
from config import logger
from src.database.mysql_connect import connect_mysql


# 获取文件的哈希值
def get_file_hash(file: str):
    """获取文件的哈希值
    Args:
        file: 文件
    """
    return hashlib.sha256(open(file, 'rb').read()).hexdigest()


# 上传文件接口
def get_file_info(file: str):
    """上传文件
    Args:
        file: 文件
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
    file_info = {
        'doc_id': file_sha256,
        'source_document_name': file_name,
        'source_document_type': file_type,
        'source_document_path': file_path,
    }

    return file_info


# 遍历文件上传
def upload_files(path: str):
    """遍历文件上传
    Args:
        path: 源文件路径
    """
    file_infos = []
    for root, dirs, files in os.walk(path):
        for file in files:
            # 跳过系统文件
            if file.startswith('.'):
                continue
            file_info = get_file_info(os.path.join(root, file))
            file_infos.append(file_info)
        if len(dirs) > 0:
            for dir in dirs:
                upload_files(os.path.join(root, dir))
    return file_infos


if __name__ == '__main__':
    # raw_data_path = Config.PATHS['origin_data']
    raw_data_path = '/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业'

    # 连接数据库
    mysql = connect_mysql()
    # 上传文件
    # file_info = get_file_info('datas/raw/1_1_竞争情况（天宽科技）.docx')
    file_infos = upload_files(raw_data_path)

    try:
        # 将文件信息存储到数据库中
        mysql.use_db()
        for file_info in file_infos:
            mysql.insert_data(file_info)
            # 查询数据
            data = mysql.select_data('tk_table', {'doc_id': file_info['doc_id']})
            print(data)
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
    finally:
        # 关闭数据库连接
        mysql.close()
