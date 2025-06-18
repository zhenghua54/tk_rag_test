#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查Elasticsearch中的数据
"""
import sys
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from databases.elasticsearch.operations import ElasticsearchOperation


def check_es_index():
    """检查ES索引信息"""
    print("\n=== 检查ES索引信息 ===")
    try:
        es_op = ElasticsearchOperation()
        stats = es_op.get_stats()
        print(f"索引名称: {es_op.index_name}")
        print(f"文档数量: {stats.get('doc_count', 0)}")
        print(f"索引大小: {stats.get('store_size', '0')}")
    except Exception as e:
        print(f"获取索引信息失败: {e}")

def search_es_data():
    """搜索ES中的数据"""
    print("\n=== 搜索ES中的数据 ===")
    try:
        es_op = ElasticsearchOperation()
        
        # 获取所有文档
        all_docs = es_op.list_all_documents(size=10)
        print(f"ES中共有 {len(all_docs)} 条文档")
        
        # 打印前5条文档
        for i, doc in enumerate(all_docs[:5]):
            print(f"\n文档 {i+1}:")
            print(f"  ID: {doc['_id']}")
            print(f"  分数: {doc.get('_score', 'N/A')}")
            print(f"  文档ID: {doc['_source'].get('doc_id', 'N/A')}")
            print(f"  内容预览: {doc['_source'].get('seg_content', 'N/A')[:100]}...")
            print(f"  权限ID: {doc['_source'].get('permission_ids', 'N/A')}")
        
        # 尝试搜索特定关键词
        keywords = ["发行人", "竞争", "公司"]
        for keyword in keywords:
            print(f"\n搜索关键词 '{keyword}':")
            results = es_op.search(query=keyword, top_k=3)
            print(f"  找到 {len(results)} 条结果")
            
            # 打印搜索结果
            for i, hit in enumerate(results):
                print(f"  结果 {i+1}:")
                print(f"    ID: {hit['_id']}")
                print(f"    分数: {hit['_score']}")
                print(f"    内容预览: {hit['_source'].get('seg_content', 'N/A')[:100]}...")
    
    except Exception as e:
        print(f"搜索ES数据失败: {e}")

if __name__ == "__main__":
    try:
        check_es_index()
        search_es_data()
    except Exception as e:
        print(f"发生错误: {e}") 