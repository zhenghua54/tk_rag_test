"""文档API实现"""

import time
from typing import Any

from fastapi import APIRouter, Request

from api.request.doc_request import (
    DocumentDeleteRequest,
    DocumentMetadataUpdateRequest,
    DocumentPermissionUpdateRequest,
    DocumentStatusRequest,
    DocumentUploadRequest,
)
from api.response import APIException, ResponseBuilder
from error_codes import ErrorCode
from services.doc_server import DocumentService
from utils.log_utils import log_exception, logger
from utils.validators import validate_doc_id, validate_param_type

router = APIRouter(prefix="/documents", tags=["文档相关"])


@router.post("/upload")
async def upload_document(request: DocumentUploadRequest, fastapi_request: Request) -> dict[str, Any]:
    """上传文档接口

    将服务器本地指定路径的文件信息入库, 并关联对应的部门ID

    Args:
        request: 文档上传请求参数
        fastapi_request: FastAPI请求对象，用于获取请求ID等信息

    Returns:
        dict: 包含文档ID等信息的响应
    """
    # 获取服务实例
    doc_service = DocumentService.get_instance()
    # 获取请求ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    start_time = time.time()
    logger.info(
        f"[文档上传] 开始, request_id={request_id}, doc={request.document_http_url[:200]}..., permission_ids={request.permission_ids}"
    )
    try:
        # 上传文档
        data = await doc_service.upload_file(
            document_http_url=request.document_http_url,
            is_visible=request.is_visible,
            permission_ids=request.permission_ids,
            request_id=request_id,
            callback_url=request.callback_url,
        )

        # 记录操作成功
        duration = int((time.time() - start_time) * 1000)
        logger.info(
            f"[文档上传] 成功, request_id={request_id}, doc_id={data.get('doc_id')}, duration={duration}ms, file_size={data.get('file_size', 'unknown')}"
        )

        return ResponseBuilder.success(data=data, request_id=request_id).model_dump()

    except APIException as e:
        logger.error(f"[文档上传失败] request_id={request_id}, error_code={e.code.value}, error_msg={e.message}")
        log_exception(f"request_id={request_id}, 文档上传失败", exc=e)
        return ResponseBuilder.error(
            error_code=e.code.value, error_message=e.message, request_id=request_id
        ).model_dump()
    except Exception as e:
        logger.error(f"[文档上传失败] request_id={request_id}, error_code=INTERNAL_ERROR, error_msg={str(e)}")
        log_exception(f"request_id={request_id}, 文档上传异常", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.INTERNAL_ERROR.value, error_message=str(e), request_id=request_id
        ).model_dump()


@router.put("/permissions")
async def update_document_permission(
    request: DocumentPermissionUpdateRequest, fastapi_request: Request
) -> dict[str, Any]:
    """更新文档权限接口

    更新指定doc_id对应的文档权限关系

    Args:
        request: 更新请求参数{doc_id, permission_ids}
        fastapi_request: FastAPI请求对象, 用于获取请求ID等信息

    Returns:
        dict: 更新结果信息
    """
    # 获取服务实例
    doc_service = DocumentService.get_instance()
    # 获取请求ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    start_time = time.time()
    logger.info(
        f"[文档权限更新] 开始, request_id={request_id}, doc_id={request.doc_id}, permission_ids={request.permission_ids}"
    )
    try:
        # 更新文档
        result = await doc_service.update_permission(
            doc_id=request.doc_id, permission_ids=request.permission_ids, request_id=request_id
        )

        # 记录操作成功
        duration = int((time.time() - start_time) * 1000)
        logger.info(
            f"[文档权限更新] 成功, request_id={request_id}, doc_id={request.doc_id}, permission_ids={request.permission_ids}, duration={duration}ms"
        )

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()
    except Exception as e:
        logger.error(f"[文档权限更新] 失败, request_id={request_id}, error_msg={str(e)}")
        log_exception(f"request_id={request_id}, 文档更新失败", exc=e)

        return ResponseBuilder.error(
            error_code=ErrorCode.INTERNAL_ERROR.value, error_message=str(e), request_id=request_id
        ).model_dump()


@router.delete("/delete")
async def delete_document(request: DocumentDeleteRequest, fastapi_request: Request) -> dict[str, Any]:
    """删除文档接口

    删除指定doc_id对应的文档, 权限关系及文档对应的切块内容

    Args:
        request: 删除请求参数{doc_id, is_soft_delete}
        fastapi_request: FastAPI请求对象, 用于获取请求ID等信息

    Returns:
        dict: 删除结果信息
    """
    # 获取服务实例
    doc_service = DocumentService.get_instance()
    # 获取请求ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    # 记录操作开始
    start_time = time.time()
    delete_type = "保留源文件" if request.is_soft_delete else "不保留源文件"
    logger.info(f"[文档删除] 开始, request_id={request_id}, doc_id={request.doc_id}, delete_type={delete_type}")

    try:
        # 验证参数
        validate_doc_id(request.doc_id)
        validate_param_type(request.is_soft_delete, bool, "删除类型")

        # 记录业务信息
        logger.info(
            f"[文档删除请求] request_id={request_id}, doc_id={request.doc_id}, is_soft_delete={request.is_soft_delete}"
        )

        result = await doc_service.delete_file(doc_id=request.doc_id, is_soft_delete=request.is_soft_delete)

        # 记录操作成功
        duration = int((time.time() - start_time) * 1000)
        logger.info(
            f"[文档删除] 成功, request_id={request_id}, doc_id={request.doc_id}, delete_type={delete_type}, duration={duration}ms"
        )

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()

    except Exception as e:
        logger.error(
            f"[文档删除失败] request_id={request_id}, doc_id={request.doc_id}, error_code=INTERNAL_ERROR, error_msg={str(e)}"
        )
        log_exception(f"文档删除异常: {str(e)}", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.INTERNAL_ERROR.value, error_message=str(e), request_id=request_id
        ).model_dump()


@router.post("/check_status")
async def check_document_status(request: DocumentStatusRequest, fastapi_request: Request):
    """文档状态监测接口

    监测指定 doc_id 的文档状态, 决定前端展示的内容

    Args:
        request: 监测请求参数{doc_id}
        fastapi_request: FastAPI 请求对象,用于获取请求 ID 等信息

    Returns:
        dict: 文件状态相关信息
    """
    # 获取服务器实例
    doc_service = DocumentService.get_instance()
    # 获取请求 ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    start_time = time.time()
    logger.info(f"[文档状态查询] 开始, request_id={request_id}, doc_id={request.doc_id}")

    try:
        validate_doc_id(request.doc_id)

        result = await doc_service.check_status(doc_id=request.doc_id)

        # 记录操作成功
        duration = int((time.time() - start_time) * 1000)
        status = result.get("status", "unknown")
        logger.info(
            f"[文档状态查询] 成功, request_id={request_id}, doc_id={request.doc_id}, status={status}, duration={duration}ms"
        )

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()
    except Exception as e:
        logger.error(
            f"[文档状态查询失败] request_id={request_id}, doc_id={request.doc_id}, error_code=FILE_STATUS_CHECK_FAIL, error_msg={str(e)}"
        )
        log_exception("文档状态查询异常", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.FILE_STATUS_CHECK_FAIL.value, error_message=str(e), request_id=request_id
        ).model_dump()


@router.get("/result/{doc_id}")
async def get_doc_result(doc_id: str, fastapi_request: Request) -> dict[str, Any] | None:
    """查询文档信息接口

    Args:
        doc_id: 要查询的文档 ID
        fastapi_request: FastAPI 请求对象,用于获取请求 ID 等信息

    Returns:
        dict: 文档信息响应
    """

    # 获取服务器实例
    doc_service = DocumentService.get_instance()
    # 获取请求 ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    start_time = time.time()
    logger.info(f"[文档信息查询] 开始, request_id={request_id}, doc_id={doc_id}")

    try:
        validate_doc_id(doc_id)

        result = await doc_service.get_result(doc_id=doc_id, request_id=request_id)

        # 记录操作成功
        duration = int((time.time() - start_time) * 1000)
        result_keys = list(result.keys()) if result else []
        logger.info(
            f"[文档信息查询] 成功, request_id={request_id}, doc_id={doc_id}, result_keys={result_keys}, duration={duration}ms"
        )

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()

    except Exception as e:
        logger.error(f"[文档信息查询] 查询失败: {str(e)}, request_id={request_id}, doc_id={doc_id}")
        log_exception("文档信息查询异常", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.FILE_STATUS_CHECK_FAIL.value, error_message=str(e), request_id=request_id
        ).model_dump()


@router.put("/metadata")
async def update_doc_metadata(
    request: DocumentMetadataUpdateRequest, fastapi_request: Request
) -> dict[str, Any] | None:
    """更新文档元数据接口

    Args:
        request: 更新请求参数{doc_id, is_visible}
        fastapi_request: FastAPI 请求对象,用于获取请求 ID 等信息

    Returns:
        dict: 文档信息响应
    """

    # 获取服务器实例
    doc_service = DocumentService.get_instance()
    # 获取请求 ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    start_time = time.time()
    logger.info(
        f"[文档元数据更新] 开始, request_id={request_id}, doc_id={request.doc_id}, is_visible={request.is_visible}"
    )

    try:
        validate_doc_id(request.doc_id)

        result = await doc_service.update_doc_metadata(
            doc_id=request.doc_id, is_visible=request.is_visible, request_id=request_id
        )

        # 记录操作成功
        duration = int((time.time() - start_time) * 1000)
        logger.info(
            f"[文档元数据更新] 成功, request_id={request_id}, doc_id={request.doc_id}, is_visible={request.is_visible}, duration={duration}ms"
        )

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()

    except Exception as e:
        logger.error(
            f"[文档元数据更新失败] request_id={request_id}, doc_id={request.doc_id}, error_code=FILE_STATUS_CHECK_FAIL, error_msg={str(e)}"
        )
        log_exception("文档元数据更新异常", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.FILE_STATUS_CHECK_FAIL.value, error_message=str(e), request_id=request_id
        ).model_dump()
