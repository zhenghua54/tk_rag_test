"""
文件上传模块
1. 接收上传的文件
2. 提取文件信息
3. 存储到 mysql 数据库
"""

import os
import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")

import hashlib
from src.utils.get_logger import logger
from src.database.mysql_connect import connect_mysql,check_table_exists
from config import Config


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
    # PDF 文件 直接更新 PDF 文件路径
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
            # 跳过配置文件中未指定格式的文件
            if not file.endswith(tuple(Config.SUPPORTED_FILE_TYPES['all'])):
                continue
            file_info = get_file_info(os.path.join(root, file))
            file_infos.append(file_info)
        if len(dirs) > 0:
            for dir in dirs:
                upload_files(os.path.join(root, dir))
    return file_infos


def upload_file_to_db(file_paths: list[dict], debug: bool = False):
    """
    上传文件信息到数据库
    Args:
        file_paths: 文件路径列表
        debug: 是否开启调试模式，开启后会打印插入的数据信息
    """
    if not file_paths:
        logger.info("没有需要上传的文件")
        return

    success_count = 0
    fail_count = 0
    try:
        mysql = connect_mysql()
        mysql.use_db()
        if not check_table_exists(mysql,'file_info'):
            logger.error("数据库表 'file_info' 不存在, 退出流程")
            return
        for file_path in file_paths:
            try:
                if mysql.insert_data(file_path, 'file_info'):
                    success_count += 1
                    if debug:
                        # 查询并打印刚插入的数据
                        data = mysql.select_data(sql='select * from file_info where doc_id = %s', args=(file_path['doc_id'],))
            except Exception as e:
                logger.error(f"插入文件 {file_path.get('source_document_name', 'unknown')} 失败: {str(e)}")
                fail_count += 1
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if 'mysql' in locals():
            mysql.close()
            
    if success_count > 0 or fail_count > 0:
        logger.info(f"批量插入完成: 成功 {success_count} 条, 失败 {fail_count} 条")


if __name__ == '__main__':
    # raw_data_path = Config.PATHS['origin_data']
    # raw_data_path = '/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业'
    raw_data_path = '/Users/jason/Library/CloudStorage/OneDrive-个人/项目/内部企业知识库/文档资料'


    # 上传文件
    file_infos = upload_files(raw_data_path)
    
    # 将文件信息存储到数据库中，开启调试模式查看插入的数据
    upload_file_to_db(file_infos, debug=True)
