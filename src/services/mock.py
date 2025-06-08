"""Mock 服务模块

提供测试数据，方便前后端联调。后期可以方便地替换为真实服务。
"""
from typing import Dict, Any, Optional
import time

class MockData:
    """Mock数据类
    
    集中管理所有的测试数据
    """
    
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
                    "segment_id": "seg_001",
                    "page_idx": "1",
                    "confidence": 0.95
                },
                {
                    "doc_id": "doc_mock_002", 
                    "file_name": "测试文档2.pdf",
                    "segment_id": "seg_002",
                    "page_idx": "2",
                    "confidence": 0.85
                }
            ],
            "tokens_used": 123,
            "processing_time": 0.5
        }
    
    @staticmethod
    def document_upload_response(doc_path: str, **kwargs) -> Dict[str, Any]:
        """生成文档上传测试响应
        
        Args:
            doc_path: 文件路径
            **kwargs: 其他参数
            
        Returns:
            Dict: 测试响应数据
        """
        import os
        return {
            "doc_id": "215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83",
            "file_name": "天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225",
            "status": "completed",
            "department_id": ["1"],
        }
    
    @staticmethod
    def document_delete_response(doc_id: str, **kwargs) -> Dict[str, Any]:
        """生成文档删除测试响应
        
        Args:
            doc_id: 文档ID
            **kwargs: 其他参数
            
        Returns:
            Dict: 测试响应数据
        """
        return {
            "doc_id": doc_id,
            "delete_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "deleted"
        } 