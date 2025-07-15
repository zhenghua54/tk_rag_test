# """向量检索模块"""
#
# from collections import OrderedDict
# from typing import Any
#
# from databases.milvus.flat_collection import FlatCollectionManager
# from utils.llm_utils import EmbeddingManager
# from utils.log_utils import logger
#
#
# class VectorRetriever:
#     """向量检索器类"""
#
#     def __init__(self, flat_manager: FlatCollectionManager):
#         """初始化向量检索器
#
#         Args:
#             flat_manager: FLAT Collection 管理器实例
#         """
#         self._flat_manager = flat_manager
#         self._embedding_manager = EmbeddingManager()
#
#     def search(self, query: str, doc_ids: list[str], batch_size: int = 1000) -> dict[str, float]:
#         """执行 milvus 向量检索
#
#         Args:
#             query: 查询文本
#             doc_ids: 用户能查看的文档 ID 列表
#             batch_size: 单批次最大查询数量(默认 1000)
#
#         Returns:
#             dict[str, float]: 检索结果字典(seg_id, score)
#         """
#         logger.debug(f"[向量检索] 开始, 查询长度={len(query)}, k={k}")
#         vector_results = OrderedDict()  # 使用OrderedDict保持顺序
#         seen_parent_ids = set()  # 用于记录已处理过的父片段ID
#
#         try:
#             # 生成查询向量
#             logger.debug("[向量检索] 生成查询向量")
#             query_vector = self._embedding_manager.embed_text(query)
#
#             # 调用数据库层执行向量搜索
#             logger.debug("[向量检索] 执行数据库向量检索")
#
#             # 分批次检索
#             all_results = []
#             for i in range(0, len(doc_ids), batch_size):
#                 # 获取批次doc_id
#                 batch_ids = doc_ids[i : i + batch_size]
#                 # 获取批次检索结果
#                 hits: list[dict[str, Any]] = self._flat_manager.client.vector_search_iterator(
#                     data=[query_vector],
#                     batch_size=1000,
#                     doc_ids=doc_ids,
#                     top_k=100,
#                 )
#                 all_results.append(hits)
#
#             logger.debug("=== Milvus 向量检索结果 ===")
#             for hit in hits:
#                 seg_id = hit.get("seg_id")
#                 doc_id = hit.get("doc_id")
#                 score = hit.get("score", 0.0)  # milvus 分数
#                 permission_ids_result = hit.get("permission_ids")
#
#                 logger.debug(
#                     f"文档ID: {doc_id}, 片段ID: {seg_id}, 权限ID: {permission_ids_result}, 相似度分数: {score:.4f}"
#                 )
#
#                 if not seg_id:
#                     logger.warning(f"[向量检索] 结果缺少 seg_id: {hit}")
#                     continue
#
#                 # 添加子块结果
#                 vector_results[seg_id] = score
#
#                 # 添加父块结果
#                 seg_parent_id = hit.get("seg_parent_id", "").strip()
#                 if seg_parent_id and seg_parent_id not in seen_parent_ids:
#                     seen_parent_ids.add(seg_parent_id)
#                     logger.debug(f"向量检索结果 - 检测到父片段ID: {seg_parent_id}")
#                     vector_results[seg_parent_id] = score * 0.1  # 父块的分数为子块的 10%
#
#             logger.info(f"向量检索完成,获取到 {len(vector_results)} 条有效结果")
#             return vector_results
#
#         except Exception as e:
#             logger.error(f"向量检索失败: {str(e)}")
#             return {}  # 返回空字典而不是空列表
#
#
# if __name__ == "__main__":
#     from pymilvus import MilvusClient
#
#     client = MilvusClient(host="http://192.168.5.199:19530", token="root:Milvus", db_name="tk_rag_dev")
#     results = client.query(collection_name="rag_flat", filter="", output_fields=["seg_id", "seg_dense_vector"], limit=5)
#     for r in results:
#         print(r["seg_id"], len(r["vector"]), r["vector"][:5])  # 打印前5维
