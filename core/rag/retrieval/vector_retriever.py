"""向量检索模块"""
from collections import OrderedDict
from langchain_milvus import Milvus
from utils.common.logger import logger


class VectorRetriever:
    """向量检索器类"""

    def __init__(self, vectorstore: Milvus):
        """初始化向量检索器
        
        Args:
            vectorstore: Milvus 向量存储实例
        """
        self._vectorstore = vectorstore

    def search(self, query: str, permission_ids: str = None, k: int = 5) -> dict[str, float]:
        """执行 milvus 向量检索
        
        Args:
            query: 查询文本
            permission_ids: 权限ID
            k: 检索数量

        Returns:
            dict[str, float]: 检索结果字典(seg_id, score)
        """
        logger.info(f"开始向量检索,查询: {query}, 权限ID: {permission_ids}, k: {k}")
        vector_results = OrderedDict()  # 使用OrderedDict保持顺序
        seen_parent_ids = set()  # 用于记录已处理过的父片段ID

        try:
            # 不带权限过滤的检索
            search_params = {
                "search_type": "similarity",
                "k": k
            }

            raw_result = self._vectorstore.similarity_search_with_score(
                query=query,
                params=search_params,
            )
            logger.info("=== Milvus 向量检索结果 ===")
            for doc, score in raw_result:
                logger.info(f"文档ID: {doc.metadata.get('doc_id')}, "
                            f"片段ID: {doc.metadata.get('seg_id')}, "
                            f"权限ID: {doc.metadata.get('permission_ids')}, "
                            f"相似度分数: {score:.4f}")

            # 带权限过滤的检索
            if permission_ids:
                logger.info(f"=== 结果过滤：权限ID={permission_ids} ===")
                try:
                    # 使用Milvus过滤
                    search_params = {
                        "search_type": "similarity",
                        "k": k * 2  # 增加检索数量，确保过滤后有足够的结果
                    }

                    permission_results = self._vectorstore.similarity_search_with_score(
                        query=query,
                        expr=f'permission_ids in ["{permission_ids}", ""]',
                        params=search_params,
                    )

                    for doc, score in permission_results:
                        logger.info(f"文档ID: {doc.metadata.get('doc_id')}, "
                                    f"片段ID: {doc.metadata.get('seg_id')}, "
                                    f"权限ID: {doc.metadata.get('permission_ids')}, "
                                    f"相似度分数: {score:.4f}")
                except Exception as e:
                    logger.error(f"权限过滤失败: {str(e)}")
                    # 如果权限过滤失败，返回空结果
                    permission_results = []
            else:
                # 如果没有指定权限ID，使用原始结果
                permission_results = raw_result

            # 将结果转换为字典格式
            for doc, score in permission_results:
                seg_id = doc.metadata.get("seg_id")  # 片段ID
                doc_id = doc.metadata.get("doc_id")  # 文档ID，用来检索权限
                logger.debug(f"向量检索结果 - seg_id: {seg_id}, doc_id: {doc_id}, score: {score:.4f}")
                if not seg_id:
                    logger.warning(f"向量检索结果缺少seg_id: {doc.metadata}")
                    continue
                # 添加子块结果
                vector_results[seg_id] = score
                # 添加父块结果
                seg_parent_id = doc.metadata.get("seg_parent_id", "").strip()
                if seg_parent_id and seg_parent_id not in seen_parent_ids:
                    seen_parent_ids.add(seg_parent_id)
                    logger.debug(f"向量检索结果 - 检测到父片段ID: {seg_parent_id}")
                    vector_results[seg_parent_id] = score * 0.1  # 父块的分数为子块的 10%

            logger.info(f"向量检索完成,获取到 {len(vector_results)} 条有效结果")
            return vector_results

        except Exception as error:
            logger.error(f"向量检索失败: {str(error)}")
            return {}  # 返回空字典而不是空列表


if __name__ == '__main__':

    from pymilvus import MilvusClient

    client = MilvusClient(
        host="http://localhost:19530",
        token='root:Milvus',
        db_name='tk_rag'
    )
    results = client.query(collection_name="rag_collection", filter="", output_fields=["seg_id", "vector"], limit=5)
    for r in results:
        print(r["seg_id"], len(r["vector"]), r["vector"][:5])  # 打印前5维
