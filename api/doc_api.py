"""文档API实现"""
from typing import Dict, Union, Any

from fastapi import APIRouter, Request
from api.response import APIException
from api.response import ResponseBuilder
from error_codes import ErrorCode
from services.doc_server import DocumentService
from api.request.doc_request import DocumentDeleteRequest, DocumentUploadRequest, DocumentStatusRequest
from utils.log_utils import log_exception, logger
from utils.validators import validate_doc_id, validate_param_type

router = APIRouter(
    prefix="/documents",
    tags=["文档相关"],
)


@router.post("/upload")
async def upload_document(request: DocumentUploadRequest, fastapi_request: Request):
    """上传文档接口

    将服务器本地指定路径的文件信息入库, 并关联对应的部门ID

    Args:
        request: 文档上传请求参数
        fastapi_request: FastAPI请求对象，用于获取请求ID等信息

    Returns:
        Dict: 包含文档ID等信息的响应
    """
    # 获取服务实例
    doc_service = DocumentService.get_instance()
    # 获取请求ID
    request_id = fastapi_request.state.request_id if hasattr(fastapi_request.state, 'request_id') else None

    # 记录操作开始
    logger.info(
        f"request_id={request_id}, 开始文档上传, document_http_url={request.document_http_url[:200]}..., permission_ids={request.permission_ids}")
    try:
        logger.info("API 调用: /documents/upload")
        data = await doc_service.upload_file(
            document_http_url=request.document_http_url,
            permission_ids=request.permission_ids,
            request_id=request_id
        )

        # 记录操作成功
        logger.info(f"request_id={request_id}, 文档上传完成, doc_id={data.get('doc_id')}")

        return ResponseBuilder.success(data=data, request_id=request_id).model_dump()

    except APIException as e:
        log_exception(f"request_id={request_id}, 文档上传失败", exc=e)
        return ResponseBuilder.error(
            error_code=e.code.value,
            error_message=e.message,
            request_id=request_id
        ).model_dump()
    except Exception as e:
        log_exception(f"request_id={request_id}, 文档上传异常", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.INTERNAL_ERROR.value,
            error_message=str(e),
            request_id=request_id
        ).model_dump()


@router.delete("/delete")
async def delete_document(request: DocumentDeleteRequest, fastapi_request: Request):
    """删除文档接口

    删除指定doc_id对应的文档, 权限关系及文档对应的切块内容

    Args:
        request: 删除请求参数{doc_id, is_soft_delete}
        fastapi_request: FastAPI请求对象，用于获取请求ID等信息

    Returns:
        Dict: 删除结果信息
    """
    # 获取服务实例
    doc_service = DocumentService.get_instance()
    # 获取请求ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    logger.info(
        f"开始删除文档, request_id={request_id}, doc_id={request.doc_id}, is_soft_delete={'记录删除' if request.is_soft_delete else '记录+文件删除'}")
    try:
        # 验证参数
        validate_doc_id(request.doc_id)
        validate_param_type(request.is_soft_delete, bool, '删除类型')

        # 调用删除服务
        logger.info(f"API 调用: /documents/delete")
        result = await doc_service.delete_file(
            doc_id=request.doc_id,
            is_soft_delete=request.is_soft_delete
        )

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()

    except Exception as e:
        log_exception(f"文档删除异常: {str(e)}")
        return ResponseBuilder.error(
            error_code=ErrorCode.INTERNAL_ERROR.value,
            error_message=str(e),
            request_id=request_id
        ).model_dump()


@router.post("/check_status")
async def check_document_status(request: DocumentStatusRequest, fastapi_request: Request):
    """文档状态监测接口

    监测指定 doc_id 的文档状态, 决定前端展示的内容

    Args:
        request: 监测请求参数{doc_id}
        fastapi_request: FastAPI 请求对象,用于获取请求 ID 等信息

    Returns:
        Dict: 文件状态相关信息
    """
    # 获取服务器实例
    doc_service = DocumentService.get_instance()
    # 获取请求 ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    logger.info(f"查询文档状态, request_id={request_id}, doc_id={request.doc_id}")

    try:
        validate_doc_id(request.doc_id)

        # 调用监测服务
        logger.info(f"API 调用: /documents/check_status")
        result = await doc_service.check_status(doc_id=request.doc_id)

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()
    except Exception as e:
        log_exception(f"文档状态查询异常", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.FILE_STATUS_CHECK_FAIL.value,
            error_message=str(e),
            request_id=request_id
        ).model_dump()


@router.get("/result/{doc_id}")
async def get_doc_result(doc_id: str, fastapi_request: Request) -> Union[Dict[str, Any], None]:
    """查询文档信息接口

    Args:
        doc_id: 要查询的文档 ID
        fastapi_request: FastAPI 请求对象,用于获取请求 ID 等信息
    
    Returns:
        Dict: 文档信息响应
    """

    # 获取服务器实例
    doc_service = DocumentService.get_instance()
    # 获取请求 ID
    request_id = getattr(fastapi_request.state, "request_id", None)

    # 记录操作开始
    logger.info(f"查询文档信息, request_id={request_id}, doc_id={doc_id}")

    try:
        validate_doc_id(doc_id)

        # 调用查询文档信息方法
        logger.info(f"API 调用: /documents/result/{doc_id}")
        result = await doc_service.get_result(doc_id=doc_id)

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()

    except Exception as e:
        log_exception(f"文档信息查询异常", exc=e)
        return ResponseBuilder.error(
            error_code=ErrorCode.FILE_STATUS_CHECK_FAIL.value,
            error_message=str(e),
            request_id=request_id
        ).model_dump()
