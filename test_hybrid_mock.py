#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用模拟对象测试HybridRetriever类
"""
from collections import OrderedDict
from typing import Dict, List, Any
from unittest.mock import MagicMock

class Document:
    """模拟LangChain Document类"""
    def __init__(self, page_content: str, metadata: Dict[str, Any] = None):
        self.page_content = page_content
        self.metadata = metadata or {}


def merge_search_results(
        vector_results: Dict[str, float],
        bm25_results: Dict[str, float]
) -> Dict[str, float]:
    """合并向量检索和 BM25 检索结果"""
    merged_results = OrderedDict()
    seen_ids = set()

    for seg_id, score in vector_results.items():
        if seg_id not in seen_ids:
            merged_results[seg_id] = score
            seen_ids.add(seg_id)

    for seg_id, score in bm25_results.items():
        if seg_id not in seen_ids:
            merged_results[seg_id] = score
            seen_ids.add(seg_id)

    return merged_results


class HybridRetriever:
    """混合检索器类的模拟实现"""

    def __init__(self, vector_retriever, bm25_retriever):
        """初始化混合检索器"""
        self._vector_retriever = vector_retriever
        self._bm25_retriever = bm25_retriever

    def get_relevant_documents(self, query: str, *, permission_ids: str = None, k: int = 20, top_k: int = 5,
                               chunk_op=None) -> List[Document]:
        """获取相关文档"""
        try:
            # 向量检索
            vector_results = self._vector_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
                chunk_op=chunk_op
            )

            # BM25检索
            bm25_results = self._bm25_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
                chunk_op=chunk_op
            )

            # 合并结果
            merged_results = merge_search_results(vector_results, bm25_results)
            print(f"[混合检索] 合并结果完成,共 {len(merged_results)} 条")

            # 模拟从 mysql 获取原文内容
            rerank_input = []
            for seg_id, score in merged_results.items():
                doc = Document(
                    page_content=f"模拟内容 {seg_id}",
                    metadata={
                        "seg_id": seg_id,
                        "doc_id": f"doc_{seg_id.split('_')[1]}",
                        "seg_page_idx": "1",
                    }
                )
                rerank_input.append(doc)

            print(f"[混合检索] 获取原文完成,共 {len(rerank_input)} 条")
            
            # 模拟重排序
            # 在这个模拟实现中，我们直接返回前top_k个结果，不做实际重排序
            final_results = rerank_input[:top_k]
            print(f"[重排序] 重排完成, 返回 {len(final_results)} 条结果")

            return final_results

        except Exception as error:
            print(f"混合检索失败: {str(error)}")
            return []


def test_hybrid_retriever_with_mocks():
    """使用模拟对象测试HybridRetriever"""
    print("\n=== 测试混合检索器(使用模拟对象) ===")
    
    # 创建模拟对象
    mock_vector_retriever = MagicMock()
    mock_bm25_retriever = MagicMock()
    
    # 设置模拟对象的返回值
    mock_vector_retriever.search.return_value = {
        "seg_001": 0.95,
        "seg_002": 0.85,
        "seg_003": 0.75
    }
    
    mock_bm25_retriever.search.return_value = {
        "seg_003": 0.80,  # 重复的ID
        "seg_004": 0.70,
        "seg_005": 0.65
    }
    
    # 创建HybridRetriever实例
    hybrid_retriever = HybridRetriever(
        vector_retriever=mock_vector_retriever,
        bm25_retriever=mock_bm25_retriever
    )
    
    # 执行测试
    test_query = "测试查询"
    test_permission_id = "test_permission"
    
    results = hybrid_retriever.get_relevant_documents(
        query=test_query,
        permission_ids=test_permission_id,
        k=10,
        top_k=3
    )
    
    # 验证模拟对象被正确调用
    mock_vector_retriever.search.assert_called_once_with(
        query=test_query,
        permission_ids=test_permission_id,
        k=10,
        chunk_op=None
    )
    
    mock_bm25_retriever.search.assert_called_once_with(
        query=test_query,
        permission_ids=test_permission_id,
        k=10,
        chunk_op=None
    )
    
    # 验证结果
    print(f"获取到 {len(results)} 条结果:")
    for i, doc in enumerate(results):
        print(f"[{i+1}] 文档ID: {doc.metadata.get('doc_id')}")
        print(f"    片段ID: {doc.metadata.get('seg_id')}")
        print(f"    内容: {doc.page_content}")
    
    assert len(results) == 3, "应返回3条结果"
    assert results[0].metadata.get("seg_id") == "seg_001", "第一条结果应为seg_001"
    
    print("混合检索器测试通过!")


def test_hybrid_retriever_edge_cases():
    """测试混合检索器的边缘情况"""
    print("\n=== 测试混合检索器边缘情况 ===")
    
    # 创建模拟对象
    mock_vector_retriever = MagicMock()
    mock_bm25_retriever = MagicMock()
    
    # 测试空结果
    mock_vector_retriever.search.return_value = {}
    mock_bm25_retriever.search.return_value = {}
    
    hybrid_retriever = HybridRetriever(
        vector_retriever=mock_vector_retriever,
        bm25_retriever=mock_bm25_retriever
    )
    
    empty_results = hybrid_retriever.get_relevant_documents(
        query="空查询",
        permission_ids="test",
        top_k=5
    )
    
    print(f"空结果测试: 返回 {len(empty_results)} 条结果")
    assert len(empty_results) == 0, "应返回0条结果"
    
    # 测试只有向量检索有结果
    mock_vector_retriever.search.return_value = {"seg_001": 0.9}
    mock_bm25_retriever.search.return_value = {}
    
    vector_only_results = hybrid_retriever.get_relevant_documents(
        query="只有向量",
        permission_ids="test",
        top_k=5
    )
    
    print(f"只有向量结果测试: 返回 {len(vector_only_results)} 条结果")
    assert len(vector_only_results) == 1, "应返回1条结果"
    assert vector_only_results[0].metadata.get("seg_id") == "seg_001", "结果应为seg_001"
    
    # 测试异常情况
    mock_vector_retriever.search.side_effect = Exception("模拟异常")
    
    try:
        exception_results = hybrid_retriever.get_relevant_documents(
            query="异常测试",
            permission_ids="test",
            top_k=5
        )
        print(f"异常处理测试: 返回 {len(exception_results)} 条结果")
        assert len(exception_results) == 0, "异常情况应返回空列表"
    except Exception as e:
        print(f"异常处理失败: {e}")
        assert False, "异常应被正确处理"
    
    print("边缘情况测试通过!")


if __name__ == "__main__":
    # 运行测试
    test_hybrid_retriever_with_mocks()
    test_hybrid_retriever_edge_cases()
    print("\n所有测试通过!") 