#!/usr/bin/env python3
"""
查找Milvus中的所有数据
"""

import os
import sys
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

from pymilvus import Collection, connections, utility, db
from config.global_config import GlobalConfig

def find_all_milvus_data():
    """查找所有Milvus数据库和集合"""
    try:
        # 连接到Milvus
        connections.connect(
            alias="default",
            host=GlobalConfig.MILVUS_CONFIG["host"],
            port=GlobalConfig.MILVUS_CONFIG["port"]
        )
        
        print("=" * 60)
        print("查找Milvus中的所有数据")
        print("=" * 60)
        
        # 1. 列出所有数据库
        print("1. 所有数据库:")
        databases = db.list_database()
        for db_name in databases:
            print(f"  - {db_name}")
        
        # 2. 检查每个数据库中的集合
        for db_name in databases:
            print(f"\n2. 数据库 '{db_name}' 中的集合:")
            
            try:
                # 切换到该数据库
                db.using_database(db_name)
                collections = utility.list_collections()
                
                for collection_name in collections:
                    try:
                        collection = Collection(collection_name)
                        collection.load()
                        num_entities = collection.num_entities
                        print(f"  - {collection_name}: {num_entities} 个实体")
                        
                        # 如果有数据，显示一些样本
                        if num_entities > 0:
                            print(f"    样本数据:")
                            try:
                                sample = collection.query(
                                    expr="",
                                    output_fields=["doc_id", "seg_id"],
                                    limit=3
                                )
                                for i, item in enumerate(sample):
                                    print(f"      {i+1}. doc_id: {item.get('doc_id', 'N/A')}")
                                    print(f"         seg_id: {item.get('seg_id', 'N/A')}")
                            except Exception as e:
                                print(f"      查询样本失败: {e}")
                        
                    except Exception as e:
                        print(f"  - {collection_name}: 访问失败 ({e})")
                        
            except Exception as e:
                print(f"  访问数据库 '{db_name}' 失败: {e}")
        
        # 3. 特别检查我们期望的集合
        print(f"\n3. 特别检查目标集合:")
        target_db = GlobalConfig.MILVUS_CONFIG["db_name"]
        target_collection = GlobalConfig.MILVUS_CONFIG["collection_name"]
        
        print(f"目标数据库: {target_db}")
        print(f"目标集合: {target_collection}")
        
        try:
            db.using_database(target_db)
            collection = Collection(target_collection)
            collection.load()
            
            print(f"实体数量: {collection.num_entities}")
            print(f"集合状态: {collection.get_load_state()}")
            
            # 检查集合schema
            print("集合字段:")
            for field in collection.schema.fields:
                print(f"  - {field.name}: {field.dtype}")
                
        except Exception as e:
            print(f"检查目标集合失败: {e}")
            
        # 4. 查找可能的 "rag" 相关集合
        print(f"\n4. 搜索可能的RAG相关集合:")
        for db_name in databases:
            try:
                db.using_database(db_name)
                collections = utility.list_collections()
                
                rag_collections = [c for c in collections if 'rag' in c.lower()]
                if rag_collections:
                    print(f"数据库 '{db_name}' 中的RAG集合:")
                    for coll_name in rag_collections:
                        try:
                            collection = Collection(coll_name)
                            collection.load()
                            print(f"  - {coll_name}: {collection.num_entities} 个实体")
                        except Exception as e:
                            print(f"  - {coll_name}: 无法访问 ({e})")
                            
            except Exception as e:
                continue
            
    except Exception as e:
        print(f"查找失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_all_milvus_data()
