"""文档API实现
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import os
from src.api.base import APIResponse, ErrorCode
from src.services.document import DocumentService
from config.settings import Config

router = APIRouter(prefix="/api/v1")

class DocumentUploadRequest(BaseModel):
    """文档上传请求模型
    
    Attributes:
        document_path: 文件路径
        department_id: 部门ID
    """
    document_path: str = Field(..., description="文件路径")
    department_id: str = Field(..., description="部门UUID")
    
    @field_validator("document_path")
    @classmethod
    def validate_file(cls, v):
        if not os.path.exists(v):
            return APIResponse.error(
                code=ErrorCode.FILE_NOT_FOUND,
                message="文件不存在",
                data={
                    "file_path": v,
                    "reason": "文件路径不存在"
                }
            )
        
        # 检查文件大小
        if os.path.getsize(v) > Config.MAX_FILE_SIZE:
            return APIResponse.error(
                code=ErrorCode.FILE_SIZE_LIMIT,
                message="文件大小超限",
                data={
                    "file_path": v,
                    "current_size": os.path.getsize(v),
                    "max_size": Config.MAX_FILE_SIZE
                }
            )
            
        # 检查文件扩展名
        ext = os.path.splitext(v)[1].lower()
        if ext not in Config.SUPPORTED_FILE_TYPES["all"]:
            return APIResponse.error(
                code=ErrorCode.FILE_TYPE_NOT_SUPPORTED,
                message="文件格式不支持",
                data={
                    "file_path": v,
                    "current_type": ext,
                    "supported_types": Config.SUPPORTED_FILE_TYPES["all"]
                }
            )
            
        return v

class DocumentDeleteRequest(BaseModel):
    """文档删除请求模型
    
    Attributes:
        is_soft_delete: 是否软删除
    """
    is_soft_delete: Optional[bool] = Field(False, description="是否软删除")

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
        result = await doc_service.upload(
            file_path=request.document_path,
            department_id=request.department_id
        )
        return APIResponse.success(data=result)
        
    except Exception as e:
        # 记录未预期的错误
        import logging
        logging.exception("Document upload error")
        return APIResponse.error(
            code=ErrorCode.FILE_PARSE_ERROR,
            message="文件解析失败",
            data={
                "error": str(e),
                "suggestion": "请检查文件是否损坏或格式是否正确"
            }
        )

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
        result = await doc_service.delete(
            doc_id=doc_id,
            is_soft_delete=request.is_soft_delete
        )
        return APIResponse.success(data=result)
        
    except Exception as e:
        # 记录未预期的错误
        import logging
        logging.exception("Document delete error")
        return APIResponse.error(
            code=ErrorCode.FILE_PARSE_ERROR,
            message="删除失败",
            data={
                "error": str(e),
                "suggestion": "请稍后重试或联系管理员"
            }
        ) 