"""使用 PyMuPDF 检查 pdf 文件结构, 避免 MinerU 解析崩溃"""
import os
from pathlib import Path
import requests
import fitz

from src.api.error_codes import ErrorCode
from config.settings import Config
from src.api.response import APIException
from src.utils.doc_toolkit import compute_file_hash
from src.database.mysql.operations import FileInfoOperation


# # 检查 PyMuPDF
# try:
#   import fitz
# except ImportError:
#     logger.error("缺少依赖: PyMuPDF (fitz)")
#     raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")


class FileValidator:

    @staticmethod
    def validate_filepath_len(doc_path: str, max_len: int = 1000):
        """验证文件路径长度"""
        if len(doc_path) > max_len:
            raise APIException(ErrorCode.TOOLANG_FILEPATH)

    @staticmethod
    def validate_local_filepath_exist(doc_path: str):
        """验证文件路径是否存在"""
        doc_path = Path(doc_path)
        if not doc_path.is_file():
            raise APIException(ErrorCode.FILE_NOT_FOUND)

    @staticmethod
    def validate_http_filepath_exist(doc_url: str):
        """验证 HTTP 文件路径是否存在"""
        response = requests.head(doc_url)
        if response.status_code != 200:
            raise APIException(ErrorCode.HTTP_FILE_NOT_FOUND)

    @staticmethod
    def validate_file_ext(doc_path: str=None,doc_ext: str=None):
        """验证文件格式"""
        if doc_path:
            doc_ext = str(Path(doc_path).suffix)
        support_ext = Config.SUPPORTED_FILE_TYPES.get("all")
        if doc_ext.lower() not in support_ext:
            raise APIException(ErrorCode.UNSUPPORTED_FORMAT)

    @staticmethod
    def validate_file_convert_ext(doc_path: str):
        """验证文件格式"""
        doc_path = Path(doc_path)
        support_ext = Config.SUPPORTED_FILE_TYPES.get("libreoffice")
        if doc_path.suffix not in support_ext:
            raise APIException(ErrorCode.UNSUPPORTED_FORMAT)

    @staticmethod
    def validate_file_size(doc_path: str, max_file_size_bytes: int = 50 * 1024 * 1024):
        """验证文件大小"""
        # 50 * 1024 * 1024 = 52428800 字节
        file_size = os.path.getsize(doc_path)
        # 空文件
        if file_size == 0:
            raise APIException(ErrorCode.FILE_EMPTY)
        # 大文件
        elif file_size > max_file_size_bytes:
            raise APIException(ErrorCode.FILE_TOO_LARGE)

    @staticmethod
    def validate_filename_len(doc_path: str, max_len: int = 200):
        """验证文件名长度"""
        if len(doc_path) > max_len:
            raise APIException(ErrorCode.TOOLANG_FILENAME)

    @staticmethod
    def validate_file_name(doc_path: str, replacement: str = "_", is_replace_name: bool = False):
        """文件名称格式校验：统一平台无关型文件名清洗器

        Args:
            doc_path (str): 文件路径
            replacement (str): 替换字符，默认为下划线
            is_replace_name (bool): 是否替换文件名中的非法字符，默认为 False
        """
        doc_path = Path(doc_path)
        # 文件名校验
        if len(doc_path.stem) > 100:
            raise APIException(ErrorCode.INVALID_FILENAME)
        if any(c in Config.UNSUPPORTED_FILENAME_CHARS for c in doc_path.stem):
            raise APIException(ErrorCode.INVALID_FILENAME)

        # 文件名修改返回
        if is_replace_name:
            # 替换非法字符
            new_name = ''.join(
                c if c not in Config.UNSUPPORTED_FILENAME_CHARS else replacement for c in doc_path.stem
            )
            # 修改文件名
            new_doc_path = doc_path.with_stem(new_name)
            return str(new_doc_path)

        return str(doc_path)

    @staticmethod
    def validate_file_normal(doc_path: str):
        """校验文档是否可正常打开"""
        abs_file_path = os.path.abspath(doc_path)
        file_ext = os.path.splitext(doc_path)[1].lower()

        try:
            # 1. 使用二进制模式验证文件可读性
            with open(abs_file_path, "rb") as f:
                f.read(1024)  # 只读取前1KB验证文件可读性

            # 2. 如果是PDF文件，额外进行结构验证
            if file_ext == '.pdf':
                with fitz.open(abs_file_path) as doc:
                    if doc.is_encrypted:
                        raise APIException(ErrorCode.FILE_EXCEPTION,
                                         "PDF文件已加密"
                                         )
                    if doc.page_count == 0:
                        raise APIException(ErrorCode.FILE_EMPTY)

        except Exception as e:
            raise APIException(ErrorCode.FILE_EXCEPTION,
                             f"文件无法正常打开: {str(e)}"
                             )

    @staticmethod
    def validate_file_exist(doc_path: str):
        """验证文件是否已上传"""
        doc_id = compute_file_hash(doc_path)

        with FileInfoOperation() as file_op:
            if file_op.get_file_by_doc_id(doc_id):
                raise APIException(ErrorCode.FILE_EXISTS)
        return doc_id

if __name__ == '__main__':
    pass
