# """Milvus操作类 - 不同集合继承自基础类，提供特定业务操作"""

# import json
# from typing import List, Dict, Any, Optional, Union
# from datetime import datetime
# from pymilvus import CollectionSchema, FieldSchema, DataType, Function, FunctionType

# from tests.base import get_milvus_base
# from config.global_config import GlobalConfig
# from utils.log_utils import logger


# class MilvusCollectionBase:
#     """Milvus集合操作基类 - 所有集合操作类都继承自此类"""

#     def __init__(self, collection_name: str):
#         """初始化集合操作基类
        
#         Args:
#             collection_name: 集合名称
#         """
#         self.milvus_base = get_milvus_base()
#         self.client = self.milvus_base.get_client()
#         self.collection_name = collection_name
#         self._collection = None

#     @property
#     def collection(self):
#         """获取集合实例 - 懒加载"""
#         if self._collection is None:
#             self._collection = self.milvus_base.get_collection(self.collection_name)
#         return self._collection

#     def exists(self) -> bool:
#         """检查集合是否存在"""
#         return self.milvus_base.has_collection(self.collection_name)

#     def load(self) -> bool:
#         """加载集合到内存"""
#         try:
#             self.collection.load()
#             logger.info(f"集合 {self.collection_name} 加载成功")
#             return True
#         except Exception as e:
#             logger.error(f"加载集合失败: {str(e)}")
#             return False

#     def release(self) -> bool:
#         """释放集合内存"""
#         try:
#             self.collection.release()
#             logger.info(f"集合 {self.collection_name} 释放成功")
#             return True
#         except Exception as e:
#             logger.error(f"释放集合失败: {str(e)}")
#             return False

#     def get_statistics(self) -> Dict[str, Any]:
#         """获取集合统计信息"""
#         try:
#             stats = self.collection.get_statistics()
#             return {
#                 "collection_name": self.collection_name,
#                 "entity_count": stats.get("row_count", 0),
#                 "indexes": self.milvus_base.list_indexes(self.collection_name)
#             }
#         except Exception as e:
#             logger.error(f"获取集合统计信息失败: {str(e)}")
#             return {}

#     # ==================== 简化的CRUD操作 ====================

#     def insert(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
#         """插入数据"""
#         return self.milvus_base.insert(self.collection_name, data)

#     def delete(self, ids: Union[str, List[str]]) -> Dict[str, Any]:
#         """删除数据"""
#         return self.milvus_base.delete(self.collection_name, ids)

#     def upsert(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
#         """更新或插入数据"""
#         return self.milvus_base.upsert(self.collection_name, data)

#     def get(self, ids: Union[str, List[str]], output_fields: List[str] = None) -> List[Dict[str, Any]]:
#         """根据ID获取数据"""
#         return self.milvus_base.get(self.collection_name, ids, output_fields)

#     def query(self, filter_expr: str = "", output_fields: List[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
#         """查询数据"""
#         return self.milvus_base.query(self.collection_name, filter_expr, output_fields, limit)

#     def search(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
#         """搜索数据"""
#         return self.milvus_base.search(self.collection_name, search_params)

#     def flush(self) -> None:
#         """执行flush操作"""
#         self.milvus_base.flush(self.collection_name)


# class MilvusHybridCollection(MilvusCollectionBase):
#     """混合检索集合"rag_collection_v2"的操作类"""

#     def __init__(self):
#         """初始化混合检索集合"""
#         super().__init__("rag_collection_v2")

#     def create_collection(self) -> bool:
#         """创建混合检索集合"""
#         try:
#             if self.exists():
#                 logger.warning(f"集合 {self.collection_name} 已存在")
#                 return True

#             # 加载schema配置
#             schema_config = self._load_schema()

#             # 创建字段
#             fields = []
#             for field_config in schema_config["fields"]:
#                 field = FieldSchema(
#                     name=field_config["name"],
#                     dtype=getattr(DataType, field_config["type"]),
#                     description=field_config.get("description", ""),
#                     is_primary=field_config.get("is_primary", False),
#                     **{k: v for k, v in field_config.items()
#                        if k not in ["name", "type", "description", "is_primary"]}
#                 )
#                 fields.append(field)

#             # 创建schema
#             schema = CollectionSchema(
#                 fields=fields,
#                 description=schema_config.get("description", ""),
#                 enable_dynamic_field=True
#             )

#             # 创建BM25函数
#             function = None
#             if "functions" in schema_config:
#                 function = self._create_bm25_function(schema_config["functions"])

#             # 使用官方方法创建集合（包含函数）
#             if function:
#                 success = self.milvus_base.create_collection_with_function(
#                     self.collection_name,
#                     schema,
#                     function
#                 )
#             else:
#                 # 如果没有函数，使用普通方法创建集合
#                 success = self.milvus_base.create_collection(self.collection_name, schema)

#             return success

#         except Exception as e:
#             logger.error(f"创建混合检索集合失败: {str(e)}")
#             return False

#     @staticmethod
#     def _create_bm25_function(functions_config: List[Dict[str, Any]]) -> Optional[Function]:
#         """创建BM25函数对象
        
#         Args:
#             functions_config: 函数配置列表
            
#         Returns:
#             Optional[Function]: BM25函数对象，如果没有配置则返回None
#         """
#         try:
#             for func_config in functions_config:
#                 if func_config["function_type"] == "BM25":
#                     func = Function(
#                         name=func_config["name"],
#                         input_field_names=func_config["input_field_names"],
#                         output_field_names=func_config["output_field_names"],
#                         function_type=FunctionType.BM25
#                     )
#                     logger.info(f"BM25函数 {func_config['name']} 创建成功")
#                     return func

#             logger.warning("未找到BM25函数配置")
#             return None

#         except Exception as e:
#             logger.error(f"创建BM25函数失败: {str(e)}")
#             return None

#     @staticmethod
#     def _load_schema() -> Dict[str, Any]:
#         """加载schema配置"""
#         schema_path = GlobalConfig.PATHS.get("milvus_hybrid_schema_path")
#         with open(schema_path, 'r', encoding='utf-8') as f:
#             return json.load(f)

#     def create_indexes(self) -> bool:
#         """创建索引"""
#         try:
#             # 密集向量索引
#             dense_index_params = self.client.prepare_index_params()
#             dense_index_params.add_index(
#                 field_name="seg_dense_vector",
#                 index_type="IVF_FLAT",
#                 metric_type="IP",
#                 params={"nlist": 1024}
#             )

#             success = self.milvus_base.create_index(self.collection_name, dense_index_params)
#             if not success:
#                 return False

#             # 稀疏向量索引
#             sparse_index_params = self.client.prepare_index_params()
#             sparse_index_params.add_index(
#                 field_name="seg_sparse_vector",
#                 index_type="SPARSE_INVERTED_INDEX",
#                 metric_type="IP"
#             )

#             success = self.milvus_base.create_index(self.collection_name, sparse_index_params)
#             return success

#         except Exception as e:
#             logger.error(f"创建索引失败: {str(e)}")
#             return False

#     def insert_data(self, data: List[Dict[str, Any]]) -> List[str]:
#         """插入数据"""
#         try:
#             # 验证数据格式
#             self._validate_hybrid_data(data)

#             # 使用基类的insert方法
#             result = self.insert(data)
#             return result.get('ids', [])

#         except Exception as e:
#             logger.error(f"插入数据失败: {str(e)}")
#             raise

#     @staticmethod
#     def _validate_hybrid_data(data: List[Dict[str, Any]]) -> None:
#         """验证集合字段完整性"""
#         required_fields = [
#             "doc_id", "seg_id", "seg_parent_id", "seg_dense_vector",
#             "seg_content", "seg_type", "seg_page_idx", "permissions",
#             "create_time", "update_time"
#         ]

#         for idx, item in enumerate(data):
#             # 验证必需字段
#             missing_fields = [field for field in required_fields if field not in item]
#             if missing_fields:
#                 raise ValueError(f"第 {idx + 1} 条数据缺少必需字段: {missing_fields}")

#             # 验证向量维度
#             if not isinstance(item["seg_dense_vector"], list) or len(item["seg_dense_vector"]) != 1024:
#                 raise ValueError(f"第 {idx + 1} 条数据的seg_dense_vector字段必须是1024维的浮点数列表")

#     # ==================== 单一检索操作 ====================
#     def dense_search(self, query_vector: List[float], top_k: int = 20, filter_expr: str = "",
#                      output_fields: List[str] = None) -> List[Dict[str, Any]]:
#         """密集向量检索
        
#         Args:
#             query_vector: 查询向量, 1024维的浮点数列表
#             top_k: 返回结果数量, 默认20
#             filter_expr: 过滤条件, 默认空字符串
#             output_fields: 返回字段, 默认空列表
#         Returns:
#             List[Dict[str, Any]]: 检索结果
#         """
#         try:
#             if output_fields is None:
#                 output_fields = ["*"]

#             # 构建搜索参数
#             search_params = {
#                 "data": [query_vector],
#                 "anns_field": "seg_dense_vector",
#                 "params": {"nprobe": 10},  # 在IVF索引中搜索10个聚类, 平衡精度和速度
#                 "limit": top_k,
#                 "output_fields": output_fields,
#                 "filter": filter_expr
#             }
#             results = self.search(search_params)
#             return self._process_search_results(results[0], "dense") if results else []
#         except Exception as e:
#             logger.error(f"密集向量检索失败: {str(e)}")
#             return []

#     def full_text_search(self, query: str, top_k: int = 20, filter_expr: str = "", output_fields: List[str] = None) -> \
#             List[Dict[str, Any]]:
#         """全文检索 - 使用BM25算法在文本上搜索
        
#         Args:
#             query: 查询文本
#             top_k: 返回结果数量, 默认20
#             filter_expr: 过滤条件, 默认空字符串
#             output_fields: 返回字段, 默认空列表
#         Returns:
#             List[Dict[str, Any]]: 检索结果
#         """
#         try:
#             if output_fields is None:
#                 output_fields = ["*"]

#             # 构建搜索参数
#             search_params = {
#                 "data": [query],  # 原始文本
#                 "anns_field": "seg_sparse_vector",  # 存储BM25生成的稀疏向量的字段
#                 "metric_type": "BM25",
#                 "analyzer_name": "standard",  # 分析器(分词器)
#                 "drop_ratio_search": "0.2",  # 丢弃20%的维度,提高检索速度
#                 "limit": top_k,
#                 "output_fields": output_fields,
#                 "filter": filter_expr
#             }

#             results = self.search(search_params)
#             # 单个查询向量，取第一个结果列表
#             return self._process_search_results(results[0], "full_text") if results else []
#         except Exception as e:
#             logger.error(f"全文检索失败: {str(e)}")
#             return []

#     @staticmethod
#     def _process_search_results(results: List[Dict[str, Any]], search_type: str) -> List[Dict[str, Any]]:
#         """处理搜索结果
        
#         Args:
#             results: 搜索结果
#             search_type: 搜索类型, 可选值: "dense", "sparse", "text"
#         Returns:
#             List[Dict[str, Any]]: 处理后的搜索结果
#         """
#         processed_results = []

#         for result in results:
#             processed_result = {
#                 "doc_id": result.get("doc_id", ""),
#                 "seg_id": result.get("seg_id", ""),
#                 "seg_parent_id": result.get("seg_parent_id", ""),
#                 "seg_content": result.get("seg_content", ""),
#                 "seg_type": result.get("seg_type", ""),
#                 "seg_page_idx": result.get("seg_page_idx", ""),
#                 "permissions": result.get("permissions", ""),
#                 "score": result.get("score", ""),
#                 "search_type": search_type,  # 标记检索类型
#                 "create_time": result.get("create_time", ""),
#                 "update_time": result.get("update_time", "")
#             }
#             processed_results.append(processed_result)

#         return processed_results

#     def delete_by_doc_id(self, doc_id: str) -> int:
#         """根据doc_id删除数据
        
#         Args:
#             doc_id: 文档ID
#         Returns:
#             Dict[str, Any]: 删除结果
#         """
#         try:
#             result = self.delete(doc_id)
#             deleted_count = result.get("delete_count", 0)

#             # 持久化删除
#             self.flush()

#             logger.info(f"删除数据成功, 共 {deleted_count} 条, doc_id={doc_id}")
#             return deleted_count

#         except Exception as e:
#             logger.error(f"删除数据失败: {str(e)}")
#             return 0

#     def upsert_data(self, doc_id: str, data: List[Dict[str, Any]]) -> bool:
#         """插入或更新数据（upsert操作）
        
#         Args:
#             doc_id: 文档ID
#             data: 要插入或更新的数据
#         Returns:
#             bool: 操作是否成功
#         """
#         try:
#             # 为每条数据添加doc_id和更新时间
#             processed_data = []
#             for item in data:
#                 processed_item = item.copy()
#                 processed_item['doc_id'] = doc_id
#                 processed_item['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                 processed_data.append(processed_item)

#             # 使用基类upsert方法
#             self.upsert(processed_data)

#             logger.info(f"数据插入/更新成功, doc_id={doc_id}, 共 {len(data)} 条")
#             return True

#         except Exception as e:
#             logger.error(f"数据插入/更新失败: {str(e)}")
#             return False

#     def get_by_doc_id(self, doc_id: Union[str, List[str]]) -> List[Dict[str, Any]]:
#         """根据doc_id获取数据
        
#         Args:
#             doc_id: 文档ID
#         Returns:
#             Dict[str, Any]: 数据
#         """
#         if isinstance(doc_id, str):
#             return self.get([doc_id])
#         elif isinstance(doc_id, list):
#             return self.get(doc_id)
#         else:
#             raise ValueError("doc_id 必须是字符串或列表")

#     def get_by_seg_id(self, seg_id: Union[str, List[str]]) -> Optional[List[Dict[str, Any]]]:
#         """根据seg_id获取数据
        
#         Args:
#             seg_id: 段落ID
#         Returns:
#             Dict[str, Any]: 数据
#         """
#         if isinstance(seg_id, str):
#             return self.query(filter_expr=f'seg_id == "{seg_id}"')
#         elif isinstance(seg_id, list):
#             return self.query(filter_expr=f'seg_id in {seg_id}')
#         else:
#             raise ValueError("seg_id 必须是字符串或列表")

#     def get_parent_segments(self, seg_ids: List[str]) -> List[Dict[str, Any]]:
#         """获取父片段数据
        
#         Args:
#             seg_ids: 段落ID列表, 父片段的seg_id在 seg_parent_id 中
#         Returns:
#             List[Dict[str, Any]]: 父片段数据
#         """
#         try:
#             if not seg_ids:
#                 return []

#             # 查询父片段
#             parent_expr = f'seg_parent_id in {seg_ids}'
#             results = self.query(filter_expr=parent_expr, output_fields=["*"])

#             logger.info(f"获取父片段数据成功, 共 {len(results)} 条")
#             return results

#         except Exception as e:
#             logger.error(f"获取父片段数据失败: {str(e)}")
#             return []


# # 全局集合实例
# _hybrid_collection: Optional[MilvusHybridCollection] = None


# def get_hybrid_collection() -> MilvusHybridCollection:
#     """获取集合"rag_collection_v2"的实例"""
#     global _hybrid_collection
#     if _hybrid_collection is None:
#         _hybrid_collection = MilvusHybridCollection()
#     return _hybrid_collection


# def init_hybrid_collection() -> bool:
#     """初始化集合"rag_collection_v2"的实例"""
#     try:
#         collection = get_hybrid_collection()

#         # 创建集合
#         if not collection.create_collection():
#             return False

#         # 创建索引
#         if not collection.create_indexes():
#             return False

#         # 加载集合
#         if not collection.load():
#             return False

#         logger.info("集合'rag_collection_v2'初始化完成")
#         return True

#     except Exception as e:
#         logger.error(f"初始化集合'rag_collection_v2'失败: {str(e)}")
#         return False
