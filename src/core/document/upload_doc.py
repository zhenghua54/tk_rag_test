"""上传文档服务"""

import os
from datetime import datetime
from src.database.mysql.operations import FileInfoOperation
from src.utils.file.file_toolkit import compute_file_hash
from src.utils.common.unit_convert import convert_bytes
from src.utils.common.args_validator import Validator
from config.settings import Config


def upload_doc(doc_path: str, department_id: str):
    """接收上传文档保存信息

    Args:
        doc_path (str): 文档服务器存储路径
        department_id (str): 文档权限部门 ID
    """

    # 参数校验
    Validator.validate_file(doc_path)
    Validator.validate_department_id(department_id)

    # 初始化存储信息
    doc_id = compute_file_hash(doc_path)  # 文档唯一标识
    doc_name = os.path.basename(doc_path)  # 文档名称
    doc_ext = os.path.splitext(doc_path)[1]  # 文档后缀
    doc_size = convert_bytes(os.path.getsize(doc_path))  # 文档大小
    doc_path = os.path.abspath(doc_path)    # 文档服务器存储路径
    doc_pdf_path = doc_path if doc_ext == "pdf" else None
    created_at = datetime.now()
    updated_at = created_at
    


# 保存到 mysql 服务器
# with FileInfoOperation as fo:

if __name__ == '__main__':
    print(os.path.getsize(__file__))
