#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据库中的权限数据格式
"""
import sys
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from src.database.mysql.operations import ChunkOperation
from src.utils.common.logger import logger

def check_permissions():
    """检查数据库中的权限数据格式"""
    try:
        with ChunkOperation() as op:
            # 检查权限表结构
            print("\n=== 权限表结构 ===")
            table_info = op._execute_query("DESCRIBE permission_info")
            for field in table_info:
                print(f"字段: {field['Field']}, 类型: {field['Type']}, 可空: {field['Null']}, 默认值: {field['Default']}")
            
            # 获取权限数据示例
            print("\n=== 权限数据示例 ===")
            permission_data = op._execute_query("SELECT * FROM permission_info LIMIT 10")
            for i, record in enumerate(permission_data):
                print(f"\n记录 {i+1}:")
                print(f"  权限ID: '{record['permission_ids']}', 类型: {type(record['permission_ids'])}")
                print(f"  文档ID: '{record['doc_id']}'")
                print(f"  创建时间: {record['created_at']}")
            
            # 检查ES中的权限数据
            print("\n=== ES中的权限数据 ===")
            from src.database.elasticsearch.operations import ElasticsearchOperation
            es_op = ElasticsearchOperation()
            docs = es_op.list_all_documents(size=10)
            for i, doc in enumerate(docs):
                print(f"\n文档 {i+1}:")
                print(f"  文档ID: {doc['_source'].get('doc_id')}")
                print(f"  片段ID: {doc['_source'].get('seg_id')}")
                print(f"  权限ID: '{doc['_source'].get('permission_ids')}', 类型: {type(doc['_source'].get('permission_ids'))}")
            
            # 检查Milvus中的权限数据
            print("\n=== Milvus中的权限数据 ===")
            from pymilvus import connections, Collection
            try:
                connections.connect(
                    uri="http://localhost:19530", 
                    token="root:Milvus", 
                    db_name="default"
                )
                collection = Collection("tk_rag")
                results = collection.query(
                    expr="", 
                    output_fields=["seg_id", "permission_ids"], 
                    limit=10
                )
                for i, r in enumerate(results):
                    print(f"\n记录 {i+1}:")
                    print(f"  片段ID: {r.get('seg_id')}")
                    print(f"  权限ID: '{r.get('permission_ids')}', 类型: {type(r.get('permission_ids'))}")
            except Exception as e:
                print(f"Milvus查询失败: {e}")
    
    except Exception as e:
        print(f"检查权限数据失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_permissions() 