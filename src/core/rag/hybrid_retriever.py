"""混合检索模块"""
from typing import List, Any, Dict, OrderedDict
from langchain_core.documents import Document
from langchain.schema import BaseRetriever
from src.utils.common.logger import logger
from src.core.rag.retrieval.text_retriever import get_segment_contents
from src.core.rag.retrieval.vector_retriever import VectorRetriever
from src.core.rag.retrieval.bm25_retriever import BM25Retriever
from src.core.rag.reranker import rerank_results


# 处理权限ID


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

    # merged_results = []
    # seen_ids: Set[str] = set()
    # seen_parent_ids: Set[str] = set()

    # # 收集所有文档和权限ID
    # doc_ids = set()
    # permission_ids = set()

    # # 添加向量检索结果
    # for doc, score in vector_results:
    #     seg_id = doc.metadata.get("seg_id")

    #     # 如果是新的seg_id，则添加到结果中
    #     if seg_id and seg_id not in seen_ids:
    #         merged_results.append((doc, score))
    #         seen_ids.add(seg_id)

    #         # 记录文档ID和权限ID
    #         if doc.metadata.get("doc_id"):
    #             doc_ids.add(doc.metadata.get("doc_id"))
    #         if doc.metadata.get("permission_ids"):
    #             permission_ids.update(doc.metadata.get("permission_ids"))

    #     # 处理父片段
    #     seg_parent_id = doc.metadata.get("seg_parent_id", "").strip()
    #     if seg_parent_id and seg_parent_id not in seen_parent_ids:
    #         seen_parent_ids.add(seg_parent_id)
    #         logger.debug(f"添加父片段ID: {seg_parent_id}到结果集")

    #         # 获取父片段详细信息
    #         parent_info = get_parent_segment_info(parent_id=seg_parent_id, chunk_op=None)
    #         if parent_info["doc_id"]:
    #             doc_ids.add(parent_info["doc_id"])
    #         if parent_info["permission_ids"]:
    #             permission_ids.update(parent_info["permission_ids"])

    # # 添加 BM25 检索结果
    # for doc, score in bm25_results:
    #     seg_id = doc.metadata.get("seg_id")

    #     # 如果是新的seg_id，则添加到结果中
    #     if seg_id and seg_id not in seen_ids:
    #         merged_results.append((doc, score))
    #         seen_ids.add(seg_id)

    #         # 记录文档ID和权限ID
    #         if doc.metadata.get("doc_id"):
    #             doc_ids.add(doc.metadata.get("doc_id"))
    #         if doc.metadata.get("permission_ids"):
    #             permission_ids.update(doc.metadata.get("permission_ids"))

    #     # 处理父片段
    #     seg_parent_id = doc.metadata.get("seg_parent_id", "").strip()
    #     if seg_parent_id and seg_parent_id not in seen_parent_ids:
    #         seen_parent_ids.add(seg_parent_id)
    #         logger.debug(f"添加父片段ID: {seg_parent_id}到结果集")

    #         # 获取父片段详细信息
    #         parent_info = get_parent_segment_info(parent_id=seg_parent_id, chunk_op=None)
    #         if parent_info["doc_id"]:
    #             doc_ids.add(parent_info["doc_id"])
    #         if parent_info["permission_ids"]:
    #             permission_ids.update(parent_info["permission_ids"])

    # logger.info(f"合并后共有 {len(merged_results)} 条结果, {len(doc_ids)} 个文档, {len(permission_ids)} 个权限ID")
    # return merged_results


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

    def get_relevant_documents(self, query: str, *, permission_ids: str = None, k: int = 20, top_k: int = 5,
                               chunk_op=None) -> List[Document]:
        """获取相关文档
        
        Args:
            query: 用户查询
            permission_ids: 权限ID列表
            k: 初始检索数量
            top_k: 最终返回结果数量
            chunk_op: ChunkOperation实例
            
        Returns:
            List[Document]: 相关文档列表
        """
        try:
            # 向量检索
            vector_results: dict[str, float] = self._vector_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
                chunk_op=chunk_op
            )

            # BM25检索
            bm25_results: dict[str, float] = self._bm25_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
                chunk_op=chunk_op
            )

            # 合并结果
            merged_results: dict[str, float] = merge_search_results(vector_results, bm25_results)
            logger.debug(f"[混合检索] 合并结果完成,共 {len(merged_results)} 条")

            # 从 mysql 获取所需的原文内容
            seg_ids = list(merged_results.keys())
            mysql_records: List[Dict[str, Any]] = get_segment_contents(seg_ids=seg_ids, chunk_op=chunk_op)
            
            # 再次对mysql获取到的原文内容进行过滤，避免遗漏
            rerank_input = []
            for record in mysql_records:
                
                # 处理记录中的权限 ID
                if permission_ids and record.get("permission_ids") == permission_ids:
                    continue
                
                doc = Document(
                    page_content=record.get("seg_content", ""),
                    metadata={
                        "seg_id": record.get("seg_id"),
                        "seg_type": record.get("seg_type"),
                        "seg_image_path": record.get("seg_image_path"),
                        "seg_caption": record.get("seg_caption"),
                        "seg_footnote": record.get("seg_footnote"),
                        "seg_page_idx": record.get("seg_page_idx"),
                        "doc_id": record.get("doc_id"),
                        "doc_http_url": record.get("doc_http_url"),
                        "doc_created_at": record.get("doc_created_at"),
                        "doc_updated_at": record.get("doc_updated_at"),
                    }
                )
                rerank_input.append(doc)

            logger.debug(f"[混合检索] rerank_input 共有 {len(rerank_input)} 条结果")
            
            # 重排序
            reranked_results = rerank_results(query=query, merged_results=rerank_input, top_k=top_k)
            logger.debug(f"[重排序] 重排完成, 返回 {len(reranked_results)} 条结果")

            # 提取文档列表
            return [doc for doc, _ in reranked_results]

        except Exception as error:
            logger.error(f"混合检索失败: {str(error)}")
            return []
