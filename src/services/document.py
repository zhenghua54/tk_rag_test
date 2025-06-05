"""文档服务实现
"""
from typing import Dict, Any, Optional
from src.services.base import BaseService
from src.services.mock import MockData
from src.core.document.upload_doc import upload_doc
from src.utils.common.logger import logger
from src.api.base import APIResponse, ErrorCode

class DocumentService(BaseService):
    """文档服务类
    
    处理文档相关的业务逻辑
    """
    
    async def upload(self, file_path: str, department_id: str) -> Dict[str, Any]:
        """上传文档
        
        Args:
            file_path: 文件路径
            department_id: 部门ID
            
        Returns:
            Dict: 上传响应数据，包含：
                - doc_id: 文档ID
                - doc_name: 文档名称
                - doc_ext: 文档后缀
                - doc_size: 文档大小
                - doc_path: 文档服务器存储路径
                - created_at: 创建时间
                - updated_at: 更新时间
        """
        # # TODO: 实现真实的文档上传逻辑
        # raise NotImplementedError("真实文档上传服务尚未实现")
        try:
            # 调用上传文档函数，该函数会处理文件信息并保存到数据库
            file_info = upload_doc(file_path, department_id)
            logger.info(f"文件信息: {file_info}")            
            # 构建符合接口文档的响应数据
            response = {
                "code": ErrorCode.SUCCESS.value,
                "message": "success",
                "data": {
                    "doc_id": file_info["doc_id"],
                    "file_name": file_info["doc_name"] + file_info["doc_ext"],
                    "status": "completed",
                    "department_id": department_id  # 确保是字符串
                }
            }
            
            logger.info(f"文档上传成功: {file_path}")
            return response
            
        except Exception as e:
            logger.error(f"文档上传失败: {str(e)}")
            raise Exception(APIResponse.error(
                code=ErrorCode.FILE_PARSE_ERROR,
                message="文件解析失败",
                data={
                    "error": str(e),
                    "suggestion": "请检查文件是否损坏或格式是否正确"
                }
            ).json())
    
    async def delete(self, doc_id: str, is_soft_delete: bool = False) -> Dict[str, Any]:
        """删除文档
        
        Args:
            doc_id: 文档ID
            is_soft_delete: 是否软删除
            
        Returns:
            Dict: 删除响应数据
        """
        # TODO: 实现真实的文档删除逻辑
        raise NotImplementedError("真实文档删除服务尚未实现")

class MockDocumentService(DocumentService):
    """Mock文档服务类"""
    
    async def upload(self, file_path: str, department_id: str) -> Dict[str, Any]:
        """生成 mock 上传响应"""
        return MockData.document_upload_response(
            file_path=file_path,
            department_id=department_id
        )
    
    async def delete(self, doc_id: str, is_soft_delete: bool = False) -> Dict[str, Any]:
        """生成 mock 删除响应"""
        return MockData.document_delete_response(
            doc_id=doc_id,
            is_soft_delete=is_soft_delete
        ) 