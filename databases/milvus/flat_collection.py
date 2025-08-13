"""FLAT Collection 管理模块

提供 FLAT 索引集合的创建、管理和操作功能。
专门用于小数据量场景，确保向量检索结果的稳定性。

使用示例：
    # 创建 FLAT collection 管理器
    flat_manager = FlatCollectionManager()

    # 初始化 collection
    flat_manager.init_collection()

    # 插入数据
    flat_manager.insert_data(data_list)
"""

import json
import threading
from typing import Any

from pymilvus import CollectionSchema, DataType, FieldSchema, Function, FunctionType, MilvusClient, connections

from config.global_config import GlobalConfig
from config.milvus_config import MilvusFlatConfig
from utils.log_utils import logger


class FlatCollectionManager:
    """
    FLAT Collection 管理器

    专门管理使用 FLAT 索引的向量集合，提供：
    1. 集合创建和初始化
    2. 数据插入和查询
    3. 索引管理
    4. 集合状态监控

    Attributes:
        collection_name: 集合名称，默认为 "rag_flat"
        config: Milvus 配置对象
    """

    # 多实例模式 - 按集合名称区分
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """按集合名称创建不同实例"""
        collection_name = kwargs.get('collection_name', 'rag_flat')
        if collection_name not in cls._instances:
            with cls._lock:
                if collection_name not in cls._instances:
                    cls._instances[collection_name] = super().__new__(cls)
                    cls._instances[collection_name].__init__(*args, **kwargs)
        return cls._instances[collection_name]

    def __init__(self, collection_name="rag_flat"):
        """初始化 FLAT Collection 管理器

        初始化时自动创建数据库和集合.

        Args:
            collection_name (str): 集合名称，默认为 "rag_flat"
        """
        # 避免重复初始化
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.collection_name = collection_name
        self.config = MilvusFlatConfig()
        self._initialized = False
        self._current_db = None

        # 初始化 Milvus 客户端
        self._init_client()

        # 自动初始化数据库
        self._init_db()

        # 自动初始化集合
        self._init_collection()

        # 标记初始化
        self._initialized = True
        logger.info(f"[FLAT Milvus] Collection 管理器初始化成功, collection_name: {self.collection_name}")

    @classmethod
    def get_instance(cls, collection_name="rag_flat"):
        """获取单例实例

        Args:
            collection_name (str): 集合名称，默认为 "rag_flat"

        Returns:
            FlatCollectionManager: 单例实例
        """
        return cls(collection_name)

    def _init_client(self):
        """初始化 Milvus 客户端"""
        try:
            self.client = MilvusClient(
                uri=GlobalConfig.MILVUS_CONFIG["uri"], token=GlobalConfig.MILVUS_CONFIG.get("token")
            )

            # 建立连接
            connections.connect(
                alias="default",
                host=GlobalConfig.MILVUS_CONFIG["host"],
                port=GlobalConfig.MILVUS_CONFIG["port"],
                token=GlobalConfig.MILVUS_CONFIG.get("token"),
            )

            # 使用配置中的db_name，如果没有则使用default
            self.db_name = GlobalConfig.MILVUS_CONFIG.get("db_name", "default")
            self._current_db = "default"  # 初始化为 default 数据库

            logger.info(f"[FLAT Milvus] Collection 管理器初始化成功，数据库： {self._current_db}")

        except Exception as e:
            logger.error(f"[FLAT Milvus] Collection 管理器初始化失败: {e}")
            raise

    @staticmethod
    def _load_schema() -> dict[str, Any]:
        """加载集合 schema 配置

        使用与原有 collection 相同的字段结构，确保数据兼容性。

        Returns:
            dict[str, Any]: schema 配置字典
        """
        schema_path = GlobalConfig.PATHS.get("milvus_flat_schema")
        with open(schema_path, encoding="utf-8") as f:
            schema_config = json.load(f)

        return schema_config

    def _init_db(self, force_recreate: bool = False) -> bool:
        """创建 Database

        Args:
            force_recreate: 是否强制重新创建数据库

        Returns:
            bool: 初始化是否成功
        """
        try:
            # 检查数据库是否存在
            db_list = self.client.list_databases()
            db_exists = self.db_name in db_list

            # 如果需要强制重新创建或数据库不存在，则创建数据库
            if force_recreate or not db_exists:
                if db_exists:
                    logger.warning(f"[FLAT Milvus] Database {self.db_name} 已存在，强制重新创建")
                    self.client.drop_database(self.db_name)

                logger.info(f"[FLAT Milvus] 创建Database {self.db_name} ...")
                self.client.create_database(self.db_name)
                logger.info(f"[FLAT Milvus] Database {self.db_name} 创建成功")
            else:
                logger.info(f"[FLAT Milvus] Database {self.db_name} 已存在，跳过创建")

            # 切换到目标数据库
            if self._current_db != self.db_name:
                logger.info(f"[FLAT Milvus] 切换Database到 {self.db_name}")
                self.client.using_database(self.db_name)
                self._current_db = self.db_name
                logger.info("[FLAT Milvus] 切换Database成功!")

            return True

        except Exception as e:
            logger.error(f"[FLAT Milvus] Database 创建失败: {e}")
            return False

    def _init_collection(self, force_recreate: bool = False) -> bool:
        """
        初始化 FLAT collection

        创建集合和 FLAT 索引，确保集合可以正常使用。

        Args:
            force_recreate: 是否强制重新创建集合（会删除现有数据）

        Returns:
            bool: 初始化是否成功
        """
        try:
            # 切换到指定数据库
            self.client.using_database(self.db_name)

            # 检查集合是否存在
            collections = self.client.list_collections()

            if self.collection_name in collections:
                if force_recreate:
                    logger.warning(f"[FLAT Milvus] Collection {self.collection_name} 已存在，强制重新创建")
                    self.drop_collection()
                else:
                    logger.info(f"[FLAT Milvus] Collection {self.collection_name} 已存在，跳过创建")
                    return True

            # 创建集合
            logger.info(f"[FLAT Milvus] 创建Collection {self.collection_name} ...")
            self._create_collection()

            # 创建 FLAT 索引
            self._create_flat_index()

            logger.info(f"[FLAT Milvus] Collection {self.collection_name} 初始化成功")
            return True
        except Exception as e:
            logger.error(f"[FLAT Milvus] Collection 初始化失败: {e}")
            return False

    def _create_collection(self):
        """创建集合"""
        # 加载 schema 配置
        schema_config = self._load_schema()

        # 创建字段
        fields = []
        for field_config in schema_config["fields"]:
            field = FieldSchema(
                name=field_config["name"],
                dtype=getattr(DataType, field_config["type"]),
                description=field_config.get("description", ""),
                is_primary=field_config.get("is_primary", False),
                **{k: v for k, v in field_config.items() if k not in ["name", "type", "description", "is_primary"]},
            )
            fields.append(field)

        # 创建 schema
        schema = CollectionSchema(
            fields=fields,
            description=schema_config.get("description", "FLAT 索引向量库，搜索结果稳定性高"),
            enable_dynamic_field=schema_config.get("enable_dynamic_field", False),
        )

        # 创建函数
        if "functions" in schema_config:
            # 添加函数到 schema
            for func in schema_config["functions"]:
                # 创建 BM25 函数
                function = Function(
                    name=func["name"],
                    input_field_names=func["input_field_names"],
                    output_field_names=func["output_field_names"],
                    function_type=getattr(FunctionType, func["function_type"]),
                )
                schema.add_function(function)

        # 创建集合
        self.client.create_collection(collection_name=self.collection_name, schema=schema)

        logger.info(f"[FLAT Milvus] Collection {self.collection_name} 创建成功")

    def _create_flat_index(self):
        """创建 FLAT 索引"""
        try:
            # 获取 FLAT 索引参数
            index_params = self.client.prepare_index_params()

            # 为稠密向量创建 FLAT 索引
            flat_index_params = self.config.get_dense_index_params()
            index_params.add_index(**flat_index_params)

            # 为稀疏向量创建 SPARSE_INVERTED_INDEX 索引
            sparse_index_params = self.config.get_sparse_index_params()
            index_params.add_index(**sparse_index_params)

            logger.info("[FLAT Milvus] 正在为向量字段创建 FLAT 索引 ...")
            self.client.create_index(collection_name=self.collection_name, index_params=index_params)

            # 验证索引创建
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            logger.info(f"[FLAT Milvus] Collection {self.collection_name} 索引列表: {indexes}")

            # 加载集合
            self.client.load_collection(collection_name=self.collection_name)
            logger.info("[FLAT Milvus] FLAT 索引创建成功, Collection 已加载")

        except Exception as e:
            logger.error(f"[FLAT Milvus] 创建 FLAT 索引失败：{str(e)}")
            raise

    def insert_data(self, data: list[dict[str, Any]]) -> list[str]:
        """
        插入数据到 FLAT collection

        Args:
            data: 要插入的数据列表

        Returns:
            list[str]: 插入成功的数据 ID 列表

        Raises:
            ValueError: 当数据格式不符合要求时抛出
        """
        try:
            # 验证数据格式
            self._validate_data(data)

            # 插入数据
            result = self.client.insert(collection_name=self.collection_name, data=data)

            inserted_ids = result["ids"]

            # 执行持久化操作，确保数据持久化
            self.client.flush(collection_name=self.collection_name)

            logger.info(f"[FLAT Milvus] Collection 数据插入成功，共 {len(inserted_ids)} 条")
            return inserted_ids
        except Exception as e:
            logger.error(f"[FLAT Milvus] Collection 数据插入失败：{str(e)}")
            raise

    def vector_search(
        self, query_vector: list[float], doc_ids: list[str], limit: int, output_fields: list[str] = None
    ) -> list[list[dict]]:
        """
        执行向量相似性搜索，并返回标准化的结果格式。
        """
        try:
            output_fields = output_fields or ["*"]
            filter_expr = f"doc_id in {doc_ids}"
            search_params = {"metric_type": "IP", "params": {}}

            search_results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                anns_field="seg_dense_vector",
                limit=limit,
                search_params=search_params,
                output_fields=output_fields,
                filter=filter_expr,
            )

            # 将SearchResult转换为标准字典格式
            results = []
            if search_results and search_results[0]:
                for hit in search_results[0]:
                    entity = hit.get("entity", {})
                    result = {
                        "entity": {
                            "doc_id": entity.get("doc_id", ""),
                            "seg_id": entity.get("seg_id", ""),
                            "seg_content": entity.get("seg_content", ""),
                            "seg_type": entity.get("seg_type", ""),
                            "seg_page_idx": entity.get("seg_page_idx", 0),
                            "metadata": entity.get("metadata", {})
                        },
                        "score": hit.get("distance", 0.0),  # 统一为 score
                        "id": hit.get("id")
                    }
                    results.append(result)
            
            return [results]

        except Exception as e:
            logger.error(f"[FLAT Milvus] 向量搜索检索失败: {str(e)}")
            return [[]] # 保持格式一致

    def full_text_search(
        self, query_text: str, doc_ids: list[str], limit: int, output_fields: list[str] = None
    ) -> list[list[dict]]:
        """
        执行全文检索(BM25)，并返回标准化的结果格式。
        """
        try:
            output_fields = output_fields or ["*"]
            search_params = {"params": {}, "is_sparse": True}
            filter_expr = f"doc_id in {doc_ids}"

            search_results = self.client.search(
                collection_name=self.collection_name,
                data=[query_text],
                anns_field="seg_sparse_vector",
                search_params=search_params,
                filter=filter_expr,
                limit=limit,
                output_fields=output_fields,
            )

            # 将原始BM25结果转换为与向量搜索一致的标准格式
            formatted_results = []
            if search_results and search_results[0]:
                for hit in search_results[0]:
                    entity = hit.get("entity", {})
                    formatted_result = {
                        "entity": {
                            "doc_id": entity.get("doc_id", ""),
                            "seg_id": entity.get("seg_id", ""),
                            "seg_content": entity.get("seg_content", ""),
                            "seg_type": entity.get("seg_type", ""),
                            "seg_page_idx": entity.get("seg_page_idx", 0),
                            "metadata": entity.get("metadata", {})
                        },
                        "score": hit.get("score", 0.0), # 统一为 score
                        "id": hit.get("id")
                    }
                    formatted_results.append(formatted_result)

            logger.info(f"[FLAT Milvus] 全文检索(BM25)成功，召回 {len(formatted_results)} 条")
            return [formatted_results]
        except Exception as e:
            logger.error(f"[FLAT Milvus] 全文搜索(BM25)失败: {str(e)}")
            return [[]]

    def _less_hybrid_search(
        self, query_text: str, query_vector: list[float], doc_id_list: list[str], limit: int, output_fields: list[str]
    ) -> tuple[list[dict], list[dict]]:
        """
        同时执行向量检索和BM25检索，返回两个独立的结果列表。

        Args:
            query_text: 查询文本
            query_vector: 查询向量
            doc_id_list: 文档 ID 列表
            limit: 每个检索召回的数量
            output_fields: 输出字段

        Returns:
            tuple[list[dict], list[dict]]: (向量检索结果, BM25检索结果)
        """
        try:
            # 1. 执行向量检索
            vector_results_raw = self.vector_search(
                query_vector=query_vector, doc_ids=doc_id_list, limit=limit, output_fields=output_fields
            )
            vector_results = vector_results_raw[0] if vector_results_raw else []
            logger.debug(f"[混合检索] 向量检索完成，召回 {len(vector_results)} 条")

            # 2. 执行全文检索 (BM25)
            full_text_results_raw = self.full_text_search(
                query_text=query_text, doc_ids=doc_id_list, limit=limit, output_fields=output_fields
            )
            full_text_results = full_text_results_raw[0] if full_text_results_raw else []
            logger.debug(f"[混合检索] 全文检索(BM25)完成，召回 {len(full_text_results)} 条")

            return vector_results, full_text_results

        except Exception as e:
            logger.error(f"[FLAT Milvus] 并行检索失败: {str(e)}")
            return [], []

    @staticmethod
    def _reciprocal_rank_fusion(
        results_lists: list[list[dict]], k: int = 60, limit: int = 50
    ) -> list[dict]:
        """
        使用倒数排名融合 (RRF) 算法合并多个检索结果列表。

        Args:
            results_lists: 一个包含多个检索结果列表的列表。
                           每个结果列表是一个字典列表，字典中必须包含'seg_id'。
            k: RRF算法中的排名常数，默认为60。
            limit: 最终返回的结果数量。

        Returns:
            list[dict]: 经过RRF融合排序和去重后的结果列表。
        """
        fused_scores = {}
        doc_info = {} # 存储每个文档的完整信息

        # 遍历每个检索结果列表
        for results in results_lists:
            # 遍历单个列表中的每个文档
            for rank, doc in enumerate(results):
                seg_id = doc.get("entity", {}).get("seg_id")
                if not seg_id:
                    continue
                
                # 如果是第一次见到这个seg_id，存储它的信息
                if seg_id not in doc_info:
                    doc_info[seg_id] = doc

                # 计算RRF分数
                if seg_id not in fused_scores:
                    fused_scores[seg_id] = 0
                fused_scores[seg_id] += 1 / (k + rank + 1) # rank从0开始，所以+1

        # 按RRF分数对文档进行降序排序
        reranked_results = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)

        # 构建最终的排序后文档列表
        final_results = []
        for seg_id, score in reranked_results:
            doc = doc_info[seg_id]
            doc['rerank_score'] = score  # 可以将RRF分数存入，供后续使用
            final_results.append(doc)

        return final_results[:limit]
        
    def optimized_hybrid_search(
        self,
        doc_id_list: list[str],
        query_text: str,
        query_vector: list[float],
        limit: int,
        output_fields: list[str] = None,
    ) -> list[list[dict]]:
        """
        优化的混合检索，使用RRF进行结果融合。

        Args:
            doc_id_list: 文档 ID 列表
            query_text: 查询文本
            query_vector: 查询向量
            limit: 最终返回数量
            output_fields: 输出字段

        Returns:
            list[list[dict]]: 融合排序后的结果列表
        """
        try:
            output_fields = output_fields or GlobalConfig.MILVUS_CONFIG["output_fields"]
            
            # 1. 并行执行向量检索和BM25检索
            vector_results, full_text_results = self._less_hybrid_search(
                query_text=query_text,
                query_vector=query_vector,
                doc_id_list=doc_id_list,
                limit=limit, # 初始召回数量
                output_fields=output_fields,
            )
            
            # 2. 使用RRF融合结果
            if not vector_results and not full_text_results:
                logger.info("[混合检索] 向量和BM25均未召回任何结果")
                return [[]]

            fused_results = self._reciprocal_rank_fusion(
                [vector_results, full_text_results], limit=limit
            )

            logger.info(f"[混合检索] RRF融合完成，返回 {len(fused_results)} 条结果")
            
            return [fused_results]

        except Exception as e:
            logger.error(f"[FLAT Milvus] 优化的混合检索失败: {str(e)}")
            return [[]]

    def _validate_data(self, data: list[dict[str, Any]]):
        """
        验证数据格式

        Args:
            data: 要验证的数据列表

        Raises:
            ValueError: 当数据格式不符合要求时抛出
        """
        if not data:
            raise ValueError("[FLAT Milvus] 数据列表不能为空")

        # 加载 schema 获取必须字段
        schema_config = self._load_schema()
        required_fields = [field["name"] for field in schema_config["fields"] if field["name"] != "seg_sparse_vector"]

        for idx, item in enumerate(data):
            # 检查必须字段
            missing_fields = set(required_fields) - set(item.keys())
            if missing_fields:
                raise ValueError(f"[FLAT Milvus] 第 {idx + 1} 条数据缺少必须字段：{missing_fields}")

            # 验证向量字段
            embed_dim = GlobalConfig.MILVUS_CONFIG["vector_dim"]
            if not isinstance(item["seg_dense_vector"], list) or len(item["seg_dense_vector"]) != embed_dim:
                raise ValueError(f"[FLAT Milvus] 第 {idx + 1} 条数据的 seg_dense_vector 字段必须是 1024维的浮点数列表")

    def get_collection_stats(self) -> dict[str, Any]:
        """
        获取集合统计信息

        Returns:
            dict[str, Any]: 集合统计信息
        """
        try:
            stats = self.client.get_collection_stats(collection_name=self.collection_name)
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            load_state = self.client.get_load_state(collection_name=self.collection_name)

            return {
                "collection_name": self.collection_name,
                "entity_count": stats.get("row_count", 0),
                "indexes": indexes,
                "load_state": load_state,
                "index_type": "FLAT",
                "config": self.config.get_config_summary(),
            }
        except Exception as e:
            logger.error(f"[FLAT Milvus] 获取集合统计信息失败： {str(e)}")
            return {}

    def drop_collection(self, force: bool = False) -> bool:
        """
        删除集合

        Args：
            force: 是否强制删除，不需要确认

        Returns:
            bool: 删除是否成功
        """
        try:
            self.client.using_database(self.db_name)

            if not self.client.has_collection(self.collection_name):
                logger.warning(f"[FLAT Milvus] Collection {self.collection_name} 不存在")
                return True

            if not force:
                logger.warning(f"[FLAT Milvus] 即将删除集合 {self.collection_name}, 此操作不可恢复！")
                confirm = input(f"确定要删除集合 {self.collection_name} 吗？（y/n）：")
                if confirm.lower() != "y":
                    logger.info("已取消删除操作")
                    return False

            self.client.drop_collection(self.collection_name)
            logger.info(f"[FLAT Milvus] Collection {self.collection_name} 已删除")
            return True
        except Exception as e:
            logger.error(f"[FLAT MIlvus] 删除 Collection 失败：{str(e)}")
            return False

    def delete_by_doc_id(self, doc_id: str) -> int:
        """根据文档ID删除数据

        Args:
            doc_id (str): 文档ID

        Returns:
            int: 删除的记录数量
        """
        try:
            # 执行删除
            result: dict[str, int] = self.client.delete(collection_name=self.collection_name, ids=doc_id)

            # 确保删除操作被持久化
            self.client.flush(collection_name=self.collection_name)

            return result["delete_count"]

        except Exception as e:
            logger.error(f"Milvus 数据删除失败: {str(e)}")
            return False

    def get_existing_doc_ids(self, doc_id_list: list[str]) -> set[str]:
        """批量查询已存在的 doc_id 集合，用于去重插入

        Args:
            doc_id_list: 待检查的主键列表

        Returns:
            set[str]: 已存在的主键集合
        """
        try:
            if not doc_id_list:
                return set()

            self.client.using_database(self.db_name)

            # Milvus 表达式中 in 列表需要是 ["a","b"] 格式
            # 分批查询，避免表达式过长
            batch_size = 1000
            exists: set[str] = set()
            for i in range(0, len(doc_id_list), batch_size):
                batch = doc_id_list[i : i + batch_size]
                quoted = ",".join([f'"{x}"' for x in batch])
                expr = f"doc_id in [{quoted}]"
                rows = self.client.query(
                    collection_name=self.collection_name,
                    filter=expr,
                    output_fields=["doc_id"],
                )
                for row in rows:
                    did = row.get("doc_id")
                    if did:
                        exists.add(did)
            return exists
        except Exception as e:
            logger.error(f"[FLAT Milvus] 查询已存在 doc_id 失败: {str(e)}")
            return set()

    def exists(self) -> bool:
        """
        检查集合是否存在

        Returns:
            bool: 集合是否存在
        """
        return self.client.has_collection(self.collection_name)

    def get_all_doc_ids(self) -> list[str]:
        """
        获取集合中所有的doc_id列表，使用基于主键的游标翻页处理大数据量
        
        Returns:
            list[str]: 所有doc_id列表
        """
        try:
            all_doc_ids = set()  # 使用set自动去重
            batch_size = 10000  # 批次大小，不受max_query_result_window限制
            last_pk = None  # 游标：上一批的最后一个主键
            
            logger.debug(f"[FLAT Milvus] 开始使用游标翻页获取所有doc_id，批次大小: {batch_size}")
            
            batch_count = 0
            while True:
                batch_count += 1
                
                # 构建基于主键的过滤条件
                # 注意：这个集合的主键字段是doc_id，需要使用字符串比较
                if last_pk is not None:
                    expr = f'doc_id > "{last_pk}"'
                    logger.debug(f"[FLAT Milvus] 批次 {batch_count}: 游标翻页，doc_id > \"{last_pk}\"")
                else:
                    expr = ""  # 第一次查询不需要过滤条件
                    logger.debug(f"[FLAT Milvus] 批次 {batch_count}: 首次查询")
                
                # 执行查询，获取doc_id字段（既是主键也是我们需要的数据）
                # 注意：为了确保游标翻页的正确性，需要按主键排序
                results = self.client.query(
                    collection_name=self.collection_name,
                    filter=expr,
                    output_fields=["doc_id"],  # 只需要doc_id字段
                    limit=batch_size,
                    # 注意：Milvus的query方法不直接支持order by，但结果通常是有序的
                    # 如果需要严格排序，可能需要在应用层处理
                )
                
                if not results:
                    # 没有更多数据，退出循环
                    logger.debug(f"[FLAT Milvus] 批次 {batch_count}: 查询完成，无更多数据")
                    break
                
                # 提取doc_id并确保排序
                batch_doc_ids = [record.get("doc_id", "") for record in results if record.get("doc_id")]
                if not batch_doc_ids:
                    # 这一批没有有效的doc_id，退出循环
                    logger.debug(f"[FLAT Milvus] 批次 {batch_count}: 查询完成，无有效doc_id")
                    break
                
                # 对这一批的doc_id进行排序，确保游标翻页的正确性
                batch_doc_ids.sort()
                
                all_doc_ids.update(batch_doc_ids)
                logger.debug(f"[FLAT Milvus] 批次 {batch_count}: 获取到 {len(batch_doc_ids)} 个doc_id, 累计 {len(all_doc_ids)} 个唯一doc_id")
                
                # 如果返回的结果少于batch_size，说明已经到最后一页
                if len(results) < batch_size:
                    logger.debug(f"[FLAT Milvus] 批次 {batch_count}: 查询完成，已到最后一页 (返回{len(results)}个，期望{batch_size}个)")
                    break
                
                # 更新游标：使用这一批排序后的最后一个doc_id（主键）
                last_pk = batch_doc_ids[-1]  # 使用排序后的最后一个
                logger.debug(f"[FLAT Milvus] 批次 {batch_count}: 更新游标，下次查询从 doc_id > \"{last_pk}\" 开始")
            
            doc_ids = list(all_doc_ids)
            logger.info(f"[FLAT Milvus] 从集合 {self.collection_name} 游标翻页获取到 {len(doc_ids)} 个唯一doc_id，共 {batch_count} 个批次")
            
            return doc_ids
            
        except Exception as e:
            logger.error(f"[FLAT Milvus] 获取doc_id列表失败: {str(e)}")
            logger.info("[FLAT Milvus] 尝试回退到MySQL方式获取doc_id列表")
            
            # 如果Milvus查询失败，回退到MySQL方式
            try:
                from databases.mysql.operations import file_op
                
                # 查询所有可见的文档ID
                sql = f"SELECT DISTINCT doc_id FROM {file_op.table_name} WHERE is_visible = true"
                results = file_op._execute_query(sql, ())
                
                # 转换为Milvus中存储的格式（如果需要）
                doc_ids = [row['doc_id'] for row in results if row.get("doc_id")]
                logger.info(f"[FLAT Milvus] MySQL备用方案获取到 {len(doc_ids)} 个文档ID")
                
                return doc_ids
                
            except Exception as e2:
                logger.error(f"[FLAT Milvus] MySQL备用方案也失败: {e2}")
                return []

    def close(self):
        """关闭 Milvus 客户端"""
        self.client.close()


if __name__ == "__main__":
    # # 测试 FLAT collection 创建
    # logger.info("开始测试 FLAT Collection 创建...")
    #
    # try:
    #     # 创建管理器
    #     flat_manager = FlatCollectionManager()
    #
    #     # 删除 collection
    #     # flat_manager.drop_collection(True)
    #
    #     # # 验证索引信息
    #     # collection_info = flat_manager.client.describe_collection(
    #     #     collection_name=flat_manager.collection_name
    #     # )
    #     # print(collection_info)
    #     # print("=" * 60)
    #     # index_info = flat_manager.client.describe_index(
    #     #     collection_name=flat_manager.collection_name, index_name="seg_sparse_vector"
    #     # )
    #     # print(index_info)
    #     #
    #     # print("=" * 60)
    #     #
    #     # # 验证数据插入
    #     # results = flat_manager.client.query(
    #     #     collection_name=flat_manager.collection_name,
    #     #     filter="doc_id == '308802d4082973cf8c3a548413585e753b4d37ffa8f8e16a3a005e8023066e52'",
    #     #     output_fields=["seg_content", "doc_id"],
    #     # )
    #     # print(results)
    #     # print("=" * 60)
    #     #
    #     # # # 测试稀疏向量
    #     # search_params = {"params": {"drop_ratio_search": 0.2}}
    #     #
    #     # search_results = flat_manager.client.search(
    #     #     collection_name=flat_manager.collection_name,
    #     #     data=["红楼梦"],
    #     #     anns_field="seg_sparse_vector",
    #     #     search_params=search_params,
    #     #     limit=5,
    #     #     output_fields=["seg_content", "doc_id"],
    #     # )
    #     # print(search_results)
    #     # print("=" * 60)
    #
    #     # 初始化embedding
    #     embedding_manager = EmbeddingManager()
    #     # 测试混合检索
    #     hybrid_res: list[list[dict]] = flat_manager.optimized_hybrid_search(
    #         doc_id_list=[
    #             "308802d4082973cf8c3a548413585e753b4d37ffa8f8e16a3a005e8023066e52",
    #         ],
    #         query_text="红色",
    #         query_vector=embedding_manager.embed_text("红色"),
    #         limit=2,
    #     )
    #     print(len(hybrid_res))
    #     print(hybrid_res)
    #     print("=" * 60)
    #     # 获取统计信息
    #     # stats = flat_manager.get_collection_stats()
    #     # logger.info(f"[FLAT Milvus] Collection 统计信息：{stats}")
    #
    # except Exception as e:
    #     logger.error(f"[FLAT Milvus] 测试过程中出现错误：{str(e)}")

    # 准备查询参数
    flat_manager = FlatCollectionManager()

    query_text = "出差旅费报销单"
    from utils.llm_utils import embedding_manager

    query_vector = embedding_manager.embed_text(query_text)
    doc_id_list = [
        "308802d4082973cf8c3a548413585e753b4d37ffa8f8e16a3a005e8023066e52",
        "84bf50f240e290c94c850ee5f936838368c61b7f1e3be4f321f4aa9c2b843021",
        "162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26",
        "c2815526bd0fafe2ab7874b43efe9b58cf840c6dba94d49228a2d9506cbffd62",
    ]
    limit = 100

    # 查询集合数量
    desc = flat_manager.client.describe_collection(flat_manager.collection_name)

    print(desc)
    print("-" * 100)

    print(flat_manager.client.get_collection_stats(flat_manager.collection_name))
    print("-" * 100)

    res = flat_manager.client.search(
        collection_name=flat_manager.collection_name,
        data=[query_vector],
        anns_field="seg_dense_vector",
        limit=limit,
        output_fields=["seg_id", "seg_content"],
    )

    for hit in res[0]:
        print(hit)

    print("-" * 100)

    sparse_res = flat_manager.client.search(
        collection_name=flat_manager.collection_name,
        data=[query_text],
        anns_field="seg_sparse_vector",
        limit=limit,
        output_fields=["seg_id", "seg_content"],
        filter='doc_id in ["123"]',
    )

    for hit in sparse_res[0]:
        print(hit)
