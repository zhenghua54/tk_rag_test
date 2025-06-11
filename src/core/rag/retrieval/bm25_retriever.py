"""BM25检索模块"""
from typing import List, Tuple
from langchain_core.documents import Document
from src.utils.common.logger import logger
from src.core.rag.retrieval.text_retriever import get_seg_content
from src.database.elasticsearch.operations import ElasticsearchOperation


class BM25Retriever:
    """BM25检索器类"""
    
    def __init__(self, es_retriever: ElasticsearchOperation):
        """初始化BM25检索器
        
        Args:
            es_retriever: ES检索实例
        """
        self._es_retriever = es_retriever

    def search(self, query: str, k: int = 5, chunk_op=None) -> List[Tuple[Document, float]]:
        """执行BM25检索
        
        Args:
            query: 查询文本
            k: 检索数量
            chunk_op: Mysql 的 ChunkOperation实例
            
        Returns:
            List[Tuple[Document, float]]: 检索结果列表
        """
        logger.info(f"开始BM25检索,查询: {query}, k: {k}")
        bm25_results = []
        
        try:
            # 执行BM25检索
            es_results = self._es_retriever.search(query=query, top_k=k)
            logger.info(f"BM25检索原始结果数量: {len(es_results)}")

            # 处理检索结果
            for hit in es_results:
                seg_id = hit["_source"]["seg_id"]
                # 从MySQL获取原文
                original_text = get_seg_content(segment_id=seg_id, chunk_op=chunk_op)
                if not original_text:
                    logger.warning(f"无法获取seg_id {seg_id} 的原文内容")
                    continue

                doc = Document(
                    page_content=original_text,
                    metadata={
                        "seg_id": seg_id,
                        "seg_parent_id": hit["_source"].get("seg_parent_id"),
                        "doc_id": hit["_source"].get("doc_id", ""),
                        "seg_type": hit["_source"].get("seg_type", "text"),
                        "score": hit["_score"]
                    }
                )
                bm25_results.append((doc, hit["_score"]))
                logger.debug(f"BM25检索结果 - seg_id: {seg_id}, score: {hit['_score']:.4f}")
                
            logger.info(f"BM25检索完成,获取到 {len(bm25_results)} 条有效结果")
            return bm25_results
            
        except Exception as error:
            logger.error(f"BM25检索失败: {str(error)}")
            return [] 