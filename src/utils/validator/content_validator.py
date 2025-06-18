"""文档内容校验"""
from api.response import APIException

"""使用 PyMuPDF 检查 pdf 文件结构, 避免 MinerU 解析崩溃"""
import fitz

from api.error_codes import ErrorCode
from src.utils.common.logger import logger


# # 检查 PyMuPDF
# try:
#   import fitz
# except ImportError:
#     logger.error("缺少依赖: PyMuPDF (fitz)")
#     raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")


class ContentValidator:

    @staticmethod
    def validate_json_file(json_content: str) -> None:
        """json文件内容格式校验: [{}, {}]，每个元素为一个字典。

        Args:
            json_content (str): JSON 文件内容字符串
        """
        if not isinstance(json_content, list):
            raise APIException(ErrorCode.FILE_EXCEPTION, "JSON 文件内容格式错误，应该是一个列表")
        if not isinstance(json_content[0], dict):
            raise APIException(ErrorCode.FILE_EXCEPTION, "JSON 文件内容格式错误，列表内应该是各元素的字典信息组成")




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
                    raise APIException(ErrorCode.FILE_EXCEPTION, "PDF 文件已加密")

                # 检查页数
                page_count = doc.page_count
                logger.info(f"PDF 总页数: {page_count}")
                if page_count == 0:
                    logger.error("PDF 文件没有页数")
                    raise APIException(ErrorCode.FILE_EMPTY)

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
                    return True, "OK"

                except Exception as e:
                    logger.error(f"读取第一页失败: {str(e)}")
                    raise APIException(ErrorCode.FILE_EXCEPTION, f"无法读取 PDF: {str(e)}")

        except Exception as e:
            raise APIException(ErrorCode.FILE_EXCEPTION, f"PDF 文件结构检查失败: {str(e)}")



if __name__ == '__main__':
    pass
