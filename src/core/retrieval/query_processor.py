"""使用 langchain 框架处理用户 query"""
import psutil
import os
import sys
from typing import List, Tuple, Any, Set

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from sentence_transformers import CrossEncoder
from langchain.schema import BaseRetriever

# 项目配置
from config.settings import Config
from src.utils.common.logger import logger
from src.database.milvus.operations import VectorOperation
from src.database.mysql.operations import ChunkOperation
from src.database.elasticsearch.operations import ElasticsearchOperation
from src.core.embedding.embedder import init_embedding_model, init_langchain_embeddings
from src.core.rerank.reranker import rerank_results


def log_memory_usage():
    """记录当前内存使用情况"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logger.info(f"内存使用: {memory_info.rss / 1024 / 1024:.2f} MB")


def init_bm25_retriever(vector_op: VectorOperation) -> ElasticsearchOperation:
    """初始化基于 Elasticsearch 的 BM25 检索器
    
    Args:
        vector_op: 向量库操作实例
        
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
    except Exception as e:
        logger.error(f"初始化 ES BM25 检索器失败: {str(e)}")
        raise


def get_segment_text(segment_id: str, chunk_op: ChunkOperation = None) -> str:
    """从 MySQL 获取 segment 原文内容
    Args:
        segment_id: segment ID
        chunk_op: 复用的 ChunkOperation 实例
    Returns:
        str: segment 原文内容
    """
    try:
        if chunk_op is not None:
            chunk_info = chunk_op.select_record(
                fields=["segment_text"],
                conditions={"segment_id": segment_id}
            )
            return chunk_info[0]["segment_text"] if chunk_info else ""
        else:
            with ChunkOperation() as temp_op:
                chunk_info = temp_op.select_record(
                    fields=["segment_text"],
                    conditions={"segment_id": segment_id}
                )
                return chunk_info[0]["segment_text"] if chunk_info else ""
    except Exception as e:
        logger.error(f"获取 segment 原文失败: {str(e)}")
        return ""


def merge_search_results(
    vector_results: List[Tuple[Document, float]],
    bm25_results: List[Tuple[Document, float]]
) -> List[Tuple[Document, float]]:
    """合并向量检索和 BM25 检索结果
    
    Args:
        vector_results: 向量检索结果
        bm25_results: BM25 检索结果
        
    Returns:
        List[Tuple[Document, float]]: 合并后的结果列表
    """
    merged_results = []
    seen_ids: Set[str] = set()
    
    # 添加向量检索结果
    for doc, score in vector_results:
        segment_id = doc.metadata.get("segment_id")
        if segment_id and segment_id not in seen_ids:
            merged_results.append((doc, score))
            seen_ids.add(segment_id)
            
    # 添加 BM25 检索结果
    for doc, score in bm25_results:
        segment_id = doc.metadata.get("segment_id")
        if segment_id and segment_id not in seen_ids:
            merged_results.append((doc, score))
            seen_ids.add(segment_id)
            
    return merged_results


def get_hybrid_search_results(
    vectorstore: Milvus,
    bm25_retriever: ElasticsearchOperation,
    query: str,
    k: int = 5,
    top_k: int = 5,
    chunk_op: ChunkOperation = None  # 新增参数
) -> List[Tuple[Document, float]]:
    """执行混合检索
    
    Args:
        vectorstore: Milvus 向量存储实例
        bm25_retriever: BM25 检索器实例
        query: 查询文本
        k: 初始检索数量
        top_k: 最终返回结果数量
        
    Returns:
        List[Tuple[Document, float]]: 检索结果列表
    """
    logger.info(f"开始混合检索,查询: {query}, k: {k}, top_k: {top_k}")
    
    try:
        # 1. 向量检索
        vector_results = []
        try:
            # 执行向量检索
            logger.info("开始执行向量检索...")
            raw_results = vectorstore.similarity_search_with_score(
                query=query,
                k=k
            )
            logger.info(f"向量检索原始结果数量: {len(raw_results)}")
            
            # 处理检索结果
            for doc, score in raw_results:
                # 获取segment_id
                segment_id = doc.metadata.get("segment_id")
                if not segment_id:
                    logger.warning(f"向量检索结果缺少segment_id: {doc.metadata}")
                    continue
                    
                # 从MySQL获取原文
                original_text = get_segment_text(segment_id, chunk_op=chunk_op)
                if not original_text:
                    logger.warning(f"无法获取segment_id {segment_id} 的原文内容")
                    continue
                    
                # 构建新的Document对象
                new_doc = Document(
                    page_content=original_text,
                    metadata={
                        "segment_id": segment_id,
                        "doc_id": doc.metadata.get("doc_id", ""),
                        "type": doc.metadata.get("type", "text"),
                        "score": score
                    }
                )
                vector_results.append((new_doc, score))
                logger.debug(f"向量检索结果 - segment_id: {segment_id}, score: {score:.4f}")
                
            logger.info(f"向量检索完成,获取到 {len(vector_results)} 条有效结果")
        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            
        # 2. BM25检索
        bm25_results = []
        try:
            logger.info("开始执行BM25检索...")
            es_results = bm25_retriever.search(query, top_k=k)
            logger.info(f"BM25检索原始结果数量: {len(es_results)}")
            
            # 将 ES 结果转换为 Document 格式
            for hit in es_results:
                segment_id = hit["_source"]["segment_id"]
                # 从MySQL获取原文
                original_text = get_segment_text(segment_id, chunk_op=chunk_op)
                if not original_text:
                    logger.warning(f"无法获取segment_id {segment_id} 的原文内容")
                    continue
                    
                doc = Document(
                    page_content=original_text,
                    metadata={
                        "segment_id": segment_id,
                        "doc_id": hit["_source"].get("doc_id", ""),
                        "type": hit["_source"].get("type", "text"),
                        "score": hit["_score"]
                    }
                )
                bm25_results.append((doc, hit["_score"]))
                logger.debug(f"BM25检索结果 - segment_id: {segment_id}, score: {hit['_score']:.4f}")
            logger.info(f"BM25检索完成,获取到 {len(bm25_results)} 条有效结果")
        except Exception as e:
            logger.error(f"BM25检索失败: {str(e)}")
            
        # 3. 合并结果
        merged_results = merge_search_results(vector_results, bm25_results)
        logger.info(f"合并结果完成,共 {len(merged_results)} 条")
        
        # 4. 重排序
        reranked_results = rerank_results(query, merged_results, top_k=top_k)
        logger.info(f"重排序完成,返回 {len(reranked_results)} 条结果")
        
        return reranked_results
        
    except Exception as e:
        logger.error(f"混合检索失败: {str(e)}")
        return []


class CustomRetriever(BaseRetriever):
    """混合检索器，结合向量检索和 ES BM25 检索"""
    
    def __init__(self, vectorstore: Milvus, es_retriever: ElasticsearchOperation):
        """初始化混合检索器
        
        Args:
            vectorstore: Milvus 向量存储实例
            es_retriever: ES 检索器实例
        """
        super().__init__()
        self._vectorstore = vectorstore
        self._es_retriever = es_retriever

    @property
    def vectorstore(self) -> Milvus:
        return self._vectorstore

    @property
    def es_retriever(self) -> ElasticsearchOperation:
        return self._es_retriever

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """获取相关文档
        
        Args:
            query: 用户查询
            
        Returns:
            List[Document]: 相关文档列表
        """
        try:
            # 使用混合检索获取结果
            results = get_hybrid_search_results(
                vectorstore=self.vectorstore,
                bm25_retriever=self.es_retriever,
                query=query,
                k=5,
                top_k=5
            )
            
            # 提取文档列表
            return [doc for doc, _ in results]
            
        except Exception as e:
            logger.error(f"混合检索失败: {str(e)}")
            return []


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
        
        # 测试场景列表
        test_queries = [
            "执行、 落地、管理工作",  # 简单查询
            "",  # 空查询
            "延迟通报",  # 特殊字符
        ]
        # 初始化 BM25 检索器
        bm25_retriever = init_bm25_retriever(vector_op)
        
        # 使用 with 语句管理 ChunkOperation 生命周期
        with ChunkOperation() as chunk_op:
            # 执行测试
            for query in test_queries:
                logger.info(f"\n{'='*50}")
                logger.info(f"测试查询: {query}")
                try:
                    results = get_hybrid_search_results(
                        vectorstore=vectorstore,
                        bm25_retriever=bm25_retriever,
                        query=query,
                        k=5,
                        top_k=5,
                        chunk_op=chunk_op  # 传递实例
                    )
                    
                    # 打印结果
                    if not results:
                        logger.warning("未找到相关结果")
                        continue
                        
                    for i, (doc, score) in enumerate(results):
                        logger.info(f"\n结果 {i + 1}:")
                        logger.info(f"相似度分数: {score:.4f}")
                        logger.info(f"文档内容: {doc.page_content[:200]}...")
                        logger.info(f"元数据: {doc.metadata}")
                        
                except Exception as e:
                    logger.error(f"查询处理失败: {str(e)}")
                    continue
                    
    except Exception as e:
        logger.error(f"系统初始化失败: {str(e)}")
    finally:
        logger.info("测试完成")
