"""BM25检索模块"""
from collections import OrderedDict
from utils.common.logger import logger
from databases.elasticsearch.operations import ElasticsearchOperation


class BM25Retriever:
    """BM25检索器类"""

    def __init__(self, es_retriever: ElasticsearchOperation):
        """初始化BM25检索器
        
        Args:
            es_retriever: ES检索实例
        """
        self._es_retriever = es_retriever

    def search(self, query: str, permission_ids: str = None, k: int = 20) -> dict[str, float]:
        """执行BM25检索
        
        Args:
            query: 查询文本
            permission_ids: 权限ID
            k: 检索数量

        Returns:
            dict[str, float]: 检索结果字典(seg_id, score)
        """
        logger.info(f"开始BM25检索,查询: {query}, 权限ID: {permission_ids}, k: {k}")
        bm25_results = OrderedDict()
        seen_parent_ids = set()

        try:
            raw_result = self._es_retriever.search(query=query, top_k=k)
            for hit in raw_result:
                logger.info(f"文档ID: {hit['_source'].get('doc_id')}, "
                            f"片段ID: {hit['_source'].get('seg_id')}, "
                            f"BM25分数: {hit['_score']:.4f}")

            # 处理检索结果
            es_results = raw_result

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
            return {}  # 返回空字典而不是空列表
