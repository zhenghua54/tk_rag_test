"""使用 PyMuPDF 检查 pdf 文件结构, 避免 MinerU 解析崩溃"""
import json
import os

from src.api.response import ErrorCode
from src.utils.common.logger import logger
from config.settings import Config

# 检查 PyMuPDF
try:
    import fitz
except ImportError:
    logger.error("缺少依赖: PyMuPDF (fitz)")
    raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")


class FileValidator:

    @staticmethod
    def validity_file_exist(file_path: str):
        """验证文件路径是否存在"""
        if not os.path.isfile(file_path):
            raise ValueError(ErrorCode.FILE_NOT_FOUND, ErrorCode.FILE_NOT_FOUND.describe())

    @staticmethod
    def validity_file_ext(file_path: str):
        """判断文件格式是否支持"""
        file_ext = os.path.splitext(os.path.basename(file_path))[-1].lower()
        if file_ext not in Config.SUPPORTED_FILE_TYPES["all"]:
            raise ValueError(ErrorCode.UNSUPPORTED_FORMAT, ErrorCode.UNSUPPORTED_FORMAT.describe())

    @staticmethod
    def validity_file_name(file_path: str):
        """文件名格式校验 """
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # 检查文件名长度
        if len(file_name) > 100:
            raise ValueError(ErrorCode.INVALID_FILENAME, "文件名长度不能超过100字符")
            
        # 检查文件名是否只包含字母、数字、下划线
        if not file_name.replace('_', '').isalnum():
            raise ValueError(ErrorCode.INVALID_FILENAME, "文件名只能包含字母、数字和下划线")

    @staticmethod
    def validity_file_normal(file_path: str):
        """校验文档是否可正常打开"""
        abs_file_path = os.path.abspath(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            # 1. 使用二进制模式验证文件可读性
            with open(abs_file_path, "rb") as f:
                f.read(1024)  # 只读取前1KB验证文件可读性
                
            # 2. 如果是PDF文件，额外进行结构验证
            if file_ext == '.pdf':
                with fitz.open(abs_file_path) as doc:
                    if doc.is_encrypted:
                        raise ValueError(ErrorCode.FILE_PARSE_ERROR, "PDF文件已加密")
                    if doc.page_count == 0:
                        raise ValueError(ErrorCode.FILE_PARSE_ERROR, "PDF文件没有页数")
                    
        except Exception as e:
            raise ValueError(ErrorCode.FILE_PARSE_ERROR, f"文件无法正常打开: {str(e)}")

    @staticmethod
    def validity_json_file(file_path: str) -> None:
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
    def validity_pdf_ext(file_path: str):
        """判断文件是否为 PDF 格式"""
        if not file_path.lower().endswith(".pdf"):
            raise ValueError(f"文件后缀不是 PDF: {file_path}")

    @staticmethod
    def validity_file_size(file_path: str):
        """判断文件大小"""
        max_file_size_bytes = 50 * 1024 * 1024  # 50 * 1024 * 1024 = 52428800

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError(ErrorCode.FILE_TOO_SMALL, ErrorCode.FILE_TOO_SMALL.describe())
        elif file_size > max_file_size_bytes:
            raise ValueError(ErrorCode.FILE_TOO_LARGE, ErrorCode.FILE_TOO_LARGE.describe())

    @staticmethod
    def validity_pdf_parse(path: str):
        """
        判断 PDF 文件是否合法（结构上可被解析），适用于送入 MinerU 前的预筛选。
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
                    raise ValueError(ErrorCode.FILE_PARSE_ERROR,"PDF 文件已加密")

                # 检查页数
                page_count = doc.page_count
                logger.info(f"PDF 总页数: {page_count}")
                if page_count == 0:
                    logger.error("PDF 文件没有页数")
                    raise ValueError(ErrorCode.FILE_PARSE_ERROR,"PDF 文件没有页数")

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
                    raise ValueError(ErrorCode.FILE_PARSE_ERROR, f"无法读取 PDF 第一页: {str(e)}")

        except Exception as e:
            raise ValueError(ErrorCode.FILE_PARSE_ERROR, f"PDF 文件结构检查失败: {str(e)}")

        logger.info("PDF 文件检查通过")


if __name__ == '__main__':
    pass
