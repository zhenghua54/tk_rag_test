"""文档服务"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import httpx
import asyncio  # 异步操作
from concurrent.futures import ThreadPoolExecutor  # 线程池管理
import pymysql
import os
import json
import time

from src.services.base import BaseService
from src.utils.common.logger import (
    log_operation_start, log_operation_success,
    log_operation_error, log_business_info, log_exception
)
from config.settings import Config
from src.utils.doc_toolkit import download_file_step_by_step, get_doc_output_path, convert_permission_ids_to_list
from src.utils.common.unit_convert import convert_bytes
from src.api.response import ErrorCode, APIException
from src.utils.validator.system_validator import SystemValidator
from src.utils.validator.file_validator import FileValidator
from src.utils.validator.content_validator import ContentValidator
from src.database.mysql.operations import FileInfoOperation, PermissionOperation, ChunkOperation
from src.utils.doc_toolkit import delete_path_safely
from src.core.document.content_merger import process_doc_content
from src.core.document.content_chunker import segment_text_content
from src.utils.validator.args_validator import ArgsValidator

# 创建线程池执行器
thread_pool = ThreadPoolExecutor(max_workers=4)


class DocumentService(BaseService):
    """文档服务类"""

    @staticmethod
    async def upload_file(document_http_url: str, permission_ids: str, callback_url: str = None) -> dict:
        """上传文档"""
        # 参数验证
        ArgsValidator.validate_not_empty(document_http_url, "document_http_url")
        ArgsValidator.validate_not_empty(permission_ids, "permission_ids")
        if callback_url:
            ArgsValidator.validate_not_empty(callback_url, "callback_url")

        # 对 permission_ids 做转换处理，并字符化处理
        # permission_ids = json.dumps(convert_permission_ids_to_list(permission_ids))

        start_time = log_operation_start("文档上传",
                                         document_url=document_http_url,
                                         permission_ids=permission_ids)

        try:
            if document_http_url.startswith("http"):
                path_type = "http_path"
                # 校验 HTTP 文档
                FileValidator.validate_http_filepath_exist(document_http_url)
                doc_ext = f".{document_http_url.split('.')[-1].lower()}"  # 确保 URL 有后缀名
                FileValidator.validate_file_ext(doc_ext=doc_ext)  # 文件格式校验
                doc_path = download_file_step_by_step(url=document_http_url)  # 下载文件到本地
            else:
                path_type = "local_path"
                doc_path = document_http_url

            # 路径转换
            path = Path(doc_path)

            # 文件验证
            FileValidator.validate_file_size(str(path))  # 文件大小校验
            FileValidator.validate_file_name(str(path))  # 文件名称校验
            SystemValidator.validate_storage_space(str(path))  # 存储空间校验
            FileValidator.validate_file_normal(str(path))  # 文档是否可打开

            # 如果是 PDF，则进行额外检查
            if path.suffix.lower().endswith('.pdf'):
                ContentValidator.validate_pdf_content_parse(str(path))

            # 查重
            check_result = FileValidator.validate_file_exist(str(path))
            doc_id = check_result["doc_id"]
            process_status = check_result["process_status"]
            doc_info = check_result.get("doc_info")

            if process_status in Config.FILE_STATUS.get("error"):
                start_time = log_operation_start("删除记录", doc_id=doc_id)
                # 删除所有相关记录
                with FileInfoOperation() as file_op, PermissionOperation() as permission_op, ChunkOperation() as chunk_op:
                    file_op.delete_by_doc_id(doc_id)
                    permission_op.delete_by_doc_id(doc_id)
                    chunk_op.delete_by_doc_id(doc_id)
                log_operation_success("删除记录", start_time=start_time, doc_info=doc_info)
            elif process_status in Config.FILE_STATUS.get("normal"):
                raise APIException(ErrorCode.FILE_EXISTS_PROCESSED)

            # 文档不存在，进入上传 + 处理流程
            doc_name = path.stem  # 文档名称
            doc_ext = path.suffix  # 文档后缀
            doc_size = convert_bytes(path.stat().st_size)  # 文档大小
            abs_path = str(path.resolve())  # 文档服务器存储路径
            doc_pdf_path = abs_path if doc_ext.lower() == ".pdf" else None
            now = datetime.now()

            # 组装doc_info
            doc_info = {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "doc_ext": doc_ext,
                "doc_size": doc_size,
                "doc_http_url": document_http_url if path_type == "http_path" else "",
                "doc_path": abs_path,
                "doc_pdf_path": doc_pdf_path,
                "process_status": "uploaded",
                "created_at": now,
                "updated_at": now,
            }

            # 组装permission_info
            permission_info = {
                "permission_ids": permission_ids,
                "doc_id": doc_id,
                "created_at": now,
                "updated_at": now,
            }

            # 插入数据库元信息
            try:
                with FileInfoOperation() as file_op, PermissionOperation() as permission_op:
                    file_op.insert_datas(doc_info)
                    log_business_info("文档入库", doc_id=doc_id)
                    # log_business_info("文档入库", doc_id=doc_id, file_info=doc_info)
                    # 插入权限信息到数据库
                    permission_op.insert_datas(permission_info)
                    log_business_info("权限入库", doc_id=doc_id, permission_ids=permission_ids)
            except pymysql.IntegrityError as e:
                if e.args[0] == 1062:
                    # 唯一约束冲突
                    raise APIException(ErrorCode.FILE_EXISTS_PROCESSED)
                log_operation_error("数据库操作",
                                    error_code=ErrorCode.MYSQL_INSERT_FAIL.value,
                                    error_msg=str(e),
                                    doc_id=doc_id)
                raise APIException(ErrorCode.MYSQL_INSERT_FAIL, str(e))

            # 返回成功
            result = {
                "doc_id": doc_id,
                "doc_name": f"{doc_name}{doc_ext}",
                "status": "uploaded",
                "permission_ids": permission_ids,
            }

            # 启动后台处理流程
            asyncio.create_task(asyncio.to_thread(
                process_doc_content,
                abs_path,
                doc_id
            ))
            
            # 启动后台监听文档转换状态，完成后开始文档切块
            asyncio.create_task(DocumentService._monitor_doc_process_and_segment(
                doc_id=doc_id,
                document_name=doc_name,
                permission_ids=permission_ids
            ))

            # 回调接口
            if callback_url:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(callback_url, json=result)
                except Exception as e:
                    log_operation_error("回调通知",
                                        error_code=ErrorCode.CALLBACK_ERROR.value,
                                        error_msg=str(e),
                                        callback_url=callback_url)
                    # 回调失败不影响主流程

            log_operation_success("文档上传", start_time,
                                  doc_id=doc_id,
                                  doc_name=f"{doc_name}{doc_ext}",
                                  permission_ids=permission_ids)
            return result

        except APIException:
            raise
        except ValueError as e:
            # 来自验证器的结构化错误
            error_code = e.args[0] if len(e.args) >= 1 else ErrorCode.INTERNAL_ERROR
            # 优先用 error_code 的 message，没有就用 str(e)
            error_msg = ErrorCode.get_message(error_code) or str(e)
            log_operation_error("文档上传",
                                error_code=error_code,
                                error_msg=error_msg,
                                document_url=document_http_url,
                                permission_ids=permission_ids)
            raise APIException(error_code, error_msg)
        except Exception as e:
            log_operation_error("文档上传",
                                error_code=ErrorCode.FILE_VALIDATION_ERROR.value,
                                error_msg=str(e),
                                document_url=document_http_url,
                                permission_ids=permission_ids)
            log_exception("文档上传异常", e)
            raise APIException(ErrorCode.FILE_VALIDATION_ERROR, str(e))

    @staticmethod
    async def delete_file(doc_id: str, is_soft_delete: bool = True, callback_url: str = None) -> Dict[str, Any]:
        """删除文档服务

        Args:
            doc_id: 文档ID
            is_soft_delete: 是否软删除（仅标记删除状态，不删除文件和数据库记录）
            callback_url: 删除完成后的回调URL

        Returns:
            Dict: 删除响应数据
        """
        # 参数验证
        ArgsValidator.validate_doc_id(doc_id)
        if callback_url:
            ArgsValidator.validate_not_empty(callback_url, "callback_url")

        start_time = log_operation_start("文档删除",
                                         doc_id=doc_id,
                                         is_soft_delete=is_soft_delete)

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
                    log_operation_error("获取文件信息",
                                        error_code=ErrorCode.PARAM_ERROR.value,
                                        error_msg=str(e),
                                        doc_id=doc_id)
                    raise APIException(ErrorCode.PARAM_ERROR, str(e)) from e

                error_code = ErrorCode.FILE_SOFT_DELETE_ERROR if is_soft_delete else ErrorCode.FILE_HARD_DELETE_ERROR

                # 物理删除文件
                if is_soft_delete is False:
                    out_path = get_doc_output_path(file_info['doc_path'])['output_path']
                    file_info['out_path'] = out_path
                    for key in ["doc_path", "doc_pdf_path", "doc_json_path", "doc_images_path", "doc_process_path",
                                "out_path"]:
                        path = file_info.get(key)
                        if not path:
                            continue
                        try:
                            delete_path_safely(path, error_code)
                        except FileNotFoundError:
                            log_business_info("文件不存在", path=path)
                        except OSError as e:
                            log_exception("系统IO错误",
                                          e)
                            raise APIException(error_code, str(e)) from e

                # 删除数据库记录或软删除
                try:
                    # 软删除：更新状态
                    file_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete)
                    permission_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete)
                    chunk_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete)

                    operation = "软删除文件" if is_soft_delete else "物理删除文件"

                    log_operation_success(operation=operation, start_time=start_time, doc_id=doc_id)
                except Exception as e:
                    log_operation_error("数据库删除",
                                        error_code=ErrorCode.MYSQL_DELETE_FAIL.value,
                                        error_msg=str(e),
                                        doc_id=doc_id)
                    raise APIException(ErrorCode.MYSQL_DELETE_FAIL, str(e)) from e

            # 返回成功响应
            result = {
                "doc_id": doc_id,
                "status": "deleted",
                "delete_type": "soft" if is_soft_delete else "hard"
            }

            # 异步回调
            if callback_url:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(callback_url, json=result)
                except Exception as e:
                    log_operation_error("回调通知",
                                        error_code=ErrorCode.CALLBACK_ERROR.value,
                                        error_msg=str(e),
                                        callback_url=callback_url)
                    # 回调失败不影响主流程

            log_operation_success("文档删除", start_time,
                                  doc_id=doc_id,
                                  delete_type="soft" if is_soft_delete else "hard")
            return result

        except APIException:
            raise
        except ValueError as e:
            log_exception("参数错误",
                          e)
            raise APIException(ErrorCode.PARAM_ERROR, str(e)) from e
        except Exception as e:
            log_operation_error("文档删除",
                                error_code=ErrorCode.INTERNAL_ERROR.value,
                                error_msg=str(e),
                                doc_id=doc_id)
            log_exception("文档删除异常", e)
            raise APIException(ErrorCode.INTERNAL_ERROR, str(e)) from e

    @staticmethod
    async def _monitor_doc_process_and_segment(doc_id: str, document_name: str, permission_ids: str):
        """监控文档处理状态，完成后启动文档切块

        Args:
            doc_id (str): 文档ID
            document_name (str): 文档名称
            permission_ids (str): 部门ID
        """
        try:
            max_attempts = 60  # 最大尝试次数，相当于30分钟
            attempt_interval = 30  # 检查间隔（秒）
            
            log_operation_start("文档处理状态监控", 
                               doc_id=doc_id, 
                               document_name=document_name)
            
            for attempt in range(max_attempts):
                # 等待一段时间
                await asyncio.sleep(attempt_interval)
                
                # 检查文档处理状态
                with FileInfoOperation() as file_op:
                    file_info = file_op.get_file_by_doc_id(doc_id)
                    
                    # 如果文档不存在或处理失败，停止监控
                    if not file_info:
                        log_operation_error("文档处理状态监控", 
                                           error_msg="文档不存在", 
                                           doc_id=doc_id)
                        return
                    
                    process_status = file_info.get("process_status")
                    
                    # 如果处理失败，停止监控
                    if process_status in Config.FILE_STATUS.get("error"):
                        log_operation_error("文档处理状态监控", 
                                           error_msg=f"文档处理失败: {process_status}", 
                                           doc_id=doc_id)
                        return
                    
                    # 如果处理已完成（merged状态），启动文档切块
                    if process_status == "merged":
                        log_operation_success("文档处理完成", 
                                             start_time=time.time(), 
                                             doc_id=doc_id, 
                                             process_status=process_status)
                        
                        # 开始文档切块处理
                        start_time = log_operation_start("文档切块", 
                                                       doc_id=doc_id, 
                                                       document_name=document_name)
                        try:
                            # 读取合并后的文档内容
                            doc_process_path = file_info.get("doc_process_path")
                            if not doc_process_path or not os.path.exists(doc_process_path):
                                raise ValueError(f"处理后的文档路径不存在: {doc_process_path}")

                            # 设置权限信息
                            permission_ids = {
                                "departments": [permission_ids],
                                "roles": [],
                                "users": []
                            }
                            
                            # 执行文档切块
                            await asyncio.to_thread(
                                segment_text_content,
                                doc_id,
                                document_name,
                                doc_process_path,
                                permission_ids
                            )
                            
                            # 更新数据库状态为已切块
                            with FileInfoOperation() as file_op:
                                values = {
                                    "process_status": "chunked"
                                }
                                file_op.update_by_doc_id(doc_id, values)
                            
                            log_operation_success("文档切块", 
                                                start_time=start_time, 
                                                doc_id=doc_id)
                            return
                            
                        except Exception as e:
                            # 更新数据库状态为切块失败
                            with FileInfoOperation() as file_op:
                                values = {
                                    "process_status": "chunk_failed"
                                }
                                file_op.update_by_doc_id(doc_id, values)
                                
                            log_operation_error("文档切块", 
                                              error_code=ErrorCode.INTERNAL_ERROR.value,
                                              error_msg=str(e),
                                              doc_id=doc_id)
                            log_exception("文档切块异常", e)
                            return
            
            # 如果超过最大尝试次数仍未完成，记录超时
            log_operation_error("文档处理状态监控", 
                               error_msg="监控超时，文档处理未完成", 
                               doc_id=doc_id,
                               max_attempts=max_attempts,
                               total_time=f"{max_attempts * attempt_interval} 秒")
            
        except Exception as e:
            log_operation_error("文档处理状态监控", 
                               error_code=ErrorCode.INTERNAL_ERROR.value,
                               error_msg=str(e),
                               doc_id=doc_id)
            log_exception("文档处理状态监控异常", e)
