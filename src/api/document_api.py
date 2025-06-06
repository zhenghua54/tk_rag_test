"""文档API实现"""
from fastapi import APIRouter
from src.api.response import ResponseBuilder, ErrorCode
from src.server.document_server import DocumentService
from src.api.request.document_delete_request import DocumentDeleteRequest
from src.api.request.document_upload_request import DocumentUploadRequest
from src.utils.common.logger import logger

router = APIRouter(prefix="/api/v1")


@router.post("/documents")
async def upload_document(request: DocumentUploadRequest):
    """上传文档接口
    
    将服务器本地指定路径的文件解析、切块并入库
    
    Args:
        request: 文档上传请求参数
        
    Returns:
        Dict: 包含文档ID等信息的响应
    """
    try:
        # 获取服务实例
        doc_service = DocumentService.get_instance()

        # 调用上传服务
        result: dict = await doc_service.upload(
            document_path=request.document_path,
            department_id=request.department_id
        )

        # 检查结果是否包含错误信息
        if isinstance(result, dict) and result.get("code") != ErrorCode.SUCCESS:
            return ResponseBuilder.error(
                code=result.get("code", ErrorCode.INTERNAL_ERROR),
                message=result.get("message", "上传失败"),
                data=result.get("data")
            ).dict()

        # 成功信息直接返回
        return result

    except Exception as e:
        logger.error(f"上传文档失败: {e}")
        return ResponseBuilder.error(
            code=ErrorCode.INTERNAL_ERROR,
            message="系统内部错误",
            data={"error": str(e)}
        ).dict()


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, request: DocumentDeleteRequest):
    """删除文档接口
    
    删除指定doc_id对应的文档及其所有切块内容
    
    Args:
        doc_id: 文档ID
        request: 删除请求参数
        
    Returns:
        Dict: 删除结果信息
    """
    try:
        # 获取服务实例
        doc_service = DocumentService.get_instance()

        # 调用删除服务
        result = await doc_service.delete_file(doc_id=doc_id, is_soft_delete=request.is_soft_delete)

        # 检查结果是否包含错误信息
        if isinstance(result, dict) and result.get("code") != ErrorCode.SUCCESS:
            return ResponseBuilder.error(
                code=result.get("code", ErrorCode.INTERNAL_ERROR),
                message=result.get("message", "删除失败"),
                data=result.get("data")
            ).dict()

        return ResponseBuilder.success(data=result).dict()

    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        return ResponseBuilder.error(
            code=ErrorCode.INTERNAL_ERROR,
            message="系统内部错误",
            data={"error": str(e)}
        ).dict()
