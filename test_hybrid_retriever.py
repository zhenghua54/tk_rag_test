#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试混合检索器功能
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from src.core.rag.hybrid_retriever import HybridRetriever, merge_search_results
from src.core.rag.retrieval.vector_retriever import VectorRetriever
from src.core.rag.retrieval.bm25_retriever import BM25Retriever
from src.database.elasticsearch.operations import ElasticsearchOperation
from src.database.mysql.operations import ChunkOperation
from langchain_milvus import Milvus
from src.core.rag.embedder import init_langchain_embeddings
from config.settings import Config
from src.utils.common.logger import logger

# 测试合并结果函数
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

# 初始化检索组件 - 模拟版本
def init_mock_retrievers():
    """初始化模拟的检索器，不需要真实的数据库连接"""
    print("\n=== 初始化模拟检索组件 ===")
    
    class MockVectorRetriever:
        def search(self, query, permission_ids=None, k=5, chunk_op=None):
            print(f"[模拟] 执行向量检索: query={query}, permission_ids={permission_ids}")
            return {
                "mock_seg_001": 0.95,
                "mock_seg_002": 0.85,
                "mock_seg_003": 0.75
            }
    
    class MockBM25Retriever:
        def search(self, query, permission_ids=None, k=5, chunk_op=None):
            print(f"[模拟] 执行BM25检索: query={query}, permission_ids={permission_ids}")
            return {
                "mock_seg_003": 0.80, 
                "mock_seg_004": 0.70,
                "mock_seg_005": 0.65
            }
    
    return MockVectorRetriever(), MockBM25Retriever()

# 测试混合检索器 - 模拟版本
def test_mock_hybrid_retriever():
    """测试混合检索器功能 (模拟版本)"""
    print("\n=== 测试混合检索器 (模拟版本) ===")
    
    # 初始化模拟检索器
    vector_retriever, bm25_retriever = init_mock_retrievers()
    
    # 测试合并结果函数
    mock_vector_results = vector_retriever.search("测试查询")
    mock_bm25_results = bm25_retriever.search("测试查询")
    
    merged_results = merge_search_results(mock_vector_results, mock_bm25_results)
    print(f"合并后的结果: {merged_results}")
    print(f"合并后结果数量: {len(merged_results)}")
    
    print("混合检索器模拟测试完成!")

# 初始化检索组件 - 真实版本
def init_real_retrievers():
    """初始化真实的向量检索器和BM25检索器"""
    print("\n=== 初始化真实检索组件 ===")
    
    try:
        # 初始化embeddings模型
        print("初始化embeddings模型...")
        embeddings = init_langchain_embeddings()
        print(f"embeddings模型初始化成功，使用设备: {Config.DEVICE}")
        
        # 初始化Milvus向量存储
        print("初始化Milvus向量存储...")
        print(f"Milvus配置: {Config.MILVUS_CONFIG['uri']}, {Config.MILVUS_CONFIG['collection_name']}")
        
        milvus_vectorstore = Milvus(
            embedding_function=embeddings,
            collection_name=Config.MILVUS_CONFIG["collection_name"],
            connection_args={
                "uri": Config.MILVUS_CONFIG["uri"],
                "token": Config.MILVUS_CONFIG["token"],
                "db_name": Config.MILVUS_CONFIG["db_name"]
            },
            search_params={
                "metric_type": Config.MILVUS_CONFIG["index_params"]["metric_type"],
                "params": Config.MILVUS_CONFIG["search_params"]
            },
            text_field="seg_content"
        )
        print("Milvus向量存储初始化成功")
        
        # 初始化ES检索
        print("初始化ES检索...")
        print(f"ES配置: {Config.ES_CONFIG['host']}, {Config.ES_CONFIG['index_name']}")
        
        es_retriever = ElasticsearchOperation(
            index_name=Config.ES_CONFIG["index_name"],
            hosts=Config.ES_CONFIG["host"],
            http_auth=(Config.ES_CONFIG["username"], Config.ES_CONFIG["password"])
        )
        print("ES检索初始化成功")
        
        # 初始化向量检索器
        vector_retriever = VectorRetriever(vectorstore=milvus_vectorstore)
        
        # 初始化BM25检索器
        bm25_retriever = BM25Retriever(es_retriever=es_retriever)
        
        return vector_retriever, bm25_retriever
        
    except Exception as e:
        print(f"初始化检索器失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None

# 测试真实的混合检索器
def test_real_hybrid_retriever():
    """测试真实的混合检索器功能"""
    print("\n=== 测试真实的混合检索器 ===")
    
    # 初始化真实检索组件
    vector_retriever, bm25_retriever = init_real_retrievers()
    
    if not vector_retriever or not bm25_retriever:
        print("真实检索器初始化失败，跳过真实混合检索测试")
        return
    
    # 初始化混合检索器
    hybrid_retriever = HybridRetriever(
        vector_retriever=vector_retriever,
        bm25_retriever=bm25_retriever
    )
    
    # 准备测试查询
    test_query = "企业知识库的架构设计"
    permission_id = ["test_permission_id"]  # 使用列表格式
    
    # 执行混合检索
    print(f"执行混合检索，查询: '{test_query}'")
    
    try:
        results = hybrid_retriever.get_relevant_documents(
            query=test_query,
            permission_ids=permission_id,
            k=10,
            top_k=5
        )
        
        # 打印检索结果
        print(f"检索到 {len(results)} 条结果:")
        for i, doc in enumerate(results):
            print(f"\n[{i+1}] 文档ID: {doc.metadata.get('doc_id')}")
            print(f"片段ID: {doc.metadata.get('seg_id')}")
            print(f"页码: {doc.metadata.get('seg_page_idx')}")
            print(f"内容预览: {doc.page_content[:100]}...")
            
    except Exception as e:
        print(f"混合检索器执行失败: {e}")
        import traceback
        traceback.print_exc()

# 执行测试
if __name__ == "__main__":
    # 测试合并函数
    test_merge_search_results()
    
    # 测试模拟的混合检索器
    test_mock_hybrid_retriever()
    
    # 根据环境变量决定是否测试真实的混合检索器
    if os.getenv("TEST_REAL_RETRIEVER", "false").lower() == "true":
        test_real_hybrid_retriever()
    else:
        print("\n跳过真实混合检索器测试。如需测试，请设置环境变量 TEST_REAL_RETRIEVER=true") 