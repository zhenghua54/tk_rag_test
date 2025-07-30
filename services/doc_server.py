"""文档服务"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pymysql

from config.global_config import GlobalConfig
from core.doc.chunker import segment_text_content
from core.doc.parser import process_doc_content
from databases.db_ops import delete_all_database_data
from databases.mysql.operations import PermissionOperation, file_op, mysql_transaction, page_op, permission_op
from services.base import BaseService
from utils.converters import convert_bytes, local_path_to_url, normalize_permission_ids
from utils.file_ops import delete_local_file, download_file_step_by_step, generate_doc_id, split_pdf_to_pages
from utils.log_utils import logger
from utils.status_sync import sync_status_safely
from utils.validators import (
    check_disk_space_sufficient,
    check_doc_ext,
    check_doc_name_chars,
    check_doc_size,
    check_http_doc_accessible,
    validate_doc_id,
    validate_empty_param,
    validate_file_normal,
    validate_permission_ids,
)


class DocumentService(BaseService):
    """文档服务类"""

    @staticmethod
    async def upload_file(
        document_http_url: str,
        permission_ids: str | list[str] | list[None] = None,
        is_visible: bool = True,
        request_id: str = None,
        callback_url: str = None,
    ) -> dict:
        """上传文档

        Args:
            document_http_url (str): 文档 url / 服务器path地址
            permission_ids : 部门权限 ID, 可能有多种类型
            is_visible: 文档在RAG中的可见性，TRUE可见并参与，FALSE不参与
            request_id (str): 请求 ID
            callback_url (str): 回调 URL

        Returns:
            dict: 上传的文档信息
        """
        validate_empty_param(document_http_url, "文档地址")
        # 部门格式验证
        validate_permission_ids(permission_ids)
        # 权限 ID 格式转换
        cleaned_dep_ids: list[str] = normalize_permission_ids(permission_ids)

        try:
            if document_http_url.startswith("http"):
                path_type = "http_path"
                # 校验 HTTP 文档
                check_http_doc_accessible(document_http_url)
                doc_ext = f".{document_http_url.split('.')[-1].lower()}"  # 确保 URL 有后缀名
                check_doc_ext(ext=doc_ext, doc_type="all")  # 文件格式校验
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
            logger.info(f"[文档上传]  mysql 数据查重, doc_id: {doc_id}")
            records = file_op.select_by_id(doc_id=doc_id)

            if records:
                records = records[0]
                if records["process_status"] in GlobalConfig.FILE_STATUS.get("error"):
                    logger.info(f"[文档上传] 记录存在，状态异常，准备删除: {records}")
                    delete_all_database_data(doc_id=doc_id)
                elif records["process_status"] in GlobalConfig.FILE_STATUS.get("normal"):
                    raise ValueError(f"[文档上传] 文件已上传, 状态: {records['process_status']}")

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
            permission_info = []
            for dep_id in cleaned_dep_ids:
                permission_info.append(
                    {"permission_type": "department", "subject_id": dep_id, "doc_id": doc_id, "created_at": now}
                )

            # 插入数据库元信息
            try:
                logger.info(f"[文档上传] 开始文档入库, request_id={request_id}, doc_id={doc_id}")
                file_op.insert_data(doc_info)
                # 插入权限信息到数据库
                logger.info(
                    f"[文档上传] 开始权限入库, request_id={request_id}, doc_id={doc_id}, permission_ids={cleaned_dep_ids}"
                )
                permission_op.insert_datas(permission_info)

                # 启动后台处理流程
                asyncio.create_task(
                    asyncio.to_thread(process_doc_content, str(path.resolve()), doc_id, request_id, callback_url)
                )
                # 启动后台监听文档转换状态，完成后按照顺序: 开始文档切块 -> 页面切分
                asyncio.create_task(
                    DocumentService._monitor_doc_process_and_segment(
                        doc_id=doc_id, document_name=path.stem, request_id=request_id, callback_url=callback_url
                    )
                )

                return {
                    "doc_id": doc_id,
                    "doc_name": path.name,
                    "doc_size": convert_bytes(path.stat().st_size),
                    "status": "uploaded",
                    "permission_ids": cleaned_dep_ids,
                }

            except pymysql.IntegrityError as e:
                logger.error(f"[文档上传] 数据库操作失败, error_msg={str(e)}, request_id={request_id}")
                raise ValueError(f"数据库操作失败, error_msg={str(e)}") from e

        except Exception as e:
            logger.error(f"[文档上传] 失败, request_id={request_id}, error={str(e)}")
            raise e from e

    @staticmethod
    async def update_permission(
        doc_id: str, permission_ids: str | list[str] | list[None], request_id: str = None
    ) -> dict:
        """更新文档

        Args:
            doc_id: 已存在的文档 ID
            permission_ids: 部门ID
            request_id: 请求 ID

        Returns:
            dict: 更新结果
        """
        # 参数校验
        validate_doc_id(doc_id)

        # 权限格式转换
        cleaned_dep_ids: list[str] = normalize_permission_ids(permission_ids)

        # 验证源文档是否存在
        logger.debug(f"[文档权限更新] 文档查重, request_id={request_id}, doc_id={doc_id}")
        source_doc_info = file_op.select_by_id(doc_id=doc_id)
        logger.debug(
            f"[文档权限更新] 查询结果为 doc_id: {source_doc_info[0]['doc_id']}, doc_name: {source_doc_info[0]['doc_name']}"
        )

        if not source_doc_info:
            logger.error(
                f"[文档权限更新] 文档不存在, request_id={request_id}, doc_id={doc_id}, permission_ids={permission_ids}"
            )
            raise ValueError(f"文档不存在, doc_id={doc_id}")
        source_doc_info = source_doc_info[0]

        # 构造新数据
        now = datetime.now()

        permission_data = []
        for dep_id in cleaned_dep_ids:
            permission_data.append(
                {"permission_type": "department", "subject_id": dep_id, "doc_id": doc_id, "created_at": now}
            )

        with mysql_transaction() as conn, PermissionOperation(conn=conn) as permission_op:
            # 删除原有权限
            permission_op.delete_by_doc_id(doc_id)

            # 写入新权限
            result_num = permission_op.insert_datas(permission_data)
            logger.debug(
                f"[文档权限更新] 权限更新成功, request_id={request_id}, doc_id={doc_id}, 更新数量: {result_num}"
            )

        return {"doc_id": doc_id, "updated_permissions": cleaned_dep_ids, "update_count": result_num}

    @staticmethod
    async def delete_file(doc_id: str, is_soft_delete: bool = True, callback_url: str = None) -> dict[str, Any]:
        """删除文档服务

        Args:
            doc_id: 文档ID
            is_soft_delete: 是否只删除记录,不删除本地文件
            callback_url: 删除完成后的回调URL

        Returns:
            dict: 删除响应数据
        """
        # 参数验证
        validate_doc_id(doc_id)
        if callback_url:
            validate_empty_param(callback_url, "callback_url")

        try:
            # 获取文件信息
            file_info = None
            try:
                # 查询文件表,只有一个结果
                file_info = file_op.select_by_id(doc_id)
                if not file_info:
                    logger.info(f"MySQL中未找到文档记录: {doc_id}")
                    # 如果数据库中没有记录，直接返回成功
                    return {
                        "doc_id": doc_id,
                        "status": "deleted",
                        "delete_type": "记录删除" if is_soft_delete else "记录+文件删除",
                        "message": "文档记录不存在，无需删除",
                    }

            except ValueError as e:
                logger.error(f"尝试从 MySQL 中获取文件信息失败, 错误原因: {str(e)}, doc_id: {doc_id}")
                raise ValueError(f"尝试从 MySQL 中获取文件信息失败, 错误原因: {str(e)}, doc_id: {doc_id}") from e

            # 确保 file_info 不为空后再进行下标操作
            if file_info and len(file_info) > 0:
                file_info = file_info[0]

                # 删除所有数据库记录
                delete_all_database_data(doc_id)

                # 只删除记录时,连带处理后的文件一块删除,保留源文件
                if is_soft_delete:
                    # 删除处理文件
                    logger.info(f"开始删除处理文件, doc_id: {doc_id}")
                    delete_path_list = [file_info.get("doc_output_dir")]
                    delete_local_file(delete_path_list)
                # 物理删除时, 连带源文件一并删除
                elif not is_soft_delete:
                    logger.info(f"开始删除源文件+处理文件, doc_id: {doc_id}")
                    delete_path_list = [
                        file_info.get("doc_output_dir"),
                        file_info.get("doc_path"),
                        file_info.get("doc_pdf_path"),
                    ]
                    delete_local_file(delete_path_list)
            else:
                # 如果 file_info 为空，只删除数据库记录
                logger.info(f"文件信息为空，仅删除数据库记录, doc_id: {doc_id}")
                delete_all_database_data(doc_id)

            # 返回成功响应
            result = {
                "doc_id": doc_id,
                "status": "deleted",
                "delete_type": "记录删除" if is_soft_delete else "记录+文件删除",
            }

            return result

        except Exception as e:
            logger.error(f"文档删除失败, 错误原因: {str(e)}")
            raise ValueError(f"文档删除失败, 错误原因: {str(e)}") from e

    @staticmethod
    async def check_status(doc_id: str) -> dict[str, Any] | None:
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
            file_info: list[dict[str, Any]] = file_op.select_by_id(doc_id=doc_id)

            # 查无记录
            if not file_info:
                logger.info("未查询到相关记录")
                return result
            file_info = file_info[0]

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

            result["status"] = doc_status
            result["status_text"] = status_text
            result["reupload"] = doc_status in error_map
            return result
        except Exception as e:
            raise ValueError(f"文件状态查询失败: {str(e)}") from e

    @staticmethod
    async def get_result(doc_id: str, request_id: str | None = None) -> dict[str, Any]:
        """根据doc_id获取相关信息,如切块信息, 解析文档地址等
        - 文档已解析: 解析后的layout文件

        Args:
            doc_id: 文档 ID
            request_id: 请求 ID

        Returns:
            dict: 文档的所有相关信息
        """
        file_info: list[dict] = file_op.select_by_id(doc_id=doc_id)
        logger.debug(f"[文档信息查询] 数据库查询, request_id: {request_id}, 结果: {file_info}")

        if not file_info:
            logger.info(f"未查询到文档信息, doc_id: {doc_id}")
            raise ValueError("文档不存在, 未查询到相关记录")

        # 查询文件表,只有一个结果
        file_info = file_info[0]

        file_status = file_info.get("process_status")
        pdf_path = local_path_to_url(file_info.get("doc_pdf_path")) if file_info.get("doc_pdf_path") else None
        values = {"doc_id": doc_id, "file_status": file_status, "pdf_path": pdf_path}

        # 异常状态处理
        if file_status not in list(GlobalConfig.FILE_STATUS["normal"].keys()) + list(
            GlobalConfig.FILE_STATUS["error"].keys()
        ):
            raise ValueError(f"文件状态未注册: {file_status}")

        # 文档仅上传
        if file_status in ["uploaded", "parse_failed"]:
            return values

        # 文档已解析成功
        if file_status in ["parsed", "merged", "chunked", "merge_failed", "chunk_failed", "split_failed", "splited"]:
            # 已解析及之后状态,增加解析 layout 信息回传
            layout_path = file_info.get("doc_layout_path")
            values["layout_path"] = local_path_to_url(layout_path) if layout_path else None

        # 文档已切页, 增加分页信息
        if file_status == "splited":
            doc_page_info: list[dict] = page_op.select_by_id(doc_id=doc_id)
            page_info_list = []

            for page_info in doc_page_info:
                page_path = page_info.get("page_png_path")
                page_info_list.append(
                    {
                        "page_idx": page_info["page_idx"],
                        "page_path": local_path_to_url(page_path) if page_path else None,
                    }
                )
            values["page_info_list"] = page_info_list
        return values

    @staticmethod
    async def _monitor_doc_process_and_segment(
        doc_id: str, document_name: str, request_id: str = None, callback_url: str | None = None
    ) -> None:
        """监控文档处理状态，完成后启动文档切块

        Args:
            doc_id: 文档ID
            document_name: 文档名称
            request_id: 请求 ID
            callback_url: 回调 URL
        """
        try:
            logger.info(f"文档状态监控, doc_id={doc_id}, document_name={document_name}, request_id={request_id}")
            max_attempts = 30
            attempt_interval = 60

            for _ in range(max_attempts):  # 最大尝试 30 次
                await asyncio.sleep(attempt_interval)  # 每次等待 60 秒

                # 检查文档处理状态
                file_info = file_op.select_by_id(doc_id)

                # 文档不存在或处理失败, 停止监控
                if not file_info:
                    logger.error("文档状态监控失败, 文档不存在")
                    return
                file_info = file_info[0]

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

                        # 执行文档切块
                        logger.info(f"request_id={request_id}, 开始文档切块")
                        await asyncio.to_thread(
                            segment_text_content,
                            doc_id=doc_id,
                            doc_process_path=doc_process_path,
                            request_id=request_id,
                        )
                        doc_status = "chunked"
                        logger.info(
                            f"request_id={request_id}, 文档切块完成, 开始更新数据库状态: process_status -> {doc_status}"
                        )
                        if callback_url:
                            # 同步状态到外部系统
                            sync_status_safely(doc_id, "chunked", request_id, callback_url)

                        # 更新数据库状态为已切块
                        file_op.update_by_doc_id(doc_id, {"process_status": doc_status})

                    except Exception as e:
                        logger.error(f"request_id={request_id}, 文档切块失败, error={e}")
                        doc_status = "chunk_failed"
                        logger.info(f"request_id={request_id}, 开始更新数据库状态: process_status -> {doc_status}")

                        if callback_url:
                            # 同步状态到外部系统
                            sync_status_safely(doc_id, "chunk_failed", request_id, callback_url)

                        file_op.update_by_doc_id(doc_id, {"process_status": doc_status})
                        return
                    try:
                        logger.info(f"request_id={request_id}, 开始文档切页")
                        pdf_path: str = file_info["doc_pdf_path"]
                        output_dir: str = f"{Path(file_info['doc_json_path']).parent}/split_pages"

                        split_result: dict[str, str] = await asyncio.to_thread(
                            split_pdf_to_pages, input_path=pdf_path, output_dir=output_dir
                        )
                        logger.info(
                            f"request_id={request_id}, 文档切页完成, 结果路径: {f'{Path(doc_process_path).parent}/split_pages'}"
                        )
                        # 更新数据库状态为已切页
                        doc_status = "splited"
                        logger.info(
                            f"request_id={request_id}, 文档切块完成, 开始更新数据库状态: process_status -> {doc_status}"
                        )

                        if callback_url:
                            # 同步状态到外部系统
                            sync_status_safely(doc_id, "splited", request_id, callback_url)

                        file_op.update_by_doc_id(doc_id, {"process_status": doc_status})

                        # 组装数据
                        values = [
                            {"doc_id": doc_id, "page_idx": k, "page_png_path": v} for k, v in split_result.items()
                        ]
                        # 批量更新
                        logger.info(f"request_id={request_id}, 分页入库, doc_id={doc_id}, 入库数量: {len(values)}")
                        page_op.insert(values)
                    except Exception as e:
                        logger.error(f"request_id={request_id}, 文档切页失败, error={e}")
                        doc_status = "split_failed"
                        logger.info(f"request_id={request_id}, 开始更新数据库状态: process_status -> {doc_status}")

                        if callback_url:
                            # 同步状态到外部系统
                            sync_status_safely(doc_id, "split_failed", request_id, callback_url)

                        file_op.update_by_doc_id(doc_id, {"process_status": doc_status})

                    logger.info(f"request_id={request_id}, 文档已处理, status: {doc_status}")

                    return  # 处理完成，退出监控

            # 如果超过最大尝试次数仍未完成，记录超时
            logger.error(f"request_id={request_id}, 文档处理状态监控超时: doc_id={doc_id}")

        except Exception as e:
            logger.error(f"request_id={request_id}, 文档监控任务异常：{str(e)}")

    @staticmethod
    async def update_doc_metadata(doc_id: str, is_visible: bool, request_id: str = None) -> None:
        """更新文档是否参与问答

        Args:
            doc_id: 文档ID
            is_visible: 文档是否参与问答
            request_id: 请求ID

        Returns:
            None
        """
        try:
            # 参数校验
            validate_empty_param(is_visible, "is_visible")

            # 查重
            logger.info(f"[文档元数据更新] mysql 数据查重, doc_id: {doc_id}")
            records = file_op.select_by_id(doc_id=doc_id)
            if not records:
                logger.info(f"[文档元数据更新] 未查询到相关记录, doc_id: {doc_id}")
                raise ValueError(f"未查询到相关记录, doc_id: {doc_id}")

            # 更新数据库
            file_op.update_by_doc_id(doc_id, {"is_visible": is_visible})

            # 返回成功响应
            return {"doc_id": doc_id, "is_visible": is_visible}
        except Exception as e:
            logger.error(f"[文档元数据更新] 更新失败, doc_id: {doc_id}, error: {str(e)}")
            raise ValueError(f"更新失败, doc_id: {doc_id}, error: {str(e)}") from e
