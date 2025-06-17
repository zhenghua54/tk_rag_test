#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试权限过滤功能
"""
import sys
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from src.core.rag.hybrid_retriever import HybridRetriever, init_retrievers
from src.utils.common.logger import logger

def test_permission_filter():
    """测试权限过滤功能"""
    try:
        # 初始化检索器
        vector_retriever, bm25_retriever = init_retrievers()
        
        # 创建混合检索器实例
        hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)
        
        # 测试查询
        query = "发行人是什么?"
        
        # 测试不同的权限ID
        permission_ids_list = ["1", "2", "3", None]
        
        for permission_ids in permission_ids_list:
            print(f"\n\n===== 查询: '{query}', 权限ID: '{permission_ids}' =====")
            
            # 执行混合检索
            docs = hybrid_retriever.get_relevant_documents(
                query, 
                top_k=5, 
                permission_ids=permission_ids
            )
            
            print(f"找到 {len(docs)} 条结果")
            
            # 输出结果
            for i, doc in enumerate(docs):
                print(f"\n--- 结果 {i+1} ---")
                print(f"内容: {doc.page_content[:100]}...")
                print(f"元数据: {doc.metadata}")
                
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_permission_filter() 