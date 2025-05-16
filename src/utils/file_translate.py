"""从数据库读取无 PDF 格式的文档,统一转换为 PDF 格式"""

import os
import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")

from src.utils.get_logger import logger
from src.database.mysql_connect import connect_mysql
from src.api.libreoffice_api import convert_to_pdf
from src.utils.get_doc_dir import get_translated_doc_output_dir


def get_file_path_from_db() -> list[dict]:
    """
    从数据库读取非 PDF 格式的文档,进行转换

    Returns:
        list[dict]: 源文件地址列表，每个元素包含 doc_id 和 source_document_path
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = 'select doc_id,source_document_path from file_info where source_document_pdf_path is null'
        file_paths = mysql.select_data(sql)
        return file_paths if file_paths is not None else []
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        return []
    finally:
        if 'mysql' in locals():
            mysql.close()


def translate_file():
    """
    读取文件列表,批量转换并返回转换后文件的保存路径

    Returns:
        file_paths (list[dict]): 转换后文件的保存路径
    """
    # 读取文件列表
    file_paths = get_file_path_from_db()
    if not file_paths:
        logger.warning("没有需要转换的文件")
        return []

    pdf_file_paths = []

    # 批量转换
    for file_path in file_paths:
        try:
            # 获取转换后的文件保存路径
            output_dir = get_translated_doc_output_dir(file_path['source_document_path'])
            # 转换为 PDF
            pdf_path = convert_to_pdf(file_path['source_document_path'], output_dir['output_data_dir'])
            if pdf_path:  # 检查转换是否成功
                pdf_file_paths.append({"doc_id": file_path['doc_id'], "source_document_pdf_path": pdf_path})
            else:
                logger.error(f"文件转换失败: {file_path['source_document_path']}")
        except Exception as e:
            logger.error(f"处理文件时发生错误: {file_path['source_document_path']}, 错误信息: {str(e)}")
            continue

    return pdf_file_paths


def update_file_path_to_db():
    """
    更新文件路径到数据库
    """
    # 转换文件并获取转换后的 PDF 文件路径
    pdf_file_paths = translate_file()
    
    if not pdf_file_paths:
        logger.info("没有需要更新的文件")
        return

    # 更新文件路径到数据库
    success_count = 0
    fail_count = 0
    
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = 'update file_info set source_document_pdf_path = %s where doc_id = %s'
        for pdf_file_path in pdf_file_paths:
            try:
                mysql.update_data(sql, (pdf_file_path['source_document_pdf_path'], pdf_file_path['doc_id']))
                success_count += 1
            except Exception as e:
                logger.error(f"更新文件 {pdf_file_path['doc_id']} 失败: {str(e)}")
                fail_count += 1
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if 'mysql' in locals():
            mysql.close()
            
    if success_count > 0 or fail_count > 0:
        logger.info(f"批量更新完成: 成功 {success_count} 条, 失败 {fail_count} 条")


if __name__ == '__main__':
    # pdf_file_paths = translate_file()
    # for file_path in pdf_file_paths:
        # print(file_path)
    update_file_path_to_db()
