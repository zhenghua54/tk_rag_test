#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试混合检索系统
"""
import sys
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from src.core.rag.hybrid_retriever import HybridRetriever, init_retrievers
from src.utils.common.logger import logger

def test_hybrid_retriever():
    """测试混合检索系统"""
    try:
        # 初始化检索器
        vector_retriever, bm25_retriever = init_retrievers()
        
        # 创建混合检索器实例
        hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)
        
        # 测试查询列表
        queries = [
            "发行人是什么?",
            "公司的竞争优势有哪些?",
            "公司成立于哪一年?",
            "AI业务的发展情况如何?"
        ]
        
        # 测试每个查询
        for query in queries:
            print(f"\n\n===== 查询: '{query}' =====")
            
            # 执行混合检索
            docs = hybrid_retriever._get_relevant_documents(query)
            
            print(f"找到 {len(docs)} 条结果")
            
            # 打印检索结果
            for i, doc in enumerate(docs):
                print(f"\n结果 {i+1}:")
                print(f"  内容: {doc.page_content[:150]}...")
                print(f"  元数据: {doc.metadata}")
    
    except Exception as e:
        print(f"测试混合检索系统失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hybrid_retriever() 