"""文档服务"""
import os
from datetime import datetime
from typing import Dict, Any
from src.server.base import BaseService
from src.utils.common.logger import logger
from src.utils.file.file_toolkit import compute_file_hash
from src.utils.common.unit_convert import convert_bytes
from src.api.response import ResponseBuilder, ErrorCode
from src.utils.common.system_validator import SystemValidator
from src.utils.file.file_validator import FileValidator
from src.database.mysql.operations import FileInfoOperation, PermissionOperation
from src.utils.common.args_validator import ArgsValidator


class DocumentService(BaseService):
    """文档服务类"""

    @staticmethod
    async def upload(document_path: str, department_id: str) -> dict:
        """上传文档
        
        Args:
            document_path: 上传的文件
            department_id: 部门ID
            
        Returns:
            dict: 响应结果
        """
        try:
            # 1. 文件验证
            FileValidator.validity_file_ext(document_path)  # 文件格式校验
            if document_path.lower().endswith('.pdf'):  # 如果是 PDF，则进行额外检查
                FileValidator.validity_pdf_parse(document_path)
            FileValidator.validity_file_exist(document_path)  # 文件存在校验
            FileValidator.validity_file_size(document_path)  # 文件大小校验
            FileValidator.validity_file_name(document_path)  # 文件名称校验
            SystemValidator.validity_storage_space(document_path)  # 存储空间校验
            FileValidator.validity_file_normal(document_path)  # 文档是否可打开

            # 2. 获取文档标题doc_id
            doc_id = compute_file_hash(document_path)

            # 3. 检查文件是否已存在
            with FileInfoOperation() as file_op:
                if file_op.get_file_by_doc_id(doc_id):
                    return ResponseBuilder.error(
                        code=ErrorCode.FILE_EXISTS,
                        message="文件已存在",
                        data={
                            "doc_id": doc_id,
                            "suggestion": "请检查是否重复上传"
                        }
                    ).dict()

            # 4. 获取文档信息
            doc_name = os.path.splitext(os.path.basename(document_path))[0]  # 文档名称
            doc_ext = os.path.splitext(document_path)[1]  # 文档后缀
            doc_size = convert_bytes(os.path.getsize(document_path))  # 文档大小
            doc_path = os.path.abspath(document_path)  # 文档服务器存储路径
            doc_pdf_path = doc_path if doc_ext.lower() == ".pdf" else None
            created_at = datetime.now()

            # 5. 保存文件信息
            file_info = {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "doc_ext": doc_ext,
                "doc_size": doc_size,
                "doc_path": doc_path,
                "doc_pdf_path": doc_pdf_path,
                "created_at": created_at,
                "updated_at": created_at,
            }
            with FileInfoOperation() as file_op:
                file_op.insert_datas(file_info)
            logger.info(f"文件信息已更新至 Mysql: {file_info}")


            # 6. 更新权限信息
            permission_info = {
                "department_id": department_id,
                "doc_id": doc_id,
                "created_at": created_at,
                "updated_at": created_at,
            }
            with PermissionOperation() as permission_op:
                permission_op.insert_datas(permission_info)
            logger.info(f"权限信息已更新至 Mysql: {permission_info}")

            # 7. 返回成功响应
            return ResponseBuilder.success(data={
                "doc_id": doc_id,
                "doc_name": doc_name + doc_ext,
                "status": "completed",
                "department_id": department_id,
            }).dict()

        except ValueError as e:
            # 处理验证器抛出的错误
            error_code, error_msg = e.args
            return ResponseBuilder.error(
                code=error_code,
                message=error_msg,
                data={
                    "file_path": document_path,
                    "suggestion": "请检查文件是否符合要求"
                }
            ).dict()
        except Exception as e:
            logger.error(f"上传文档失败: {e}")
            return ResponseBuilder.error(
                code=ErrorCode.FILE_PARSE_ERROR,
                message="未知错误",
                data={
                    "file_path": document_path,
                    "error": str(e),
                    "suggestion": "请反馈处理"
                }
            ).dict()

    @staticmethod
    async def delete_file(doc_id: str, is_soft_delete: bool = False) -> Dict[str, Any]:
        """删除文档服务
        
        Args:
            doc_id: 文档ID
            is_soft_delete: 是否软删除
            
        Returns:
            Dict: 删除响应数据
        """
        try:
            # 1. 参数验证
            ArgsValidator.validity_doc_id(doc_id)
            
            # 2. 检查文件是否存在
            with FileInfoOperation() as file_op:
                file_info = file_op.get_file_by_doc_id(doc_id)
                if not file_info:
                    return ResponseBuilder.error(
                        code=ErrorCode.FILE_NOT_FOUND,
                        message="文件不存在",
                        data={
                            "doc_id": doc_id,
                            "suggestion": "请检查文档ID是否正确"
                        }
                    ).dict()
                
                # 3. 执行删除操作
                if is_soft_delete:
                    # 软删除：更新状态
                    file_op.update_by_doc_id(doc_id, {"status": "deleted"})
                    logger.info(f"文件已软删除: {doc_id}")
                else:
                    # 硬删除：删除文件和相关记录
                    try:
                        # 删除物理文件
                        if os.path.exists(file_info["doc_path"]):
                            os.remove(file_info["doc_path"])
                        if file_info["doc_pdf_path"] and os.path.exists(file_info["doc_pdf_path"]):
                            os.remove(file_info["doc_pdf_path"])
                            
                        # 删除数据库记录
                        file_op.delete_by_doc_id(doc_id)
                        with PermissionOperation() as permission_op:
                            permission_op.delete_by_doc_id(doc_id)
                            
                        logger.info(f"文件已硬删除: {doc_id}")
                    except Exception as e:
                        logger.error(f"删除文件失败: {e}")
                        return ResponseBuilder.error(
                            code=ErrorCode.INTERNAL_ERROR,
                            message="删除文件失败",
                            data={
                                "doc_id": doc_id,
                                "error": str(e),
                                "suggestion": "请检查文件权限或联系管理员"
                            }
                        ).dict()
            
            # 4. 返回成功响应
            return ResponseBuilder.success(data={
                "doc_id": doc_id,
                "status": "deleted",
                "delete_type": "soft" if is_soft_delete else "hard"
            }).dict()
            
        except ValueError as e:
            # 处理验证器抛出的错误
            error_code, error_msg = e.args
            return ResponseBuilder.error(
                code=error_code,
                message=error_msg,
                data={
                    "doc_id": doc_id,
                    "suggestion": "请检查参数是否正确"
                }
            ).dict()
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return ResponseBuilder.error(
                code=ErrorCode.INTERNAL_ERROR,
                message="系统内部错误",
                data={
                    "doc_id": doc_id,
                    "error": str(e),
                    "suggestion": "请反馈处理"
                }
            ).dict()
