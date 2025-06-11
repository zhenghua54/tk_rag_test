"""混合检索模块"""
from typing import List, Tuple, Set
from langchain_core.documents import Document
from langchain.schema import BaseRetriever
from src.utils.common.logger import logger
from src.core.rag.retrieval.vector_retriever import VectorRetriever
from src.core.rag.retrieval.bm25_retriever import BM25Retriever
from src.core.rag.reranker import rerank_results


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
        seg_id = doc.metadata.get("seg_id")
        if seg_id and seg_id not in seen_ids:
            merged_results.append((doc, score))
            seen_ids.add(seg_id)

    # 添加 BM25 检索结果
    for doc, score in bm25_results:
        seg_id = doc.metadata.get("seg_id")
        if seg_id and seg_id not in seen_ids:
            merged_results.append((doc, score))
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

    def get_relevant_documents(self, query: str, *, k: int = 5, top_k: int = 5, chunk_op=None) -> List[Document]:
        """获取相关文档
        
        Args:
            query: 用户查询
            k: 初始检索数量
            top_k: 最终返回结果数量
            chunk_op: ChunkOperation实例
            
        Returns:
            List[Document]: 相关文档列表
        """
        try:
            # 1. 向量检索
            vector_results = self._vector_retriever.search(
                query=query,
                k=k,
                chunk_op=chunk_op
            )

            # 2. BM25检索
            bm25_results = self._bm25_retriever.search(
                query=query,
                k=k,
                chunk_op=chunk_op
            )

            # 3. 合并结果
            merged_results = merge_search_results(vector_results, bm25_results)
            logger.debug(f"合并结果完成,共 {len(merged_results)} 条")

            # 4. 重排序
            reranked_results = rerank_results(query=query, results=merged_results, top_k=top_k)
            logger.debug(f"重排序完成,返回 {len(reranked_results)} 条结果")

            # 提取文档列表
            return [doc for doc, _ in reranked_results]

        except Exception as error:
            logger.error(f"混合检索失败: {str(error)}")
            return [] 