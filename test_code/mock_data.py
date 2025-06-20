"""Mock 服务模块

提供测试数据，方便前后端联调。后期可以方便地替换为真实服务。
"""
from typing import Dict, Any

from services.doc_server import DocumentService
from services.chat_server import ChatService


class MockChatService(ChatService):

    @staticmethod
    def chat_response(query: str, **kwargs) -> Dict[str, Any]:
        """生成聊天测试响应
        
        Args:
            query: 用户问题
            **kwargs: 其他参数
            
        Returns:
            Dict: 测试响应数据
        """
        return {
            "answer": f"这是对问题 '{query}' 的模拟回答",
            "source": [
                {
                    "doc_id": "doc_mock_001",
                    "file_name": "测试文档1.pdf",
                    "segment_context": "片段文本",
                    "page_idx": "1",
                    "confidence": 0.95
                },
                {
                    "doc_id": "doc_mock_002",
                    "file_name": "测试文档2.pdf",
                    "segment_context": "片段文本",
                    "page_idx": "2",
                    "confidence": 0.85
                }
            ],
            "tokens_used": 123,
            "processing_time": 0.5
        }


class MockDocumentService(DocumentService):

    @staticmethod
    async def upload_file(document_http_url: str, permission_ids: str, callback_url: str = None) -> dict:
        return {
            "doc_id": "文件内容+标题的哈希值",
            "doc_name": "mock_document.pdf",
            "status": "uploaded",
            "permission_ids": permission_ids,
        }

    @staticmethod
    async def delete_file(doc_id: str, is_soft_delete: bool = True, callback_url: str = None) -> Dict[str, Any]:
        return {
            "doc_id": doc_id,
            "status": "deleted",
            "delete_type": "记录删除" if is_soft_delete else "记录+文件删除",
        }
