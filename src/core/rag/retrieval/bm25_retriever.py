"""BM25检索模块"""
from typing import List, Tuple
from collections import OrderedDict
from langchain_core.documents import Document
from src.utils.common.logger import logger
from src.core.rag.retrieval.text_retriever import get_segment_contents
from src.database.elasticsearch.operations import ElasticsearchOperation


class BM25Retriever:
    """BM25检索器类"""
    
    def __init__(self, es_retriever: ElasticsearchOperation):
        """初始化BM25检索器
        
        Args:
            es_retriever: ES检索实例
        """
        self._es_retriever = es_retriever

    def search(self, query: str, permission_ids: str = None, k: int = 20, chunk_op=None) -> dict[str, float]:
        """执行BM25检索
        
        Args:
            query: 查询文本
            permission_ids: 权限ID
            k: 检索数量
            chunk_op: Mysql 的 ChunkOperation实例
            
        Returns:
            dict[str, float]: 检索结果字典(seg_id, score)
        """
        logger.info(f"开始BM25检索,查询: {query}, 权限ID: {permission_ids}, k: {k}")
        bm25_results = OrderedDict()
        seen_parent_ids = set()
        
        try:
            # 不带权限过滤的检索    
            raw_result = self._es_retriever.search(query=query, top_k=k)
            logger.info("=== 不带权限过滤的检索结果 ===")
            for hit in raw_result:
                logger.info(f"文档ID: {hit['_source'].get('doc_id')}, "
                          f"片段ID: {hit['_source'].get('seg_id')}, "
                          f"权限ID: {hit['_source'].get('permission_ids')}, "
                          f"BM25分数: {hit['_score']:.4f}")
            
            # 处理检索结果
            es_results = raw_result
            # 由于ES检索器不支持权限过滤，我们在这里手动过滤
            if permission_ids:
                filtered_results = []
                for hit in es_results:
                    hit_permission_id = hit['_source'].get('permission_ids')
                    if hit_permission_id == permission_ids:
                        filtered_results.append(hit)
                es_results = filtered_results
                logger.info(f"=== 权限过滤后的结果数量: {len(es_results)} ===")
            
            # 处理检索结果
            for hit in es_results:
                seg_id = hit["_source"]["seg_id"]
                logger.debug(f"BM25检索结果 - seg_id: {seg_id}, score: {hit['_score']:.4f}")
                bm25_results[seg_id] = hit["_score"]
                
                # 处理父片段 - 如果存在seg_parent_id
                seg_parent_id = hit["_source"].get("seg_parent_id", "").strip()
                if seg_parent_id and seg_parent_id not in seen_parent_ids:
                    logger.debug(f"BM25检索结果 - 检测到父片段ID: {seg_parent_id}")
                    seen_parent_ids.add(seg_parent_id)
                    bm25_results[seg_parent_id] = hit["_score"] * 0.1  # 父块的分数为子块的 10%
                
            logger.info(f"BM25检索完成,获取到 {len(bm25_results)} 条有效结果")
            return bm25_results
            
        except Exception as error:
            logger.error(f"BM25检索失败: {str(error)}")
            return {} # 返回空字典而不是空列表 