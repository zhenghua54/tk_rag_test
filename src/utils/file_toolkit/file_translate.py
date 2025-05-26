"""从数据库读取无 PDF 格式的文档,统一转换为 PDF 格式"""

from src.utils.common.logger import logger
from src.api.libreoffice_convert import convert_to_pdf
from src.utils.document_path import get_translated_doc_output_path
from src.utils.database.file_db import update_pdf_paths
import shutil



def translate_file(non_pdf_file_paths: list[dict] = None):
    """读取非 PDF 文件,批量转换并返回转换后文件的保存路径

    Args:
        non_pdf_file_paths (list[dict], optional): 需要转换的文件列表。如果为 None, 则从数据库获取。

    Returns:
        pdf_file_paths (list[dict]): 转换后文件的保存路径
    """

    if not non_pdf_file_paths:
        logger.warning("没有需要转换的文件")
        return []

    pdf_file_paths = []
    total_files = len(non_pdf_file_paths)
    logger.info(f"开始转换 {total_files} 个文件")

    # 批量转换
    for index, file_path in enumerate(non_pdf_file_paths, 1):
        try:
            logger.info(f"正在转换第 {index}/{total_files} 个文件: {file_path['source_document_path']}")
            
            # 获取转换后的文件保存路径
            output_dir = get_translated_doc_output_path(
                file_path['source_document_path']
            )
            
            # 转换为 PDF
            pdf_path = convert_to_pdf(
                file_path['source_document_path'],
                output_dir['output_data_dir']
            )
            
            if pdf_path:  # 检查转换是否成功
                pdf_file_paths.append({
                    "doc_id": file_path['doc_id'],
                    "source_document_pdf_path": pdf_path
                })
                logger.info(f"文件转换成功: {pdf_path}")
            else:
                logger.error(
                    f"文件转换失败: {file_path['source_document_path']}"
                )
        except Exception as e:
            logger.error(
                f"处理文件时发生错误: {file_path['source_document_path']}, 错误信息: {str(e)}"
            )
            continue

    # 打印转换结果统计
    success_count = len(pdf_file_paths)
    fail_count = total_files - success_count
    logger.info(f"文件转换完成: 成功 {success_count} 个, 失败 {fail_count} 个")

    return pdf_file_paths


def update_file_path_in_db(pdf_file_paths: list[dict] = None):
    """更新文件路径到数据库

    Args:
        pdf_file_paths (list[dict], optional): PDF 文件路径列表。如果为 None，则从数据库获取。
    """
    if not pdf_file_paths:
        logger.info("没有需要更新的文件")
        return

    # 更新数据库
    success_count, fail_count = update_pdf_paths(pdf_file_paths)
    
    if success_count > 0 or fail_count > 0:
        logger.info(f"批量更新完成: 成功 {success_count} 条, 失败 {fail_count} 条")


if __name__ == '__main__':
    update_file_path_in_db()
