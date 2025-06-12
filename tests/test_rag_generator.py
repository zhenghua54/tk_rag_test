#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试RAG生成功能
"""
import sys
import json
import uuid
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from src.core.rag.hybrid_retriever import HybridRetriever, init_retrievers
from src.core.rag.llm_generator import RAGGenerator
from src.utils.common.logger import logger

def test_rag_generator():
    """测试RAG生成功能"""
    try:
        # 初始化检索器
        vector_retriever, bm25_retriever = init_retrievers()
        
        # 创建混合检索器实例
        hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)
        
        # 创建RAG生成器实例
        rag_generator = RAGGenerator(hybrid_retriever)
        
        # 测试查询列表
        test_cases = [
            {
                "query": "发行人是什么?",
                "permission_ids": None,  # 不带权限过滤
                "session_id": str(uuid.uuid4())
            },
            {
                "query": "发行人是什么?",
                "permission_ids": json.dumps({"departments": ["1"], "roles": [], "users": []}),  # 带权限过滤
                "session_id": str(uuid.uuid4())
            },
            {
                "query": "公司的竞争优势有哪些?",
                "permission_ids": None,
                "session_id": str(uuid.uuid4())
            }
        ]
        
        # 测试每个查询
        for i, test_case in enumerate(test_cases):
            print(f"\n\n===== 测试用例 {i+1} =====")
            print(f"查询: '{test_case['query']}'")
            print(f"权限ID: '{test_case['permission_ids']}'")
            print(f"会话ID: '{test_case['session_id']}'")
            
            # 生成回答
            response = rag_generator.generate_response(
                query=test_case["query"],
                session_id=test_case["session_id"],
                permission_ids=test_case["permission_ids"]
            )
            
            # 输出结果
            print("\n--- 生成结果 ---")
            if response.get("status") == "success":
                print(f"回答: {response['data']['answer']}")
                
                print("\n--- 源文档信息 ---")
                for i, source in enumerate(response['data']['metadata']):
                    print(f"\n源文档 {i+1}:")
                    print(f"  文档ID: {source.get('doc_id')}")
                    print(f"  片段ID: {source.get('seg_id')}")
                    print(f"  文档URL: {source.get('doc_http_url')}")
                    print(f"  相关度分数: {source.get('score')}")
                    
                print("\n--- 对话历史 ---")
                for msg in response['data']['chat_history']:
                    print(f"{msg['role']}: {msg['content']}")
            else:
                print(f"错误: {response.get('message')}")
                
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rag_generator() 