"""使用 langchain 框架处理用户 query"""
import psutil
import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from langchain_milvus import Milvus

# 项目配置
from config.settings import Config
from src.utils.common.logger import logger
from src.database.milvus.operations import VectorOperation
from src.database.mysql.operations import ChunkOperation
from src.core.embedding.embedder import init_langchain_embeddings
from src.core.retrieval.vector_retriever import VectorRetriever
from src.core.retrieval.bm25_retriever import BM25Retriever
from src.core.retrieval.hybrid_retriever import HybridRetriever
from src.database.elasticsearch.operations import ElasticsearchOperation


def log_memory_usage():
    """记录当前内存使用情况"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logger.info(f"内存使用: {memory_info.rss / 1024 / 1024:.2f} MB")


def init_bm25_retriever() -> ElasticsearchOperation:
    """初始化基于 Elasticsearch 的 BM25 检索器
    
    Returns:
        ElasticsearchOperation: ES 检索器实例
    """
    logger.info("开始初始化基于 ES 的 BM25 检索器...")

    try:
        es_retriever = ElasticsearchOperation()
        if not es_retriever.ping():
            raise Exception("ES 连接失败")
        logger.info("ES BM25 检索器初始化完成")
        return es_retriever
    except Exception as bm25_error:
        logger.error(f"初始化 ES BM25 检索器失败: {str(bm25_error)}")
        raise


if __name__ == "__main__":
    logger.info("初始化检索系统...")

    try:
        # 初始化向量库操作
        vector_op = VectorOperation()

        # 初始化 embeddings
        logger.info("初始化 embeddings 模型...")
        embeddings = init_langchain_embeddings()

        # 创建 Milvus 向量存储
        logger.info("创建 Milvus 向量存储...")
        vectorstore = Milvus(
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
            text_field="summary_text"
        )
        logger.info("Milvus 向量存储初始化完成")

        # 初始化检索器
        vector_retriever = VectorRetriever(vectorstore=vectorstore)
        bm25_retriever = BM25Retriever(es_retriever=init_bm25_retriever())
        hybrid_retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            bm25_retriever=bm25_retriever
        )

        # 测试场景列表
        test_queries = [
            "执行、 落地、管理工作",  # 简单查询
            "",  # 空查询
            "延迟通报",  # 特殊字符
        ]

        # 使用 with 语句管理 ChunkOperation 生命周期
        with ChunkOperation() as chunk_op:
            # 执行测试
            for query in test_queries:
                logger.info(f"\n{'=' * 50}")
                logger.info(f"测试查询: {query}")
                try:
                    results = hybrid_retriever.get_relevant_documents(
                        query=query,
                        k=5,
                        top_k=5,
                        chunk_op=chunk_op
                    )

                    # 打印结果
                    if not results:
                        logger.warning("未找到相关结果")
                        continue

                    for i, doc in enumerate(results):
                        logger.info(f"\n结果 {i + 1}:")
                        logger.info(f"文档内容: {doc.page_content[:200]}...")
                        logger.info(f"元数据: {doc.metadata}")

                except Exception as error:
                    logger.error(f"查询处理失败: {str(error)}")
                    continue

    except Exception as error:
        logger.error(f"系统初始化失败: {str(error)}")
    finally:
        logger.info("测试完成")
