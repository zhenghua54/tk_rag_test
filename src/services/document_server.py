"""文档服务"""
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from src.services.base import BaseService
from src.utils.common.logger import logger
from src.utils.doc.doc_toolkit import compute_file_hash
from src.utils.common.unit_convert import convert_bytes
from src.api.response import ErrorCode, APIException
from src.utils.validator.system_validator import SystemValidator
from src.utils.validator.file_validator import FileValidator
from src.utils.validator.content_validator import ContentValidator
from src.database.mysql.operations import FileInfoOperation, PermissionOperation, ChunkOperation
from src.utils.doc.doc_toolkit import delete_path_safely


class DocumentService(BaseService):
    """文档服务类"""

    @staticmethod
    async def upload_file(document_path: str, department_id: str) -> dict:
        """上传文档"""
        try:
            # 路径转换
            path = Path(document_path)

            # 文件验证
            FileValidator.validate_filepath_exist(str(path))  # 文件存在校验
            FileValidator.validate_file_ext(str(path))  # 文件格式校验
            FileValidator.validate_file_size(str(path))  # 文件大小校验
            FileValidator.validate_file_name(str(path))  # 文件名称校验
            SystemValidator.validate_storage_space(str(path))  # 存储空间校验
            FileValidator.validate_file_normal(str(path))  # 文档是否可打开

            # 如果是 PDF，则进行额外检查
            if path.suffix.lower().endswith('.pdf'):
                ContentValidator.validate_pdf_content_parse(str(path))

            # 计算文档 doc_id
            doc_id = compute_file_hash(document_path)

            # 去重校验
            with FileInfoOperation() as file_op:
                res_data = file_op.get_file_by_doc_id(doc_id)
                if res_data:
                    raise APIException(error_code=ErrorCode.FILE_EXISTS)

            # 文档元信息
            doc_name = path.stem  # 文档名称
            doc_ext = path.suffix  # 文档后缀
            doc_size = convert_bytes(path.stat().st_size)  # 文档大小
            abs_path = str(path.resolve())  # 文档服务器存储路径
            doc_pdf_path = abs_path if doc_ext.lower() == ".pdf" else None
            now = datetime.now()

            # 插入数据库
            with FileInfoOperation() as file_op, PermissionOperation() as permission_op:
                file_info = {
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "doc_ext": doc_ext,
                    "doc_size": doc_size,
                    "doc_path": abs_path,
                    "doc_pdf_path": doc_pdf_path,
                    "created_at": now,
                    "updated_at": now,
                }
                file_op.insert_datas(file_info)
                logger.info(f"[文档入库] doc_id={doc_id}, path={file_info}")

                # 插入权限信息到数据库
                permission_info = {
                    "department_id": department_id,
                    "doc_id": doc_id,
                    "created_at": now,
                    "updated_at": now,
                }
                permission_op.insert_datas(permission_info)
                logger.info(f"[权限入库] doc_id={doc_id}, department={permission_info}")

            # 返回成功
            return {
                "doc_id": doc_id,
                "doc_name": f"{doc_name}{doc_ext}",
                "status": "completed",
                "department_id": department_id,
            }

        except APIException:
            raise
        except ValueError as e:
            # 来自验证器的结构化错误
            error_code, error_msg = e.args if len(e.args) == 2 else (ErrorCode.INTERNAL_ERROR, str(e))
            raise APIException(error_code, error_msg)
        except Exception as e:
            raise APIException(ErrorCode.FILE_VALIDATION_ERROR, str(e))

    @staticmethod
    async def delete_file(doc_id: str, is_soft_delete: bool = True) -> Dict[str, Any]:
        """删除文档服务
        
        Args:
            doc_id: 文档ID
            is_soft_delete: 是否软删除（仅标记删除状态，不删除文件和数据库记录）

        Returns:
            Dict: 删除响应数据
        """
        try:
            # 数据查重
            with FileInfoOperation() as file_op, \
                    PermissionOperation() as permission_op, \
                    ChunkOperation() as chunk_op:

                # 获取文件信息
                try:
                    file_info = file_op.get_file_by_doc_id(doc_id)
                    # 文件不存在
                    if not file_info:
                        raise APIException(ErrorCode.FILE_NOT_FOUND)
                except ValueError as e:
                    logger.error(f"[获取文件信息失败] doc_id={doc_id}, error={str(e)}")
                    raise APIException(ErrorCode.PARAM_ERROR, str(e)) from e

                error_code = ErrorCode.FILE_SOFT_DELETE_ERROR if is_soft_delete else ErrorCode.FILE_HARD_DELETE_ERROR

                # 物理删除文件
                if is_soft_delete is False:
                    for key in ["doc_path", "doc_pdf_path", "doc_json_path", "doc_images_path", "doc_process_path"]:
                        path = file_info.get(key)
                        if not path:
                            continue
                        try:
                            delete_path_safely(path, error_code)
                        except FileNotFoundError:
                            logger.warning(f"[文件不存在] path={path}")
                        except OSError as e:
                            logger.error(f"[系统IO错误] path={path}, error={str(e)}")
                            raise APIException(error_code, str(e)) from e

                # 删除数据库记录或软删除
                try:
                    # 软删除：更新状态
                    file_op.delete_by_doc_id(doc_id, soft_delete=is_soft_delete)
                    permission_op.delete_by_doc_id(doc_id, soft_delete=is_soft_delete)
                    chunk_op.delete_by_doc_id(doc_id, soft_delete=is_soft_delete)
                except Exception as e:
                    logger.error(f"[数据库删除失败] doc_id={doc_id}, error={str(e)}")
                    raise APIException(ErrorCode.MYSQL_DELETE_FAIL, str(e)) from e

            # 4. 返回成功响应
            return {
                "doc_id": doc_id,
                "status": "deleted",
                "delete_type": "soft" if is_soft_delete else "hard"
            }
        except APIException:
            raise
        except ValueError as e:
            logger.error(f"[参数错误] error_code={ErrorCode.PARAM_ERROR.value}, error_msg={str(e)}")
            raise APIException(ErrorCode.PARAM_ERROR, str(e)) from e
        except Exception as e:
            logger.error(f"[删除失败] error_code={ErrorCode.INTERNAL_ERROR.value}, error={str(e)}")
            raise APIException(ErrorCode.INTERNAL_ERROR, str(e)) from e

# Mock 实现（用于测试环境）
class MockDocumentService(DocumentService):
    @staticmethod
    async def upload_file(document_path: str, department_id: str) -> dict:
        return {
            "doc_id": "假数据： doc_id",
            "doc_name": "假数据： mock_document.pdf",
            "status": "completed",
            "department_id": department_id,
        }

    @staticmethod
    async def delete_file(doc_id: str, is_soft_delete: bool = True) -> Dict[str, Any]:
        return {
            "doc_id": doc_id,
            "status": "deleted",
            "delete_type": "soft" if is_soft_delete else "hard"
        }