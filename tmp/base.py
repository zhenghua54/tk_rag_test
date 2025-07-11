# """Milvus数据库基础连接类 - 单例模式 + 线程安全连接池 + 基础CRUD操作"""
#
# import threading
# from typing import Optional, List, Dict, Any, Union
# from pymilvus import MilvusClient, connections, CollectionSchema, Collection, Function
#
# from config.global_config import GlobalConfig
# from utils.log_utils import logger
#
#
# class MilvusBase:
#     """Milvus基础连接类 - 单例模式，提供基础CRUD操作"""
#
#     _instance: Optional['MilvusBase'] = None  # 单例模式实例
#     _lock = threading.Lock()  # 线程锁，在创建实例和初始化时加锁，防止多个线程同时创建实例导致的问题
#     _initialized = False  # 是否已初始化
#
#     def __new__(cls):
#         """单例模式实现 - 确保全局只有一个实例"""
#         if cls._instance is None:  # 第一次检查
#             with cls._lock:  # 加锁
#                 if cls._instance is None:  # 第二次检查（双重检查锁定）
#                     cls._instance = super(MilvusBase, cls).__new__(cls)
#         return cls._instance
#
#     def __init__(self):
#         """初始化Milvus基础连接 - 线程安全"""
#         if self._initialized:  # 如果已初始化，直接返回
#             return
#
#         with self._lock:  # 加锁
#             if self._initialized:  # 再次检查
#                 return
#
#             try:
#                 # 初始化MilvusClient
#                 self.client = MilvusClient(
#                     uri=GlobalConfig.MILVUS_CONFIG["uri"],
#                     token=GlobalConfig.MILVUS_CONFIG["token"]
#                 )
#
#                 # 建立连接
#                 connections.connect(
#                     alias="default",
#                     host=GlobalConfig.MILVUS_CONFIG["host"],
#                     port=GlobalConfig.MILVUS_CONFIG["port"],
#                     token=GlobalConfig.MILVUS_CONFIG["token"],
#                 )
#
#                 self.db_name = GlobalConfig.MILVUS_CONFIG["db_name"]
#                 self._initialized = True
#                 logger.info(f"[Milvus初始化] 基础连接初始化成功")
#
#             except Exception as e:
#                 logger.error(f"[Milvus初始化失败] error_msg={str(e)}")
#                 raise
#
#     def get_client(self) -> MilvusClient:
#         """获取Milvus客户端实例"""
#         return self.client
#
#     # ==================== 数据库操作 ====================
#
#     def switch_database(self, db_name: str) -> None:
#         """切换数据库
#
#         Args:
#             db_name: 数据库名称
#         """
#         try:
#             self.client.using_database(db_name)
#             logger.info(f"[Milvus数据库] 切换到数据库: {db_name}")
#         except Exception as e:
#             logger.error(f"切换数据库失败: {str(e)}")
#             raise
#
#     def list_databases(self) -> List[str]:
#         """列出所有数据库
#
#         Returns:
#             List[str]: 数据库名称列表
#         """
#         try:
#             return self.client.list_databases()
#         except Exception as e:
#             logger.error(f"获取数据库列表失败: {str(e)}")
#             return []
#
#     def create_database(self, db_name: str) -> bool:
#         """创建数据库
#
#         Args:
#             db_name: 数据库名称
#
#         Returns:
#             bool: 创建是否成功
#         """
#         try:
#             self.client.create_database(db_name=db_name)
#             logger.info(f"数据库 {db_name} 创建成功")
#             return True
#         except Exception as e:
#             logger.error(f"创建数据库失败: {str(e)}")
#             return False
#
#     def drop_database(self, db_name: str) -> bool:
#         """删除数据库
#
#         Args:
#             db_name: 数据库名称
#
#         Returns:
#             bool: 删除是否成功
#         """
#         try:
#             self.client.drop_database(db_name=db_name)
#             logger.info(f"数据库 {db_name} 删除成功")
#             return True
#         except Exception as e:
#             logger.error(f"删除数据库失败: {str(e)}")
#             return False
#
#     # ==================== 集合操作 ====================
#
#     def list_collections(self) -> List[str]:
#         """列出当前数据库的所有集合
#
#         Returns:
#             List[str]: 集合名称列表
#         """
#         try:
#             return self.client.list_collections()
#         except Exception as e:
#             logger.error(f"获取集合列表失败: {str(e)}")
#             return []
#
#     def create_collection(self, collection_name: str, schema: CollectionSchema) -> bool:
#         """创建集合
#
#         Args:
#             collection_name: 集合名称
#             schema: 集合schema定义
#
#         Returns:
#             bool: 创建是否成功
#         """
#         try:
#             self.client.create_collection(
#                 collection_name=collection_name,
#                 schema=schema
#             )
#             logger.info(f"集合 {collection_name} 创建成功")
#             return True
#         except Exception as e:
#             logger.error(f"创建集合失败: {str(e)}")
#             return False
#
#     def create_collection_with_function(self, collection_name: str, schema, function: Function, index_params=None) -> bool:
#         """创建集合时添加函数 - 官方推荐方法
#
#         Args:
#             collection_name: 集合名称
#             schema: 集合schema
#             function: 函数对象
#             index_params: 索引参数
#
#         Returns:
#             bool: 创建是否成功
#         """
#         try:
#             # 检查集合是否已存在
#             if self.has_collection(collection_name):
#                 logger.warning(f"集合 {collection_name} 已存在")
#                 return True
#
#             # 将函数添加到schema
#             schema.add_function(function)
#
#             # 创建集合
#             self.client.create_collection(
#                 collection_name=collection_name,
#                 schema=schema,
#                 index_params=index_params
#             )
#
#             logger.info(f"集合 {collection_name} 创建成功，包含函数 {function.name}")
#             return True
#         except Exception as e:
#             logger.error(f"创建集合失败: {str(e)}")
#             return False
#
#     def drop_collection(self, collection_name: str) -> bool:
#         """删除集合
#
#         Args:
#             collection_name: 集合名称
#
#         Returns:
#             bool: 删除是否成功
#         """
#         try:
#             self.client.drop_collection(collection_name=collection_name)
#             logger.info(f"集合 {collection_name} 删除成功")
#             return True
#         except Exception as e:
#             logger.error(f"删除集合失败: {str(e)}")
#             return False
#
#     def has_collection(self, collection_name: str) -> bool:
#         """检查集合是否存在
#
#         Args:
#             collection_name: 集合名称
#
#         Returns:
#             bool: 集合是否存在
#         """
#         try:
#             collections = self.list_collections()
#             return collection_name in collections
#         except Exception as e:
#             logger.error(f"检查集合存在性失败: {str(e)}")
#             return False
#
#     @staticmethod
#     def get_collection(collection_name: str) -> Collection:
#         """获取集合实例
#
#         Args:
#             collection_name: 集合名称
#
#         Returns:
#             Collection: 集合实例
#         """
#         try:
#             return Collection(collection_name)
#         except Exception as e:
#             logger.error(f"获取集合实例失败: {str(e)}")
#             raise
#
#     # ==================== 索引操作 ====================
#
#     def create_index(self, collection_name: str, index_params) -> bool:
#         """创建索引
#
#         Args:
#             collection_name: 集合名称
#             index_params: 索引参数
#
#         Returns:
#             bool: 创建是否成功
#         """
#         try:
#             self.client.create_index(
#                 collection_name=collection_name,
#                 index_params=index_params
#             )
#             logger.info(f"集合 {collection_name} 索引创建成功")
#             return True
#         except Exception as e:
#             logger.error(f"创建索引失败: {str(e)}")
#             return False
#
#     def list_indexes(self, collection_name: str) -> List[str]:
#         """列出集合的所有索引
#
#         Args:
#             collection_name: 集合名称
#
#         Returns:
#             List[str]: 索引名称列表
#         """
#         try:
#             return self.client.list_indexes(collection_name=collection_name)
#         except Exception as e:
#             logger.error(f"获取索引列表失败: {str(e)}")
#             return []
#
#     def drop_index(self, collection_name: str, index_name: str) -> bool:
#         """删除索引
#
#         Args:
#             collection_name: 集合名称
#             index_name: 索引名称
#
#         Returns:
#             bool: 删除是否成功
#         """
#         try:
#             self.client.drop_index(collection_name=collection_name, index_name=index_name)
#             logger.info(f"索引 {index_name} 删除成功")
#             return True
#         except Exception as e:
#             logger.error(f"删除索引失败: {str(e)}")
#             return False
#
#
#     # ==================== Entity操作 ====================
#
#     def insert(self, collection_name: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
#         """插入数据
#
#         Args:
#             collection_name: 集合名称
#             data: 要插入的数据列表
#
#         Returns:
#             Dict[str, Any]: 插入结果，包含插入的ID列表, {'insert_count': 10, 'ids': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]}
#         """
#         try:
#             result = self.client.insert(
#                 collection_name=collection_name,
#                 data=data
#             )
#             logger.info(f"数据插入成功, 共 {len(data)} 条")
#             return result
#         except Exception as e:
#             logger.error(f"插入数据失败: {str(e)}")
#             raise
#
#     def delete(self, collection_name: str, ids: Union[str, List[str]]) -> Dict[str, Any]:
#         """删除数据
#
#         Args:
#             collection_name: 集合名称
#             ids: 要删除的ID或ID列表
#
#         Returns:
#             Dict[str, Any]: 删除结果，包含删除的记录数, {'delete_count': 2}
#         """
#         try:
#             result = self.client.delete(
#                 collection_name=collection_name,
#                 ids=ids
#             )
#             logger.info(f"数据删除成功, 共 {result.get('delete_count', 0)} 条")
#             return result
#         except Exception as e:
#             logger.error(f"删除数据失败: {str(e)}")
#             raise
#
#     def upsert(self, collection_name: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
#         """更新或插入数据
#
#         Args:
#             collection_name: 集合名称
#             data: 要更新或插入的数据列表
#
#         Returns:
#             Dict[str, Any]: 操作结果, {'upsert_count': 10}
#         """
#         try:
#             result = self.client.upsert(
#                 collection_name=collection_name,
#                 data=data
#             )
#             logger.info(f"数据更新/插入成功, 共 {len(data)} 条")
#             return result
#         except Exception as e:
#             logger.error(f"更新/插入数据失败: {str(e)}")
#             raise
#
#     def get(self, collection_name: str, ids: Union[str, List[str]], output_fields: List[str] = None) -> List[
#         Dict[str, Any]]:
#         """根据指定的主键查找实体
#
#         Args:
#             collection_name: 集合名称
#             ids: 要获取的ID或ID列表
#             output_fields: 要返回的字段列表，None表示返回所有字段
#
#         Returns:
#             List[Dict[str, Any]]: 数据列表
#         """
#         try:
#             if output_fields is None:
#                 output_fields = ["*"]
#
#             results = self.client.get(
#                 collection_name=collection_name,
#                 ids=ids,
#                 output_fields=output_fields
#             )
#             logger.info(f"数据获取成功, 共 {len(results)} 条")
#             return results
#         except Exception as e:
#             logger.error(f"获取数据失败: {str(e)}")
#             return []
#
#     def query(self, collection_name: str, filter_expr: str = "", output_fields: List[str] = None, limit: int = 100) -> \
#             List[Dict[str, Any]]:
#         """根据自定义过滤条件查找满足条件的所有或指定数量的实体
#
#         Args:
#             collection_name: 集合名称
#             filter_expr: 过滤表达式
#             output_fields: 要返回的字段列表，None表示返回所有字段
#             limit: 返回结果数量限制
#
#         Returns:
#             List[Dict[str, Any]]: 查询结果列表
#         """
#         try:
#             if output_fields is None:
#                 output_fields = ["*"]
#
#             results = self.client.query(
#                 collection_name=collection_name,
#                 filter=filter_expr,
#                 output_fields=output_fields,
#                 limit=limit
#             )
#             logger.info(f"数据查询成功, 共 {len(results)} 条")
#             return results
#         except Exception as e:
#             logger.error(f"查询数据失败: {str(e)}")
#             return []
#
#     def search(self, collection_name: str, search_params: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
#         """向量相似性搜索
#
#         Args:
#             collection_name: 集合名称
#             search_params: 搜索参数, 包含向量、过滤条件、返回字段、相似度度量类型等
#
#         Returns:
#             List[List[Dict[str, Any]]]: 搜索结果，外层列表对应查询向量，内层列表对应每个查询的结果
#         """
#         try:
#             results = self.client.search(
#                 collection_name=collection_name,
#                 **search_params
#             )
#
#             query_count = len(search_params.get('data', []))
#             logger.info(f"数据搜索成功, {query_count} 个查询向量")
#             return results
#         except Exception as e:
#             logger.error(f"搜索数据失败: {str(e)}")
#             return []
#
#     def flush(self, collection_name: str) -> None:
#         """执行flush操作，确保数据持久化
#
#         Args:
#             collection_name: 集合名称
#         """
#         try:
#             self.client.flush(collection_name=collection_name)
#             logger.info(f"集合 {collection_name} 数据已持久化")
#         except Exception as e:
#             logger.error(f"flush操作失败: {str(e)}")
#             raise
#
#     @staticmethod
#     def close() -> None:
#         """关闭连接"""
#         try:
#             connections.disconnect("default")
#             logger.info("Milvus连接已关闭")
#         except Exception as e:
#             logger.error(f"关闭Milvus连接失败: {str(e)}")
#
#
# # 全局单例实例
# _milvus_base: Optional[MilvusBase] = None
#
#
# def get_milvus_base() -> MilvusBase:
#     """获取Milvus基础连接实例"""
#     global _milvus_base
#     if _milvus_base is None:
#         _milvus_base = MilvusBase()
#     return _milvus_base
#
#
# def init_milvus_base() -> MilvusBase:
#     """应用启动时初始化Milvus基础连接"""
#     global _milvus_base
#     if _milvus_base is None:
#         _milvus_base = MilvusBase()
#
#         # 确保数据库存在
#         db_name = GlobalConfig.MILVUS_CONFIG["db_name"]
#         db_list = _milvus_base.list_databases()
#         if db_name not in db_list:
#             _milvus_base.create_database(db_name)
#
#         # 切换到指定数据库
#         _milvus_base.switch_database(db_name)
#
#         logger.info("Milvus基础连接初始化完成")
#
#     return _milvus_base
