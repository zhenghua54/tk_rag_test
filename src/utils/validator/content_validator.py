"""文档内容校验"""

"""使用 PyMuPDF 检查 pdf 文件结构, 避免 MinerU 解析崩溃"""
import json
import os
import fitz

from src.api.error_codes import ErrorCode
from src.utils.common.logger import logger
from config.settings import Config
from src.utils.doc.doc_toolkit import  compute_file_hash
from src.database.mysql.operations import FileInfoOperation


# # 检查 PyMuPDF
# try:
#   import fitz
# except ImportError:
#     logger.error("缺少依赖: PyMuPDF (fitz)")
#     raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")


class ContentValidator:

    @staticmethod
    def validate_json_file(file_path: str) -> None:
        """json文件内容格式校验"""
        # 读取 JSON 文件
        try:
            with open(file=file_path, mode='r', encoding='utf-8') as f:
                doc_content = json.load(f)

            # 验证内容类型
            if not isinstance(doc_content, list):
                raise ValueError("JSON 内容必须是列表类型")
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析错误: {str(e)}")


    @staticmethod
    def validate_pdf_content_parse(path: str):
        """判断 PDF 文件内容是否合法（结构上可被解析），适用于送入 MinerU 前的预筛选。
        使用 PyMuPDF (fitz) 进行验证,与 MinerU 底层解析库保持一致。

        参数:
            path (str): PDF 文件路径

        返回:
            (bool, str): 是否合法, 原因或 OK
        """

        logger.info(f"检查文件是否合法: {path}")

        # 使用 fitz 进行基本检查
        try:
            logger.info("尝试打开 PDF 文件...")
            with fitz.open(path) as doc:
                # 检查文件是否可以打开
                if doc.is_encrypted:
                    logger.error("PDF 文件已加密")
                    raise ValueError(ErrorCode.FILE_PARSE_ERROR, "PDF 文件已加密")

                # 检查页数
                page_count = doc.page_count
                logger.info(f"PDF 总页数: {page_count}")
                if page_count == 0:
                    logger.error("PDF 文件没有页数")
                    raise ValueError(ErrorCode.FILE_PARSE_ERROR, "PDF 文件内容为空")

                # 尝试读取第一页，验证基本结构
                try:
                    logger.info("检查第一页...")
                    first_page = doc[0]
                    # 尝试获取页面尺寸，如果能获取到说明页面有效
                    page_rect = first_page.rect
                    logger.info(f"第一页尺寸: {page_rect}")

                    # 尝试获取页面内容，如果能获取到说明页面可读
                    text = first_page.get_text()
                    text_length = len(text.strip())
                    logger.info(f"第一页文本长度: {text_length} 字符")

                    if text_length == 0:
                        logger.warning("第一页没有文本内容，可能是扫描件或图片")

                except Exception as e:
                    logger.error(f"读取第一页失败: {str(e)}")
                    raise ValueError(ErrorCode.FILE_PARSE_ERROR, f"无法读取 PDF: {str(e)}")

        except Exception as e:
            raise ValueError(ErrorCode.FILE_PARSE_ERROR, f"PDF 文件结构检查失败: {str(e)}")

        logger.info("PDF 文件检查通过")


if __name__ == '__main__':
    pass
