"""文档格式转换"""
import os

from src.utils.common.logger import logger
from config.settings import Config
from src.utils.file.doc_path import get_doc_output_path
from src.utils.file.libreoffice_convert import convert_to_pdf

def convert_office_file(file_path: str) -> str | None:
    """
    解析 Office 文件, 返回 json 文件信息
    """
    if not os.path.exists(file_path):
        logger.error(f"文件 {file_path} 不存在")
        return None

    if os.path.splitext(file_path)[1] not in Config.SUPPORTED_FILE_TYPES["libreoffice"]:
        logger.error(f"暂不支持该格式文件,目前支持的格式为: {Config.SUPPORTED_FILE_TYPES['libreoffice']}")
        return None

    # 获取输出路径
    output_path = get_doc_output_path(file_path)
    output_path, output_image_path, doc_name = output_path["output_path"], output_path["output_image_path"], output_path["doc_name"]


    # 转换为 PDF
    logger.info(f"开始转换为 PDF")
    pdf_path = convert_to_pdf(
        file_path,
        output_path
    )
    if pdf_path:  # 检查转换是否成功
        logger.info(f"文件转换成功: {pdf_path}")
        return pdf_path
    else:
        raise Exception(f"文件转换失败: {file_path}")