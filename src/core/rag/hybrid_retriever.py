"""混合检索模块"""
from typing import List, Any, Dict, OrderedDict

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain.schema import BaseRetriever
from langchain_milvus import Milvus

from config.settings import Config
from src.database.elasticsearch.operations import ElasticsearchOperation
from src.utils.common.logger import logger
from src.core.rag.retrieval.text_retriever import get_segment_contents
from src.core.rag.retrieval.vector_retriever import VectorRetriever
from src.core.rag.retrieval.bm25_retriever import BM25Retriever
from src.utils.llm_utils import rerank_manager


def init_retrievers():
    """初始化检索器
    
    Returns:
        tuple: (vector_retriever, bm25_retriever)
    """
    logger.info("开始初始化检索系统...")

    # 初始化 ES 检索器
    logger.info("初始化 ES 检索器...")
    es_op = ElasticsearchOperation()

    # 初始化 BM25 检索器
    logger.info("初始化 BM25 检索器...")
    bm25_retriever = BM25Retriever(es_retriever=es_op)

    # 初始化 embeddings
    logger.info("初始化 embeddings 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.MODEL_PATHS["embedding"],
        model_kwargs={'device': Config.DEVICE}
    )

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
        text_field="seg_content"
    )

    logger.info("检索系统初始化完成")

    # 返回向量检索器实例
    return VectorRetriever(vectorstore), bm25_retriever


def merge_search_results(
        vector_results: dict[str, float],
        bm25_results: dict[str, float]
) -> dict[str, float]:
    """合并向量检索和 BM25 检索结果
    
    Args:
        vector_results: 向量检索结果(seg_id, score)
        bm25_results: BM25 检索结果
        
    Returns:
        dict[str, float]: 合并后的结果字典(seg_id, score)
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


class HybridRetriever(BaseRetriever):
    """混合检索器，结合向量检索和 ES BM25 检索"""

    def __init__(self, vector_retriever: VectorRetriever, bm25_retriever: BM25Retriever):
        """初始化混合检索器
        
        Args:
            vector_retriever: 向量检索器实例
            bm25_retriever: BM25检索器实例
        """
        super().__init__()
        self._vector_retriever = vector_retriever
        self._bm25_retriever = bm25_retriever

    def get_relevant_documents(self, query: str, *, callbacks=None, tags=None, metadata=None, **kwargs) -> List[
        Document]:
        """实现 BaseRetriever 的方法

        Args:
            query: 用户查询
            callbacks: 回调函数
            tags: 标签
            metadata: 元数据

        Returns:
            List[Document]: 相关文档列表
        """
        # 从 kwargs 中获取参数，如果没有则使用默认值
        permission_ids = kwargs.get("permission_ids")
        k = kwargs.get("k", 20)
        top_k = kwargs.get("top_k", 10)
        chunk_op = kwargs.get("chunk_op")

        return self.search_documents(query, permission_ids=permission_ids, k=k, top_k=top_k, chunk_op=chunk_op)

    def search_documents(self, query: str, *, permission_ids: str = None, k: int = 20, top_k: int = 5,
                         chunk_op=None) -> List[Document]:
        """自定义搜索文档方法

        Args:
            query: 用户查询
            permission_ids: 权限ID列表
            k: 初始检索数量
            top_k: 最终返回结果数量
            chunk_op: ChunkOperation实例

        Returns:
            List[Document]: 相关文档列表
        """
        print(top_k)
        try:
            logger.info(f"[混合检索] 开始检索,查询: {query}, 权限ID: {permission_ids}, k: {k}, top_k: {top_k}")

            # 向量检索
            vector_results: dict[str, float] = self._vector_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
            )

            # BM25检索
            bm25_results: dict[str, float] = self._bm25_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
            )

            # 合并结果
            merged_results: dict[str, float] = merge_search_results(vector_results, bm25_results)
            logger.info(f"[混合检索] 合并结果完成,共 {len(merged_results)} 条")

            # 如果没有检索到结果，直接返回空列表
            if not merged_results:
                logger.info(f"[混合检索] 没有检索到结果，返回空列表")
                return []

            # 从 mysql 获取所需的原文内容
            seg_ids = list(merged_results.keys())
            logger.info(f"[混合检索] 从MySQL获取原文内容,seg_ids数量: {len(seg_ids)}, 权限ID: {permission_ids}")
            mysql_records: List[Dict[str, Any]] = get_segment_contents(
                seg_ids=seg_ids,
                permission_ids=permission_ids,  # 确保传递权限ID
                chunk_op=chunk_op
            )
            logger.info(f"[混合检索] 从MySQL获取到 {len(mysql_records)} 条原文记录")

            # 再次对mysql获取到的原文内容进行过滤，避免遗漏

            rerank_input = []
            filtered_count = 0
            for record in mysql_records:
                # 处理记录中的权限 ID
                if permission_ids:
                    # 获取记录中的权限ID
                    record_permission_ids = record.get("permission_ids", "")
                    # logger.info(f"权限检查 - 记录权限: {record_permission_ids}, 用户权限: {permission_ids}")

                    # 如果记录有权限ID且与用户权限不匹配，则跳过
                    if record_permission_ids and str(record_permission_ids) != str(permission_ids):
                        logger.info(
                            f"权限过滤: 跳过文档 {record.get('seg_id')}, 权限不匹配 (需要: {permission_ids}, 实际: {record_permission_ids})")
                        filtered_count += 1
                        continue

                # 获取当前片段在merged_results中的得分
                seg_id = record.get("seg_id")
                score = merged_results.get(seg_id)

                doc = Document(
                    page_content=record.get("seg_content", ""),
                    metadata={
                        "seg_id": seg_id,
                        "seg_type": record.get("seg_type"),
                        "seg_image_path": record.get("seg_image_path"),
                        "seg_caption": record.get("seg_caption"),
                        "seg_footnote": record.get("seg_footnote"),
                        "seg_page_idx": record.get("seg_page_idx"),
                        "doc_id": record.get("doc_id"),
                        "doc_http_url": record.get("doc_http_url"),
                        "doc_images_path": record.get("doc_images_path", ""),
                        "doc_created_at": record.get("doc_created_at"),
                        "doc_updated_at": record.get("doc_updated_at"),
                        "score": score
                    }
                )
                rerank_input.append(doc)

            logger.info(f"[混合检索] 权限过滤后剩余 {len(rerank_input)} 条结果 (过滤掉 {filtered_count} 条)")

            # 重排序
            reranked_result = []
            if rerank_input:
                scores = rerank_manager.rerank(
                    query=query,
                    passages=[doc.page_content for doc in rerank_input]
                )
                # 将分数与文档配对
                reranked_result = [
                    (doc, score) for doc, score in zip(rerank_input, scores)
                ]

                # 按分数排序并提取前 tok_k 个
                reranked_result.sort(key=lambda x: x[1], reverse=True)
                reranked_result = reranked_result[:top_k]

            logger.info(f"[重排序] 重排完成, 返回 {len(reranked_result)} 条结果")

            # 提取文档列表
            return [doc for doc, _ in reranked_result]

        except Exception as error:
            logger.error(f"[混合检索] 检索失败: {str(error)}")
            return []


vector_retriever, bm25_retriever = init_retrievers()
hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)

if __name__ == '__main__':
    query = "发行人"
    vector_retriever, bm25_retriever = init_retrievers()
    hyper_ob = HybridRetriever(vector_retriever, bm25_retriever)
    result = hyper_ob.get_relevant_documents(query, permission_ids="1")
    print(result)
