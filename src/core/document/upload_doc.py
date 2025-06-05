"""上传文档服务"""

import os
import shutil
from datetime import datetime
from src.database.mysql.operations import FileInfoOperation
from src.utils.common.logger import logger
from src.utils.file.file_toolkit import compute_file_hash
from src.utils.common.unit_convert import convert_bytes
from src.utils.common.args_validator import Validator
from src.api.base import APIResponse, ErrorCode
from typing import Dict, Any


def check_storage_space(file_path: str) -> None:
    """检查存储空间是否足够
    
    Args:
        file_path: 文件路径
        
    Raises:
        Exception: 存储空间不足时抛出异常
    """
    file_size = os.path.getsize(file_path)
    # 获取项目根目录所在磁盘的可用空间
    total, used, free = shutil.disk_usage(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    if free <= file_size * 2:  # 预留2倍空间作为缓冲
        raise Exception(APIResponse.error(
            code=ErrorCode.STORAGE_FULL,  # 业务错误码 3007
            message="存储空间不足",
            data={
                "file_path": file_path,
                "required_space": convert_bytes(file_size),
                "suggestion": "请联系管理员清理存储空间"
            }
        ).json())


def check_file_exists(doc_id: str) -> None:
    """检查文件是否已存在
    
    Args:
        doc_id: 文档ID
        
    Raises:
        Exception: 文件已存在时抛出异常
    """
    with FileInfoOperation() as file_op:
        if file_op.get_by_doc_id(doc_id) is not None:
            raise Exception(APIResponse.error(
                code=ErrorCode.FILE_ALREADY_EXISTS,  # 业务错误码 3006
                message="文件已存在",
                data={
                    "doc_id": doc_id,
                    "suggestion": "请勿重复上传相同文件"
                }
            ).json())


def upload_doc(file_path: str, department_id: str) -> Dict[str, Any]:
    """接收上传文档保存信息

    Args:
        file_path (str): 文档服务器存储路径
        department_id (str): 文档权限部门 ID
        
    Returns:
        Dict: 文件信息，包含：
            - doc_id: 文档ID
            - doc_name: 文档名称
            - doc_ext: 文档后缀
            - doc_size: 文档大小
            - doc_path: 文档服务器存储路径
            - doc_pdf_path: PDF文件路径（如果是PDF文件）
            - created_at: 创建时间
            - updated_at: 更新时间
            
    Raises:
        Exception: 各种错误情况下的异常
    """
    try:
        # 参数校验
        Validator.validate_file(file_path)
        Validator.validate_department_id(department_id)
        
        # 检查存储空间
        check_storage_space(file_path)
        
        # 获取文档信息
        doc_id = compute_file_hash(file_path)  # 文档唯一标识
        
        # 检查文件是否已存在
        check_file_exists(doc_id)
        
        # 获取其他文档信息
        doc_name = os.path.splitext(os.path.basename(file_path))[0]  # 文档名称
        doc_ext = os.path.splitext(file_path)[1]  # 文档后缀
        doc_size = convert_bytes(os.path.getsize(file_path))  # 文档大小
        doc_path = os.path.abspath(file_path)  # 文档服务器存储路径
        doc_pdf_path = doc_path if os.path.splitext(file_path)[1] == "pdf" else None
        created_at = datetime.now()

        # 初始化存储信息
        file_info = {
            "doc_id": doc_id,  # 文档唯一标识
            "doc_name": doc_name,  # 文档名称
            "doc_ext": doc_ext,  # 文档后缀
            "doc_size": doc_size,  # 文档大小
            "doc_path": doc_path,  # 文档服务器存储路径
            "doc_pdf_path": doc_pdf_path,
            "created_at": created_at,
            "updated_at": created_at,
        }
        logger.info(f"文件信息获取成功: {file_info}")

        # 更新 mysql-file_info 表信息
        with FileInfoOperation() as file_op:
            file_op.insert_datas(file_info)

        logger.info(f"文件信息已更新至Mysql: {os.path.basename(doc_path)}")
        
        return file_info
        
    except Exception as e:
        logger.error(f"上传文档失败: {e}")
        raise Exception(APIResponse.error(
            code=ErrorCode.FILE_PARSE_ERROR,  # 业务错误码 3005
            message="文件解析失败",
            data={
                "file_path": file_path,
                "error": str(e),
                "suggestion": "请检查文件是否损坏或格式是否正确"
            }
        ).json())


if __name__ == '__main__':
    file_path = "/home/jason/tk_rag/datas/raw/1_1_竞争情况（天宽科技）.docx"
    document_id = "1"
    upload_doc(file_path, document_id)
