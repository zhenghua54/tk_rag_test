#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据库表结构
"""
import sys
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from databases.mysql.operations import ChunkOperation, FileInfoOperation, PermissionOperation

def check_segment_table():
    """检查segment_info表结构"""
    print("\n=== 检查segment_info表结构 ===")
    with ChunkOperation() as op:
        try:
            # 尝试获取一条记录
            records = op.select_record()
            if records and len(records) > 0:
                print(f"字段列表: {list(records[0].keys())}")
                print(f"示例记录: {records[0]}")
            else:
                print("表中没有记录")
        except Exception as e:
            print(f"查询segment_info表失败: {e}")

def check_file_info_table():
    """检查file_info表结构"""
    print("\n=== 检查file_info表结构 ===")
    with FileInfoOperation() as op:
        try:
            # 尝试获取一条记录
            records = op.select_record()
            if records and len(records) > 0:
                print(f"字段列表: {list(records[0].keys())}")
                print(f"示例记录: {records[0]}")
            else:
                print("表中没有记录")
        except Exception as e:
            print(f"查询file_info表失败: {e}")

def check_permission_table():
    """检查permission_info表结构"""
    print("\n=== 检查permission_info表结构 ===")
    with PermissionOperation() as op:
        try:
            # 尝试获取一条记录
            records = op.select_record()
            if records and len(records) > 0:
                print(f"字段列表: {list(records[0].keys())}")
                print(f"示例记录: {records[0]}")
            else:
                print("表中没有记录")
        except Exception as e:
            print(f"查询permission_info表失败: {e}")

if __name__ == "__main__":
    try:
        check_segment_table()
        check_file_info_table()
        check_permission_table()
    except Exception as e:
        print(f"发生错误: {e}") 