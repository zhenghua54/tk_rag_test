#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试混合检索器中的merge_search_results函数
"""
from collections import OrderedDict
from typing import Dict


def merge_search_results(
        vector_results: Dict[str, float],
        bm25_results: Dict[str, float]
) -> Dict[str, float]:
    """合并向量检索和 BM25 检索结果
    
    Args:
        vector_results: 向量检索结果(seg_id, score)
        bm25_results: BM25 检索结果
        
    Returns:
        Dict[str, float]: 合并后的结果字典(seg_id, score)
    """
    merged_results = OrderedDict()
    seen_ids = set()

    # 合并结果保持顺序
    for seg_id, score in vector_results.items():
        if seg_id not in seen_ids:
            merged_results[seg_id] = score
            seen_ids.add(seg_id)

    for seg_id, score in bm25_results.items():
        if seg_id not in seen_ids:
            merged_results[seg_id] = score
            seen_ids.add(seg_id)

    return merged_results


def test_merge_search_results():
    """测试合并检索结果函数"""
    print("\n=== 测试合并检索结果函数 ===")
    
    # 模拟向量检索结果
    vector_results = {
        "seg_001": 0.95,
        "seg_002": 0.85,
        "seg_003": 0.75
    }
    
    # 模拟BM25检索结果
    bm25_results = {
        "seg_003": 0.80,  # 重复的ID
        "seg_004": 0.70,
        "seg_005": 0.65
    }
    
    # 执行合并
    merged = merge_search_results(vector_results, bm25_results)
    
    # 打印合并结果
    print(f"向量检索结果: {vector_results}")
    print(f"BM25检索结果: {bm25_results}")
    print(f"合并后结果: {merged}")
    print(f"合并后结果数量: {len(merged)}")
    
    # 验证合并结果
    assert len(merged) == 5, "合并结果数量应为5"
    assert "seg_003" in merged, "seg_003应出现在合并结果中"
    assert merged["seg_003"] == 0.75, "重复ID应使用向量检索的分数"
    
    print("合并检索结果函数测试通过!")


if __name__ == "__main__":
    test_merge_search_results()
    
    # 测试更复杂的情况
    print("\n=== 测试复杂情况 ===")
    
    # 测试空结果合并
    empty_vector = {}
    empty_bm25 = {}
    empty_merged = merge_search_results(empty_vector, empty_bm25)
    print(f"空结果合并测试: {empty_merged}")
    assert len(empty_merged) == 0, "空结果合并应返回空字典"
    
    # 测试一个为空的情况
    one_empty_merged = merge_search_results(vector_results={}, bm25_results={"seg_001": 0.9})
    print(f"一个为空结果合并测试: {one_empty_merged}")
    assert len(one_empty_merged) == 1, "一个为空的合并应返回非空结果"
    
    # 测试大量结果合并
    large_vector = {f"seg_{i:03d}": 0.9 - i*0.01 for i in range(100)}
    large_bm25 = {f"seg_{i:03d}": 0.8 - i*0.01 for i in range(50, 150)}
    large_merged = merge_search_results(large_vector, large_bm25)
    print(f"大量结果合并测试: 结果数量 = {len(large_merged)}")
    assert len(large_merged) == 150, "大量结果合并应返回正确数量"
    
    print("所有测试通过!") 