"""文档服务"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Union
import httpx
import asyncio  # 异步操作
from concurrent.futures import ThreadPoolExecutor  # 线程池管理
import pymysql
import os

from services.base import BaseService
from utils.log_utils import (
    log_business_info, log_exception, logger
)
from config.global_config import GlobalConfig
from utils.file_ops import download_file_step_by_step, get_doc_output_path, generate_doc_id
from utils.converters import convert_bytes
from error_codes import ErrorCode
from api.response import APIException
from utils.validators import (
    check_disk_space_sufficient, check_doc_ext, check_http_doc_accessible, check_doc_size, \
    check_doc_name_chars, validate_file_normal, validate_empty_param, validate_doc_id
)
from databases.mysql.operations import FileInfoOperation, PermissionOperation, ChunkOperation, check_duplicate_doc
from databases.milvus.operations import VectorOperation
from databases.elasticsearch.operations import ElasticsearchOperation
from databases.db_ops import delete_all_database_data

from utils.file_ops import delete_path_safely
from core.doc.parser import process_doc_content
from core.doc.chunker import segment_text_content

# 创建线程池执行器
thread_pool = ThreadPoolExecutor(max_workers=4)


class DocumentService(BaseService):
    """文档服务类"""

    @staticmethod
    async def upload_file(document_http_url: str, permission_ids: Union[str, None], callback_url: str = None) -> dict:
        """上传文档"""
        # 参数验证
        check_http_doc_accessible(document_http_url, "document_http_url")

        try:
            if document_http_url.startswith("http"):
                path_type = "http_path"
                # 校验 HTTP 文档
                check_http_doc_accessible(document_http_url)
                doc_ext = f".{document_http_url.split('.')[-1].lower()}"  # 确保 URL 有后缀名
                check_doc_ext(ext=doc_ext, doc_type='all')  # 文件格式校验
                doc_path = download_file_step_by_step(url=document_http_url)  # 下载文件到本地
            else:
                path_type = "local_path"
                doc_path = document_http_url

            # 路径转换
            path = Path(doc_path)

            # 文件验证
            check_doc_size(str(path.resolve()))  # 文件大小校验
            check_doc_name_chars(path.name)  # 文件名称校验
            check_disk_space_sufficient(str(path.resolve()))  # 存储空间校验
            validate_file_normal(str(path.resolve()))  # 文档是否可打开

            # 查重
            doc_id = generate_doc_id(doc_path=str(path.resolve()))
            check_result = check_duplicate_doc(doc_id)
            process_status = check_result["process_status"]
            doc_info = check_result.get("doc_info")

            if process_status in GlobalConfig.FILE_STATUS.get("error"):

                # 删除所有相关记录
                with FileInfoOperation() as file_op, PermissionOperation() as permission_op, ChunkOperation() as chunk_op:
                    file_op.delete_by_doc_id(doc_id)
                    permission_op.delete_by_doc_id(doc_id)
                    chunk_op.delete_by_doc_id(doc_id)
                    logger.info(f"记录删除成功, 记录信息：{doc_info}")
            elif process_status in GlobalConfig.FILE_STATUS.get("normal"):
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
                    logger.info(f"开始文档入库, doc_id={doc_id}")
                    file_op.insert_data(doc_info)
                    # 插入权限信息到数据库
                    logger.info(f"开始权限入库, doc_id={doc_id}, permission_id={permission_ids}")
                    permission_op.insert_datas(permission_info)

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
                    asyncio.create_task(
                        DocumentService._monitor_doc_process_and_segment(doc_id=doc_id, document_name=doc_name,
                                                                         permission_ids=permission_ids,
                                                                         file_op=file_op, permission_op=permission_op))

                    # 回调接口
                    if callback_url:
                        try:
                            async with httpx.AsyncClient() as client:
                                await client.post(callback_url, json=result)
                        except Exception as e:
                            logger.error(f"回调失败, 错误原因: {str(e)}, 回调地址: {callback_url}")
                            # 回调失败不影响主流程
                return result

            except pymysql.IntegrityError as e:
                if e.args[0] == 1062:
                    # 唯一约束冲突
                    raise APIException(ErrorCode.FILE_EXISTS_PROCESSED)
                logger.error(f"数据库操作失败，error_msg={str(e)}")
                raise APIException(ErrorCode.MYSQL_INSERT_FAIL, str(e))

        except Exception as e:
            raise e from e

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
        validate_doc_id(doc_id)
        if callback_url:
            validate_empty_param(callback_url, "callback_url")

        try:
            # 获取文件信息
            file_info = None
            try:
                with FileInfoOperation() as file_op:
                    file_info = file_op.get_file_by_doc_id(doc_id)
                    if not file_info:
                        logger.info(f"MySQL中未找到文档记录: {doc_id}")
            except ValueError as e:
                logger.error(f"文件信息获取失败, 错误原因: {str(e)}, doc_id: {doc_id}")
                raise APIException(ErrorCode.PARAM_ERROR, str(e)) from e

            # 删除所有数据库记录
            await delete_all_database_data(doc_id, is_soft_delete)

            # 如果找到文件信息且需要物理删除，则删除文件
            if file_info and not is_soft_delete:
                logger.info(f"物理删除, 开始删除本地文件, doc_id: {doc_id}")
                error_code = ErrorCode.FILE_HARD_DELETE_ERROR
                out_path = get_doc_output_path(file_info['doc_path'])['output_path']
                file_info['out_path'] = out_path
                for key in ["doc_path", "doc_pdf_path", "doc_json_path", "doc_images_path",
                            "doc_process_path", "out_path"]:
                    path = file_info.get(key)
                    if not path:
                        continue
                    try:
                        delete_path_safely(path)
                    except FileNotFoundError:
                        logger.info(f"文件不存在, doc_id={doc_id}, path={path}")
                    except OSError as e:
                        log_exception("系统IO错误",
                                      e)
                        raise APIException(error_code, str(e)) from e

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
                    logger.error(f"回调失败, 错误原因: {str(e)}, 回调地址: {callback_url}")
                    # 回调失败不影响主流程

            return result

        except APIException:
            raise
        except ValueError as e:
            log_exception("参数错误",
                          e)
            raise APIException(ErrorCode.PARAM_ERROR, str(e)) from e
        except Exception as e:
            logger.error(f"文档删除失败, 错误原因: {str(e)}, doc_id: {doc_id}")
            raise APIException(ErrorCode.INTERNAL_ERROR, str(e)) from e

    # @staticmethod
    # async def _delete_all_database_data(doc_id: str, is_soft_delete: bool) -> None:
    #     """删除所有数据库中的相关数据
    #
    #     Args:
    #         doc_id: 要删除的文档ID
    #         is_soft_delete: 是否软删除
    #     """
    #     try:
    #         logger.info(f"开始删除数据库记录, doc_id={doc_id}")
    #         # 删除 MySQL 数据库记录
    #         try:
    #             logger.info(f"MySQL 数据删除")
    #             with FileInfoOperation() as file_op, \
    #                     PermissionOperation() as permission_op, \
    #                     ChunkOperation() as chunk_op:
    #                 # 删除文件信息表
    #                 if file_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete):
    #                     logger.info(f"表 {GlobalConfig.MYSQL_CONFIG['file_info_table']} 数据删除成功")
    #                 else:
    #                     logger.warning(f"表 {GlobalConfig.MYSQL_CONFIG['file_info_table']} 数据不存在")
    #
    #                 # 删除权限信息表
    #                 if permission_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete):
    #                     logger.info(f"表 {GlobalConfig.MYSQL_CONFIG['permission_info_table']} 数据删除成功")
    #                 else:
    #                     logger.warning(f"表 {GlobalConfig.MYSQL_CONFIG['permission_info_table']} 数据不存在")
    #
    #                 # 删除分块信息表
    #                 if chunk_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete):
    #                     logger.info(f"表 {GlobalConfig.MYSQL_CONFIG['segment_info_table']} 数据删除成功")
    #                 else:
    #                     logger.warning(f"表 {GlobalConfig.MYSQL_CONFIG['segment_info_table']} 数据不存在")
    #
    #                 operation = "软删除文件" if is_soft_delete else "物理删除文件"
    #                 logger.info(f"{operation}成功")
    #         except Exception as e:
    #             logger.error(f"MySQL 数据删除失败, 错误原因: {str(e)}")
    #             # MySQL删除失败不影响其他数据库的删除操作
    #
    #         # 删除 Milvus 数据库记录
    #         try:
    #             logger.info(f"Milvus 数据删除")
    #             vector_op = VectorOperation()
    #             if vector_op.delete_by_doc_id(doc_id):
    #                 logger.info(f"Milvus 数据删除成功")
    #             else:
    #                 logger.warning(f"Milvus 数据不存在")
    #         except Exception as e:
    #             logger.error(f"Milvus 数据删除失败, 错误原因: {str(e)}")
    #             # 不中断主流程
    #
    #         # 删除ES中的数据
    #         try:
    #             logger.info(f"Elasticsearch 数据删除")
    #             es_op = ElasticsearchOperation()
    #             if es_op.delete_by_doc_id(doc_id):
    #                 logger.info(f"Elasticsearch 数据删除")
    #                 log_business_info("Elasticsearch 数据删除成功")
    #             else:
    #                 logger.warning(f"Elasticsearch 数据删除")
    #                 log_business_info("Elasticsearch 数据不存在")
    #         except Exception as e:
    #             logger.error(f"Elasticsearch 数据删除: {str(e)}, doc_id: {doc_id}")
    #             # 不中断主流程
    #
    #     except Exception as e:
    #         logger.error(f"数据库记录删除失败, 错误原因: {str(e)}, doc_id: {doc_id}")
    #         # 不中断主流程

    @staticmethod
    async def _monitor_doc_process_and_segment(doc_id: str, document_name: str, permission_ids: str,
                                               file_op: FileInfoOperation, permission_op: PermissionOperation) -> None:
        """监控文档处理状态，完成后启动文档切块

        Args:
            doc_id (str): 文档ID
            document_name (str): 文档名称
            permission_ids (str): 权限ID，已格式化为JSON字符串
        """
        try:
            logger.info(f"文档状态监控, doc_id={doc_id},document_name={document_name}")
            max_attempts = 30
            attempt_interval = 60

            for attempt in range(attempt_interval):  # 最大尝试次数，30分钟
                await asyncio.sleep(max_attempts)  # 等待 30 秒

                # 检查文档处理状态
                if file_op is None:
                    with FileInfoOperation() as file_op:
                        file_info = file_op.get_file_by_doc_id(doc_id)
                else:
                    file_info = file_op.get_file_by_doc_id(doc_id)

                # 文档不存在或处理失败, 停止监控
                if not file_info:
                    logger.error(f"文档状态监控失败, 文档不存在")
                    return

                process_status = file_info.get("process_status")

                # 如果处理失败，停止监控
                if process_status in GlobalConfig.FILE_STATUS.get("error"):
                    logger.error(f"文档处理失败, 停止监控, status={process_status}")
                    return

                # 如果处理已完成（merged状态），启动文档切块
                if process_status == "merged":
                    logger.info(f"文档处理完成, 开始文档切块, status={process_status}")
                    try:
                        # 读取合并后的文档内容
                        doc_process_path = file_info.get("doc_process_path")
                        if not doc_process_path or not os.path.exists(doc_process_path):
                            raise ValueError(f"处理后的文档不存在, doc_path={doc_process_path}")

                        # 直接使用已经格式化的权限ID
                        # 从permission_info表中获取权限信息
                        if permission_op:
                            permission_info = permission_op.select_by_id(doc_id)
                        else:
                            with PermissionOperation() as op:
                                permission_info = op.select_by_id(doc_id)
                        if permission_info:
                            permission_ids = permission_info.get("permission_ids", permission_ids)

                        # 执行文档切块，直接传入权限ID字符串，不再进行转换
                        await asyncio.to_thread(
                            segment_text_content,
                            doc_id,
                            doc_process_path,
                            permission_ids
                        )

                        # 更新数据库状态为已切块
                        with FileInfoOperation() as file_op:
                            values = {
                                "process_status": "chunked"
                            }
                            file_op.update_by_doc_id(doc_id, values)
                        logger.info(f"文档切块成功, doc_id={doc_id}")
                        return

                    except Exception as e:
                        # 更新数据库状态为切块失败
                        with FileInfoOperation() as file_op:
                            values = {
                                "process_status": "chunk_failed"
                            }
                            file_op.update_by_doc_id(doc_id, values)
                        logger.error(f"文档切块失败, doc_id: {doc_id}")
                        return

            # 如果超过最大尝试次数仍未完成，记录超时
            logger.error(
                f"文档处理状态监控超时:文档处理未完成, doc_id={doc_id}, max_attempts={max_attempts}, total_time={max_attempts * attempt_interval} 秒")

        except Exception as e:
            logger.error(
                f"文档处理状态监控异常, 失败原因：{str(e)}")
