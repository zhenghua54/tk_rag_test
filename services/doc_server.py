"""文档服务"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Union, List
# import httpx
import asyncio  # 异步操作
import pymysql
import os

from services.base import BaseService
from utils.log_utils import logger
from config.global_config import GlobalConfig
from utils.file_ops import download_file_step_by_step, generate_doc_id, delete_local_file, split_pdf_to_pages
from utils.converters import convert_bytes, local_path_to_url, normalize_permission_ids
from error_codes import ErrorCode
from api.response import APIException
from utils.validators import (
    check_disk_space_sufficient, check_doc_ext, check_http_doc_accessible, check_doc_size, \
    check_doc_name_chars, validate_file_normal, validate_empty_param, validate_doc_id, validate_permission_ids
)
from databases.mysql.operations import FileInfoOperation, PermissionOperation
from databases.db_ops import delete_all_database_data, update_record_by_doc_id, select_record_by_doc_id, insert_record, \
    select_records_by_doc_id

from core.doc.parser import process_doc_content
from core.doc.chunker import segment_text_content


class DocumentService(BaseService):
    """文档服务类"""

    @staticmethod
    async def upload_file(document_http_url: str, permission_ids: Union[str, list[str], list[None]] = None,
                          request_id: str = None) -> dict:
        """上传文档

        Args:
            document_http_url (str): 文档 url / 服务器path地址
            permission_ids (Union[str, list[str], list[None]]): 部门权限 ID
            request_id (str): 请求 ID

        Returns:
            dict: 上传的文档信息
        """
        validate_empty_param(document_http_url, '文档地址')
        print(f"接收到的权限 ID: {permission_ids}")
        # 部门格式验证
        validate_permission_ids(permission_ids)
        # 权限 ID 格式转换
        permission_ids = normalize_permission_ids(permission_ids)
        print(f"处理后的权限 ID: {permission_ids}")

        try:
            if document_http_url.startswith("http"):
                path_type = "http_path"
                # 校验 HTTP 文档
                check_http_doc_accessible(document_http_url)
                doc_ext = f".{document_http_url.split('.')[-1].lower()}"  # 确保 URL 有后缀名
                check_doc_ext(ext=doc_ext, doc_type='all')  # 文件格式校验
                doc_path = await download_file_step_by_step(url=document_http_url)  # 下载文件到本地
            else:
                # 本地文档指的是服务器上的文档
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
            logger.info(f"查询 MySQL 中是否已存在记录, doc_id: {doc_id}")
            records = select_record_by_doc_id(table_name=GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id=doc_id)

            if records:
                if records["process_status"] in GlobalConfig.FILE_STATUS.get("error").keys():
                    logger.info(f"记录存在，状态异常，准备删除: {records}")
                    delete_all_database_data(doc_id=doc_id)
                elif records["process_status"] in GlobalConfig.FILE_STATUS.get("normal").keys():
                    raise ValueError(f"文件已上传, 状态: {records['process_status']}")

            # 文档不存在，进入上传 + 处理流程
            now = datetime.now()
            # 组装doc_info
            doc_info = {
                "doc_id": doc_id,
                "doc_name": path.stem,
                "doc_ext": path.suffix,
                "doc_size": convert_bytes(path.stat().st_size),
                "doc_http_url": document_http_url if path_type == "http_path" else "",
                "doc_path": str(path.resolve()),
                "doc_pdf_path": str(path.resolve()) if path.suffix.lower() == ".pdf" else None,
                "process_status": "uploaded",
                "created_at": now,
                "updated_at": now,
            }
            # 组装permission_info
            permission_info = None
            if isinstance(permission_ids, str):
                permission_info = {
                    "permission_ids": permission_ids,
                    "doc_id": doc_id,
                    "created_at": now,
                    "updated_at": now,
                }
            elif isinstance(permission_ids, list):
                permission_info = []
                for permission_id in permission_ids:
                    permission_info.append({
                        "permission_ids": permission_id,
                        "doc_id": doc_id,
                        "created_at": now,
                        "updated_at": now,
                    })

            # 插入数据库元信息
            try:
                with FileInfoOperation() as file_op, PermissionOperation() as permission_op:
                    logger.info(f"request_id={request_id}, 开始文档入库, doc_id={doc_id}")
                    file_op.insert_data(doc_info)
                    # 插入权限信息到数据库
                    logger.info(
                        f"request_id={request_id}, 开始权限入库, doc_id={doc_id}, permission_ids={permission_ids}")
                    permission_op.insert_datas(permission_info)

                    # 启动后台处理流程
                    asyncio.create_task(
                        asyncio.to_thread(
                            process_doc_content,
                            str(path.resolve()),
                            doc_id,
                            request_id,
                        )
                    )
                    # 启动后台监听文档转换状态，完成后按照顺序: 开始文档切块 -> 页面切分
                    asyncio.create_task(
                        DocumentService._monitor_doc_process_and_segment(
                            doc_id=doc_id,
                            document_name=path.stem,
                            permission_ids=permission_ids,
                            file_op=file_op,
                            request_id=request_id,
                        )
                    )

                    return {
                        "doc_id": doc_id,
                        "doc_name": path.name,
                        "status": "uploaded",
                        "permission_ids": permission_ids,
                    }

            except pymysql.IntegrityError as e:
                if e.args[0] == 1062:
                    # 唯一约束冲突
                    raise APIException(ErrorCode.FILE_EXISTS_PROCESSED)
                logger.error(f"数据库操作失败，error_msg={str(e)}, request_id={request_id}")
                raise APIException(ErrorCode.MYSQL_INSERT_FAIL, str(e))

        except Exception as e:
            logger.error(f"文档上传失败, request_id={request_id}, error={str(e)}")
            raise e from e

    @staticmethod
    async def delete_file(doc_id: str, is_soft_delete: bool = True, callback_url: str = None) -> Dict[str, Any]:
        """删除文档服务

        Args:
            doc_id: 文档ID
            is_soft_delete: 是否只删除记录,不删除本地文件
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
                logger.error(f"尝试从 MySQL 中获取文件信息失败, 错误原因: {str(e)}, doc_id: {doc_id}")
                raise APIException(ErrorCode.PARAM_ERROR, str(e)) from e

            # 删除所有数据库记录
            delete_all_database_data(doc_id)

            # 如果找到文件信息且需要物理删除，则删除文件
            if file_info and not is_soft_delete:
                logger.info(f"开始删除本地文件, doc_id: {doc_id}")
                delete_path_list = [file_info.get("doc_output_dir"), file_info.get("doc_path"),
                                    file_info.get("doc_pdf_path")]
                delete_local_file(delete_path_list)

            # 返回成功响应
            result = {
                "doc_id": doc_id,
                "status": "deleted",
                "delete_type": "记录删除" if is_soft_delete else "记录+文件删除"
            }

            # # 异步回调
            # if callback_url:
            #     try:
            #         async with httpx.AsyncClient() as client:
            #             await client.post(callback_url, json=result)
            #     except Exception as e:
            #         logger.error(f"回调失败, 错误原因: {str(e)}, 回调地址: {callback_url}")
            #         # 回调失败不影响主流程

            return result

        except Exception as e:
            logger.error(f"文档删除失败, 错误原因: {str(e)}")
            raise ValueError(f"文档删除失败, 错误原因: {str(e)}") from e

    @staticmethod
    async def check_status(doc_id: str) -> Union[Dict[str, Any], None]:
        """文档上传后, 通过该接口查询文档状态
        - uploaded: 上传成功, 等待解析, 无返回内容, 无需再次上传
        - parsed, merged: 处理中, 无返回内容, 无需再次上传
        - chunked, splited: 分块+ 切页,视为已分块, 可接后续接口读取分页内容或分块内容, 无需再次上传
        - parse_failed: 解析失败, 返回失败原因, 可以再次上传
        - merge_failed: 文档处理失败, 返回失败原因, 可以再次上传
        - "chunk_failed", "split_failed": 分块失败和切页失败, 返回失败原因, 可以再次上传
        """

        # 初始化返回内容
        result = {
            "status": "",  # 状态英文标识
            "status_text": "",  # 状态中文显示
            "reupload": False,  # 支持再次上传
        }
        try:
            # 查询数据表 doc_info 的记录
            table_name = GlobalConfig.MYSQL_CONFIG["file_info_table"]
            file_info: dict[str, Any] = select_record_by_doc_id(table_name=table_name, doc_id=doc_id)
            # 查无记录
            if not file_info:
                logger.info(f"未查询到相关记录")
                return result
            # 获取状态
            doc_status = file_info.get("process_status")
            # 所有合法状态集合
            normal_map = GlobalConfig.FILE_STATUS.get("normal", {})
            error_map = GlobalConfig.FILE_STATUS.get("error", {})
            all_statuses = set(normal_map) | set(error_map)
            if doc_status not in all_statuses:
                raise ValueError(f"非法状态值: {doc_status}")

            # 获取状态文字
            status_text = normal_map.get(doc_status) or error_map.get(doc_status)

            result['status'] = doc_status
            result['status_text'] = status_text
            result['reupload'] = doc_status in error_map
            return result
        except Exception as e:
            raise ValueError(f"文件状态查询失败: {str(e)}") from e

    @staticmethod
    async def get_result(doc_id: str) -> Dict[str, Any]:
        """根据doc_id获取相关信息,如切块信息, 解析文档地址等
        - 文档已解析: 解析后的layout文件
        - 文档

        Args:
            doc_id: 文档 ID

        Returns:
            Dict: 文档的所有相关信息
        """
        file_info: Dict = select_record_by_doc_id(table_name=GlobalConfig.MYSQL_CONFIG['file_info_table'],
                                                  doc_id=doc_id)
        if not file_info:
            logger.info(f"未查询到文档信息, doc_id: {doc_id}")
            raise ValueError(f"文档不存在, 未查询到相关记录")

        file_status = file_info.get("process_status")
        pdf_path = local_path_to_url(file_info.get("doc_pdf_path")) if file_info.get("doc_pdf_path") else None
        values = {"doc_id": doc_id, "file_status": file_status, "pdf_path": pdf_path}

        # 异常状态处理
        if file_status not in list(GlobalConfig.FILE_STATUS["normal"].keys()) + list(
                GlobalConfig.FILE_STATUS["error"].keys()):
            raise ValueError(f"文件状态未注册: {file_status}")

        # 文档仅上传
        if file_status in ['uploaded', "parse_failed"]:
            return values

        # 文档已解析成功
        if file_status in ["parsed", "merged", "chunked", "merge_failed", "chunk_failed",
                           "split_failed", "splited"]:
            # 已解析及之后状态,增加解析 layout 信息回传
            layout_path = file_info.get("doc_layout_path")
            values["layout_path"] = local_path_to_url(layout_path) if layout_path else None

        # 文档已切页, 增加分页信息
        if file_status == 'splited':
            doc_page_info: List[Dict] = select_records_by_doc_id(
                table_name=GlobalConfig.MYSQL_CONFIG['doc_page_info_table'],
                doc_id=doc_id
            )
            page_info_list = []

            for page_info in doc_page_info:
                page_path = page_info.get("page_png_path")
                page_info_list.append(
                    {
                        "page_idx": page_info['page_idx'],
                        "page_path": local_path_to_url(page_path) if page_path else None
                    }
                )
            values['page_info_list'] = page_info_list
        return values

    @staticmethod
    async def _monitor_doc_process_and_segment(doc_id: str, document_name: str, permission_ids: Union[str, list[str]],
                                               file_op: FileInfoOperation, request_id: str = None) -> None:
        """监控文档处理状态，完成后启动文档切块

        Args:
            doc_id (str): 文档ID
            document_name (str): 文档名称
            request_id (str): 请求 ID
        """
        try:
            logger.info(f"文档状态监控, doc_id={doc_id}, document_name={document_name}, request_id={request_id}")
            max_attempts = 30
            attempt_interval = 60

            for attempt in range(attempt_interval):  # 最大尝试次数，30分钟
                await asyncio.sleep(max_attempts)  # 等待 30 秒

                # 检查文档处理状态
                file_info = file_op.get_file_by_doc_id(doc_id) if file_op else FileInfoOperation().get_file_by_doc_id(
                    doc_id)

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
                    try:
                        # 读取合并后的文档内容
                        doc_process_path = file_info.get("doc_process_path")
                        if not doc_process_path or not os.path.exists(doc_process_path):
                            raise ValueError(f"处理后的文档不存在, doc_path={doc_process_path}")

                        # 执行文档切块，直接传入权限ID字符串，不再进行转换
                        logger.info(f"request_id={request_id}, 开始文档切块")
                        await asyncio.to_thread(
                            segment_text_content,
                            doc_id,
                            doc_process_path,
                            permission_ids,
                            request_id,
                        )
                        doc_status = 'chunked'
                        logger.info(
                            f"request_id={request_id}, 文档切块完成, 开始更新数据库状态: process_status -> {doc_status}")
                        # 更新数据库状态为已切块
                        update_record_by_doc_id(GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id,
                                                {"process_status": doc_status})

                    except Exception as e:
                        logger.error(f"request_id={request_id}, 文档切块失败, error={e}")
                        doc_status = "chunk_failed"
                        logger.info(f"request_id={request_id}, 开始更新数据库状态: process_status -> {doc_status}")
                        update_record_by_doc_id(GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id,
                                                {"process_status": doc_status})
                        return
                    try:
                        logger.info(f"request_id={request_id}, 开始文档切页")
                        split_result: dict[str, str] = await asyncio.to_thread(
                            split_pdf_to_pages,
                            input_path=file_info["doc_pdf_path"],
                            output_dir=f"{Path(file_info['doc_json_path']).parent}/split_pages"
                        )
                        logger.info(
                            f"request_id={request_id}, 文档切页完成, 结果路径: {f'{Path(doc_process_path).parent}/split_pages'}")
                        # 更新数据库状态为已切页
                        doc_status = "splited"
                        logger.info(
                            f"request_id={request_id}, 文档切块完成, 开始更新数据库状态: process_status -> {doc_status}")
                        update_record_by_doc_id(GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id,
                                                {"process_status": doc_status})

                        # 组装数据
                        values = [{"doc_id": doc_id, "page_idx": k, "page_png_path": v} for k, v in
                                  split_result.items()]
                        # 批量更新
                        logger.info(
                            f"request_id={request_id}, 分页入库, doc_id={doc_id}, 入库数量: {len(values)}")
                        insert_record(GlobalConfig.MYSQL_CONFIG["doc_page_info_table"], values)
                    except Exception as e:
                        logger.error(f"request_id={request_id}, 文档切页失败, error={e}")
                        doc_status = "split_failed"
                        logger.info(f"request_id={request_id}, 开始更新数据库状态: process_status -> {doc_status}")
                        update_record_by_doc_id(GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id,
                                                {"process_status": doc_status})

                    logger.info(f"request_id={request_id}, 文档已处理, status: {doc_status}")

            # 如果超过最大尝试次数仍未完成，记录超时
            logger.error(
                f"request_id={request_id}, 文档处理状态监控超时: doc_id={doc_id}")

        except Exception as e:
            logger.error(f"request_id={request_id}, 文档监控任务异常：{str(e)}, error={str(e)}")
