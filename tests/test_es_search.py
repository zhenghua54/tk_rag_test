#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试ES搜索功能
"""
import sys
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from src.database.elasticsearch.operations import ElasticsearchOperation
from src.utils.common.logger import logger

def test_es_search():
    """测试ES搜索功能"""
    try:
        es_op = ElasticsearchOperation()
        
        # 测试关键词列表
        keywords = [
            "发行人",
            "发行人是什么",
            "竞争",
            "公司",
            "公司成立于",
            "AI"
        ]
        
        # 测试每个关键词
        for keyword in keywords:
            print(f"\n\n===== 搜索关键词: '{keyword}' =====")
            results = es_op.search(query=keyword, top_k=3)
            print(f"找到 {len(results)} 条结果")
            
            # 打印搜索结果
            for i, hit in enumerate(results):
                print(f"\n结果 {i+1}:")
                print(f"  ID: {hit['_id']}")
                print(f"  分数: {hit['_score']}")
                print(f"  文档ID: {hit['_source'].get('doc_id', 'N/A')}")
                print(f"  内容预览: {hit['_source'].get('seg_content', 'N/A')[:150]}...")
    
    except Exception as e:
        print(f"测试ES搜索失败: {e}")

if __name__ == "__main__":
    test_es_search() 