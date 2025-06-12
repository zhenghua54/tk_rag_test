#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查MySQL中的权限数据格式
"""
import sys
from pathlib import Path
import json

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from src.database.mysql.operations import ChunkOperation
from src.utils.common.logger import logger

def check_mysql_permissions():
    """检查MySQL中的权限数据格式"""
    try:
        with ChunkOperation() as op:
            # 获取权限数据
            print("\n=== 权限表数据 ===")
            permission_data = op._execute_query("SELECT * FROM permission_info LIMIT 10")
            for i, record in enumerate(permission_data):
                print(f"\n记录 {i+1}:")
                print(f"  doc_id: {record.get('doc_id')}")
                print(f"  permission_ids: {record.get('permission_ids')}")
                
                # 尝试解析permission_ids
                try:
                    if record.get('permission_ids'):
                        perm_data = json.loads(record.get('permission_ids'))
                        print(f"  解析后的权限数据: {perm_data}")
                        print(f"  数据类型: {type(perm_data)}")
                except Exception as e:
                    print(f"  权限数据解析失败: {e}")
            
            # 获取segment_info和permission_info的关联数据
            print("\n=== 片段与权限关联数据 ===")
            query = """
            SELECT s.seg_id, s.doc_id, p.permission_ids 
            FROM segment_info s
            LEFT JOIN permission_info p ON s.doc_id = p.doc_id
            LIMIT 10
            """
            join_data = op._execute_query(query)
            for i, record in enumerate(join_data):
                print(f"\n关联记录 {i+1}:")
                print(f"  seg_id: {record.get('seg_id')}")
                print(f"  doc_id: {record.get('doc_id')}")
                print(f"  permission_ids: {record.get('permission_ids')}")
                
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_mysql_permissions() 