"""文档服务实现
"""
from typing import Dict, Any, Optional
from src.services.base import BaseService
from src.services.mock import MockData

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
            Dict: 上传响应数据
        """
        # TODO: 实现真实的文档上传逻辑
        raise NotImplementedError("真实文档上传服务尚未实现")
    
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