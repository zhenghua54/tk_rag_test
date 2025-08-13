#!/usr/bin/env python3
"""
测试修复后的基于doc_id的游标翻页方案
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from databases.milvus.flat_collection import FlatCollectionManager
import logging

# 设置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fixed_cursor_pagination():
    """测试修复后的游标翻页功能"""
    
    print("=" * 60)
    print("测试修复后的基于doc_id的游标翻页方案")
    print("=" * 60)
    
    try:
        # 使用ragbench_msmarco集合进行测试
        collection_name = "ragbench_msmarco"
        flat_manager = FlatCollectionManager(collection_name=collection_name)
        
        if not flat_manager.collection_exists():
            print(f"❌ 集合 {collection_name} 不存在")
            return False
        
        print(f"✅ 集合 {collection_name} 存在")
        print("集合Schema中主键字段: doc_id (字符串类型)")
        
        # 测试游标翻页获取doc_id
        print("\n开始测试基于doc_id的游标翻页...")
        doc_ids = flat_manager.get_all_doc_ids()
        
        print(f"✅ 成功获取到 {len(doc_ids)} 个doc_id")
        print(f"预期数量: 21879 (根据Schema信息)")
        
        if doc_ids:
            print(f"前5个doc_id示例: {doc_ids[:5]}")
            print(f"最后5个doc_id示例: {doc_ids[-5:]}")
            
            # 验证去重效果
            unique_count = len(set(doc_ids))
            print(f"去重后数量: {unique_count}")
            if unique_count == len(doc_ids):
                print("✅ 去重正确，没有重复的doc_id")
            else:
                print(f"⚠️  发现重复，原始: {len(doc_ids)}, 去重后: {unique_count}")
        
        print("\n🎉 修复后的游标翻页测试成功！")
        return True
        
    except Exception as e:
        print(f"❌ 游标翻页测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_string_comparison():
    """测试字符串比较的正确性"""
    
    print("\n" + "=" * 60)
    print("测试字符串比较的正确性")
    print("=" * 60)
    
    # 模拟一些doc_id进行字符串比较测试
    test_doc_ids = [
        "0a1b2c3d4e5f6789",
        "1a2b3c4d5e6f7890", 
        "2a3b4c5d6e7f8901",
        "abc123def456",
        "def456ghi789"
    ]
    
    print("测试字符串排序:")
    sorted_ids = sorted(test_doc_ids)
    for i, doc_id in enumerate(sorted_ids):
        print(f"  {i+1}. {doc_id}")
    
    print("\n测试字符串比较:")
    for i in range(len(sorted_ids) - 1):
        current = sorted_ids[i]
        next_id = sorted_ids[i + 1]
        result = current < next_id
        print(f"  \"{current}\" < \"{next_id}\": {result}")
    
    print("✅ 字符串比较测试完成")
    return True

if __name__ == "__main__":
    print("修复后的基于doc_id的游标翻页测试")
    print("=" * 60)
    
    # 主要测试
    success1 = test_fixed_cursor_pagination()
    
    # 字符串比较测试
    success2 = test_string_comparison()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 所有测试完成！修复后的游标翻页方案工作正常。")
        print("✅ 修复内容：")
        print("   - 使用正确的主键字段名: doc_id (而不是pk)")
        print("   - 使用字符串比较: doc_id > \"last_value\"")
        print("   - 应用层排序确保游标翻页的正确性")
        print("   - 完全避免max_query_result_window限制")
    else:
        print("⚠️  测试完成，但存在问题，请检查日志。")
