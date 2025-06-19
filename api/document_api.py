"""文档API实现"""
from fastapi import APIRouter, Request
from api.response import APIException
from api.response import ResponseBuilder
from error_codes import ErrorCode
from services.doc_server import DocumentService
from api.request.document_delete_request import DocumentDeleteRequest
from api.request.document_upload_request import DocumentUploadRequest
from utils.log_utils import (
    log_operation_start, log_operation_success, log_operation_error,
    log_business_info, mask_sensitive_info, log_exception
)

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
    start_time = log_operation_start("文档上传",
                                     request_id=request_id,
                                     document_url=mask_sensitive_info(request.document_http_url),
                                     permission_ids=request.department_id)

    try:
        # 记录业务信息
        log_business_info("API调用",
                          endpoint="/documents/upload",
                          request_id=request_id,
                          permission_ids=request.department_id)

        data = await doc_service.upload_file(document_http_url=request.document_http_url,
                                             permission_ids=request.department_id)

        # 记录操作成功
        log_operation_success("文档上传", start_time,
                              request_id=request_id,
                              doc_id=data.get('doc_id'),
                              permission_ids=request.department_id)

        return ResponseBuilder.success(data=data, request_id=request_id).model_dump()

    except APIException as e:
        log_operation_error("文档上传",
                            error_code=e.code.value,
                            error_msg=str(e),
                            request_id=request_id,
                            permission_ids=request.department_id)
        return ResponseBuilder.error(
            error_code=e.code.value,
            error_message=e.message,
            request_id=request_id
        ).model_dump()
    except Exception as e:
        log_operation_error("文档上传",
                            error_code=ErrorCode.INTERNAL_ERROR.value,
                            error_msg=str(e),
                            request_id=request_id,
                            permission_ids=request.department_id)
        log_exception("文档上传异常", e)
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
    start_time = log_operation_start("文档删除",
                                     request_id=request_id,
                                     doc_id=request.doc_id,
                                     is_soft_delete=request.is_soft_delete)

    try:
        # 记录业务信息
        log_business_info("API调用",
                          endpoint="/documents/delete",
                          request_id=request_id,
                          doc_id=request.doc_id,
                          delete_type="软删除" if request.is_soft_delete else "硬删除")

        # 调用删除服务
        result = await doc_service.delete_file(
            doc_id=request.doc_id,
            is_soft_delete=request.is_soft_delete
        )

        # 记录操作成功
        log_operation_success("文档删除", start_time,
                              request_id=request_id,
                              doc_id=request.doc_id,
                              is_soft_delete=request.is_soft_delete,
                              deleted_count=result.get('deleted_count', 0))

        return ResponseBuilder.success(data=result, request_id=request_id).model_dump()

    except APIException as e:
        log_operation_error("文档删除",
                            error_code=e.code.value,
                            error_msg=str(e),
                            request_id=request_id,
                            doc_id=request.doc_id)
        return ResponseBuilder.error(
            error_code=e.code.value,
            error_message=e.message,
            request_id=request_id
        ).model_dump()
    except Exception as e:
        log_operation_error("文档删除",
                            error_code=ErrorCode.INTERNAL_ERROR.value,
                            error_msg=str(e),
                            request_id=request_id,
                            doc_id=request.doc_id)
        log_exception("文档删除异常", e)
        return ResponseBuilder.error(
            error_code=ErrorCode.INTERNAL_ERROR.value,
            error_message=str(e),
            request_id=request_id
        ).model_dump()
