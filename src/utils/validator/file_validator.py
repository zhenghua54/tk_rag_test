"""使用 PyMuPDF 检查 pdf 文件结构, 避免 MinerU 解析崩溃"""
import os
import fitz

from src.api.error_codes import ErrorCode
from config.settings import Config
from src.utils.doc.doc_toolkit import compute_file_hash
from src.database.mysql.operations import FileInfoOperation


# # 检查 PyMuPDF
# try:
#   import fitz
# except ImportError:
#     logger.error("缺少依赖: PyMuPDF (fitz)")
#     raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")


class FileValidator:

    @staticmethod
    def validate_filepath_len(file_path: str, max_len: int = 1000):
        """验证文件路径长度"""
        if len(file_path) > max_len:
            raise ValueError(ErrorCode.TOOLANG_FILEPATH,
                             ErrorCode.get_message(ErrorCode.TOOLANG_FILEPATH)
                             )

    @staticmethod
    def validate_filepath_exist(file_path: str):
        """验证文件路径是否存在"""
        if not os.path.isfile(file_path):
            raise ValueError(ErrorCode.FILE_NOT_FOUND,
                             ErrorCode.get_message(ErrorCode.FILE_NOT_FOUND)
                             )

    @staticmethod
    def validate_file_ext(file_path: str):
        """验证文件格式"""
        support_ext = Config.SUPPORTED_FILE_TYPES.get("all")
        file_ext = os.path.splitext(os.path.basename(file_path))[-1].lower()
        if file_ext not in support_ext:
            raise ValueError(ErrorCode.UNSUPPORTED_FORMAT,
                             ErrorCode.get_message(ErrorCode.UNSUPPORTED_FORMAT, ",".join(support_ext))
                             )

    @staticmethod
    def validate_file_size(file_path: str, max_file_size_bytes: int = 50 * 1024 * 1024):
        """验证文件大小"""
        # 50 * 1024 * 1024 = 52428800 字节
        file_size = os.path.getsize(file_path)
        # 空文件
        if file_size == 0:
            raise ValueError(ErrorCode.FILE_EMPTY)
        # 大文件
        elif file_size > max_file_size_bytes:
            raise ValueError(ErrorCode.FILE_TOO_LARGE,
                             ErrorCode.get_message(ErrorCode.FILE_TOO_LARGE)
                             )

    @staticmethod
    def validate_filename_len(file_path: str, max_len: int = 200):
        """验证文件名长度"""
        if len(file_path) > max_len:
            raise ValueError(ErrorCode.TOOLANG_FILENAME,
                             ErrorCode.get_message(ErrorCode.TOOLANG_FILENAME, )
                             )

    @staticmethod
    def validate_file_name(file_path: str):
        """文件名格式校验 """
        file_name = os.path.splitext(os.path.basename(file_path))[0]

        # 检查文件名长度
        if len(file_name) > 100:
            raise ValueError(ErrorCode.INVALID_FILENAME)

        # 检查文件名是否只包含字母、数字、下划线
        if not file_name.replace('_', '').isalnum():
            raise ValueError(ErrorCode.INVALID_FILENAME,
                             ErrorCode.get_message(ErrorCode.INVALID_FILENAME)
                             )

    @staticmethod
    def validate_file_normal(file_path: str):
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
                        raise ValueError(ErrorCode.FILE_EXCEPTION,
                                         "PDF文件已加密"
                                         )
                    if doc.page_count == 0:
                        raise ValueError(ErrorCode.FILE_EMPTY,
                                         ErrorCode.get_message(ErrorCode.FILE_EMPTY)
                                         )

        except Exception as e:
            raise ValueError(ErrorCode.FILE_EXCEPTION,
                             f"文件无法正常打开: {str(e)}"
                             )

    @staticmethod
    def validate_file_exist(file_path: str):
        """验证文件是否已上传"""
        doc_id = compute_file_hash(file_path)

        with FileInfoOperation() as file_op:
            if file_op.get_file_by_doc_id(doc_id):
                raise ValueError(ErrorCode.FILE_EXISTS,
                                 ErrorCode.get_message(ErrorCode.FILE_EXISTS)
                                 )

    @staticmethod
    def validate_pdf_ext(file_path: str):
        """判断文件是否为 PDF 格式"""
        if not file_path.lower().endswith(".pdf"):
            raise ValueError(f"文件后缀不是 PDF: {file_path}")


if __name__ == '__main__':
    pass
