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

from pymilvus import (
    AnnSearchRequest,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    MilvusClient,
    WeightedRanker,
    connections,
)
from pymilvus.client.search_iterator import SearchIteratorV2
from pymilvus.orm.iterator import SearchIterator

from config.global_config import GlobalConfig
from config.milvus_config import MilvusFlatConfig
from utils.llm_utils import EmbeddingManager
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

    # 单例模式
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _current_db = None

    def __new__(cls, *args, **kwargs):
        """现线程安全的单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.__init__(*args, **kwargs)
        return cls._instance

    def __init__(self, collection_name="rag_flat"):
        """初始化 FLAT Collection 管理器(单例模式)

        初始化时自动创建数据库和集合.

        Args:
            collection_name (str): 集合名称，默认为 "rag_flat"
        """
        # 避免重复初始化
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.collection_name = collection_name
        self.config = MilvusFlatConfig()

        # 初始化 Milvus 客户端
        self._init_client()

        # 自动初始化数据库
        self._init_db()

        # 自动初始化集合
        self._init_collection()

        # 标记初始化
        self._initialized = True
        logger.info(
            f"[FLAT Milvus] Collection 管理器初始化成功, collection_name: {self.collection_name}"
        )

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
                uri=GlobalConfig.MILVUS_CONFIG["uri"],
                token=GlobalConfig.MILVUS_CONFIG.get("token"),
            )

            # 建立连接
            connections.connect(
                alias="default",
                host=GlobalConfig.MILVUS_CONFIG["host"],
                port=GlobalConfig.MILVUS_CONFIG["port"],
                token=GlobalConfig.MILVUS_CONFIG.get("token"),
            )

            self.db_name = GlobalConfig.MILVUS_CONFIG["db_name"]
            self._current_db = "default"  # 初始化为 default 数据库

            logger.info(
                f"[FLAT Milvus] Collection 管理器初始化成功，数据库： {self._current_db}"
            )

        except Exception as e:
            logger.error(f"[FLAT Milvus] Collection 管理器初始化失败: {e}")
            raise

    @staticmethod
    def _load_schema() -> dict[str, Any]:
        """加载集合 schema 配置

        使用与原有 collection 相同的字段结构，确保数据兼容性。

        Returns:
            Dict[str, Any]: schema 配置字典
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
                    logger.warning(
                        f"[FLAT Milvus] Database {self.db_name} 已存在，强制重新创建"
                    )
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
                    logger.warning(
                        f"[FLAT Milvus] Collection {self.collection_name} 已存在，强制重新创建"
                    )
                    self.drop_collection()
                else:
                    logger.info(
                        f"[FLAT Milvus] Collection {self.collection_name} 已存在，跳过创建"
                    )
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
                **{
                    k: v
                    for k, v in field_config.items()
                    if k not in ["name", "type", "description", "is_primary"]
                },
            )
            fields.append(field)

        # 创建 schema
        schema = CollectionSchema(
            fields=fields,
            description=schema_config.get(
                "description", "FLAT 索引向量库，搜索结果稳定性高"
            ),
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
        self.client.create_collection(
            collection_name=self.collection_name, schema=schema
        )

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
            self.client.create_index(
                collection_name=self.collection_name, index_params=index_params
            )

            # 验证索引创建
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            logger.info(
                f"[FLAT Milvus] Collection {self.collection_name} 索引列表: {indexes}"
            )

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
            List[str]: 插入成功的数据 ID 列表

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

            logger.info(
                f"[FLAT Milvus] Collection 数据插入成功，共 {len(inserted_ids)} 条"
            )
            return inserted_ids
        except Exception as e:
            logger.error(f"[FLAT Milvus] Collection 数据插入失败：{str(e)}")
            raise

    # def vector_search(
    #     self,
    #     query_vector: list[float],
    #     doc_ids: list[str],
    #     top_k: int = 100,
    #     output_fields: list[str] = None,
    # ) -> list[Any] | None:
    #     """
    #     执行向量相似性搜索
    #
    #     使用项目统一的 EmbeddingManager 生成查询向量，确保向量归一化一致性。
    #
    #     Args:
    #         query_vector: 查询文本向量(1024维浮点数)
    #         doc_ids: 文档 ID 列表
    #         top_k: 返回结果数量，默认100
    #         output_fields: 返回字段，默认使用配置的输出字段
    #
    #     Returns:
    #         list[Any] | None: 检索结果列表
    #
    #     Raises:
    #         ValueError: 当查询向量格式不正确时抛出
    #         Exception: 当搜索失败时抛出
    #     """
    #     try:
    #         # 设置默认输出字段
    #         output_fields = output_fields if output_fields else ["*"]
    #
    #         # 构建过滤条件
    #         filter_expr = f"doc_id in {doc_ids}"
    #
    #         logger.debug(f"[Milvus 检索] filter: {filter_expr}")
    #
    #         # 构建搜索参数
    #         results = self.client.search(
    #             collection_name=self.collection_name,
    #             data=[query_vector],  # 查询向量列表
    #             anns_field="seg_dense_vector",  # 向量字段名
    #             search_params={"metric_type": "IP", "params": {}},  # 搜索参数
    #             limit=top_k,  # 返回结果数量
    #             output_fields=output_fields,  # 返回字段
    #             filter=filter_expr,  # 过滤条件
    #         )
    #
    #         # 处理搜索结果: 单个查询向量，只会有一个 hits，取第一个结果列表
    #         search_results = results[0] if results else []
    #         logger.info(
    #             f"[FLAT Milvus] 向量搜索完成，返回 {len(search_results)} 条结果"
    #         )
    #
    #     except Exception as e:
    #         logger.error(f"[FLAT Milvus] 向量搜索未返回结果: {str(e)}")
    #         return []

    def vector_search_iterator(
        self,
        query_vector: list[float],
        doc_ids: list[str],
        output_fields: list[str] = None,
    ) -> SearchIteratorV2 | SearchIterator | None:
        """
        执行向量相似性搜索,返回迭代器,用于处理大量检索结果数据

        Args:
            query_vector: 查询文本向量(1024维浮点数)
            doc_ids: 文档 ID 列表
            output_fields: 返回字段

        Returns:
            Union[SearchIteratorV2, SearchIterator]: 检索结果列表

        Raises:
            Exception: 当搜索失败时抛出
        """
        try:
            # 设置默认输出字段
            output_fields = output_fields if output_fields else ["*"]

            # 构建过滤条件
            filter_expr = f"doc_id in {doc_ids}"

            logger.debug(f"[Milvus 检索] filter: {filter_expr}")

            # 构建搜索参数
            search_params = {"metric_type": "IP", "params": {}}

            # 迭代检索
            results_iterator = self.client.search_iterator(
                collection_name=self.collection_name,
                data=[query_vector],  # 查询向量列表
                anns_field="seg_dense_vector",  # 向量字段名
                batch_size=1000,  # 每批返回数量,默认 1000
                limit=-1,  # 返回所有检索结果
                search_params=search_params,  # 搜索参数
                output_fields=output_fields,  # 返回字段
                filter=filter_expr,  # 过滤条件
            )

            logger.info("[FLAT Milvus] 向量检索迭代器创建成功")
            return results_iterator

        except Exception as e:
            logger.error(f"[FLAT Milvus] 向量搜索检索失败: {str(e)}")
            return None

    def full_text_search(
        self, query_text: str, doc_ids: list[str], output_fields: list[str] = None
    ) -> SearchIteratorV2 | SearchIterator | None:
        """
        执行全文检索(BM25)

        Args:
            query_text: 查询文本
            doc_ids: 文档 ID
            output_fields: 返回字段

        Returns:
           SearchIteratorV2 | SearchIterator | None: 迭代器或 None

        Raises:
            Exception: 当搜索失败时抛出
        """
        try:
            # 设置默认输出字段
            output_fields = output_fields if output_fields else ["*"]

            # 构建搜索参数
            search_params = {"metric_type": "BM25", "params": {}}

            # 构建过滤条件
            filter_expr = f"doc_id in {doc_ids}"

            iterator = self.client.search_iterator(
                collection_name=self.collection_name,
                data=[query_text],
                anns_field="seg_sparse_vector",
                search_params=search_params,
                filter=filter_expr,
                limit=-1,
                output_fields=output_fields,
            )

            logger.info("[FLAT Milvus] 全文检索迭代器创建成功")
            return iterator
        except Exception as e:
            logger.error(f"[FLAT Milvus] 全文搜索检索失败: {str(e)}")
            return None

    def _less_hybrid_search(
        self,
        doc_id_list: list[str],
        query_text: str,
        query_vector: list[float],
        limit: int,
        output_fields: list[str] = None,
    ) -> list[list[dict]]:
        """
        Milvus 混合检索(根据doc_id)

        Args:
            doc_id_list: 文档 ID 列表
            query_text: 查询文本
            query_vector: 查询向量
            limit: 最终输出数量
            output_fields: 输出字段

        Returns:
            List[List[dict]]: 混合检索后的结果列表,
        """
        try:
            # 构建过滤条件
            filter_expr = f"doc_id in {doc_id_list}"

            # 创建向量搜索请求
            similar_param = {"metric_type": "IP", "params": {}}
            search_vector = {
                "data": [query_vector],
                "anns_field": "seg_dense_vector",
                "param": similar_param,
                "limit": 50,
                "expr": filter_expr,
            }
            # 执行向量 ANN 检索请求
            vector_requtst = AnnSearchRequest(**search_vector)

            # 创建全文搜索请求
            text_param = {"metric_type": "BM25", "params": {"drop_ratio_search": 0.2}}
            search_text = {
                "data": [query_text],
                "anns_field": "seg_sparse_vector",
                "param": text_param,
                "limit": 50,
                "expr": filter_expr,
            }
            # 执行全文 ANN 检索请求
            text_request = AnnSearchRequest(**search_text)

            # 执行混合搜索
            ranker = WeightedRanker(0.7, 0.3)  # 设置向量检索和全文检索的权重
            reqs = [vector_requtst, text_request]
            res = self.client.hybrid_search(
                collection_name=self.collection_name,
                reqs=reqs,
                ranker=ranker,
                limit=limit,
                output_fields=output_fields,
            )

            return res

        except Exception as e:
            logger.error(f"[FLAT Milvus] 混合检索失败: {str(e)}")
            return [[]]

    def _batch_hybrid_search(self, batch_size: int, **kwargs) -> list[list[dict]]:
        """
        Milvus 批次混合检索(doc_id)

        Args:
            batch_size: 批次
            **kwargs: 参数集合,包括: 文档 ID 列表\查询文本\查询向量\文档数量\输出字段

        Returns:
            List[dict]:
        """

        try:
            all_results = []

            for i in range(0, len(kwargs.get("doc_id_list")), batch_size):
                batch_doc_ids = kwargs.get("doc_id_list")[i : i + batch_size]
                res = self._less_hybrid_search(
                    doc_id_list=batch_doc_ids,
                    query_text=kwargs.get("query_text"),
                    query_vector=kwargs.get("query_vector"),
                    limit=kwargs.get("limit"),
                    output_fields=kwargs.get("output_fields"),
                )
                all_results += res[0]

            all_results.sort(key=lambda x: x["distance"], reverse=True)

            return [all_results[:limit]]
        except Exception as e:
            logger.error(f"[FLAT Milvus] 批次混合检索失败: {str(e)}")
            return [[]]

    def optimized_hybrid_search(
        self,
        doc_id_list: list[str],
        query_text: str,
        query_vector: list[float],
        limit: int,
        output_fields: list[str] = None,
    ) -> list[list[dict]]:
        """
        自动选择分批或单批混合检索

        Args:
            doc_id_list: 文档 ID 列表
            query_text: 查询文本
            query_vector: 查询向量
            limit: 最终返回数量
            output_fields: 输出字段, 默认

        Returns:
            list[list[dict]]:
        """
        try:
            # 处理输出字段
            output_fields = (
                output_fields
                if output_fields
                else GlobalConfig.MILVUS_CONFIG["output_fields"]
            )

            # 设置批次
            batch_size = GlobalConfig.MILVUS_CONFIG["search_batch_size"]

            # 组合参数:
            params = {
                "doc_id_list": doc_id_list,
                "query_text": query_text,
                "query_vector": query_vector,
                "limit": limit,
                "output_fields": output_fields,
            }

            if len(doc_id_list) > batch_size:
                return self._batch_hybrid_search(batch_size=batch_size, **params)

            else:
                return self._less_hybrid_search(**params)

        except Exception as e:
            logger.error(f"[FLAT Milvus] 混合检索失败: {str(e)}")
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
        required_fields = [
            field["name"]
            for field in schema_config["fields"]
            if field["name"] != "seg_sparse_vector"
        ]

        for idx, item in enumerate(data):
            # 检查必须字段
            missing_fields = set(required_fields) - set(item.keys())
            if missing_fields:
                raise ValueError(
                    f"[FLAT Milvus] 第 {idx + 1} 条数据缺少必须字段：{missing_fields}"
                )

            # 验证向量字段
            if (
                not isinstance(item["seg_dense_vector"], list)
                or len(item["seg_dense_vector"]) != 1024
            ):
                raise ValueError(
                    f"[FLAT Milvus] 第 {idx + 1} 条数据的 seg_dense_vector 字段必须是 1024维的浮点数列表"
                )

    def get_collection_stats(self) -> dict[str, Any]:
        """
        获取集合统计信息

        Returns:
            Dict[str, Any]: 集合统计信息
        """
        try:
            stats = self.client.get_collection_stats(
                collection_name=self.collection_name
            )
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            load_state = self.client.get_load_state(
                collection_name=self.collection_name
            )

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
                logger.warning(
                    f"[FLAT Milvus] Collection {self.collection_name} 不存在"
                )
                return True

            if not force:
                logger.warning(
                    f"[FLAT Milvus] 即将删除集合 {self.collection_name}, 此操作不可恢复！"
                )
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
            result: dict[str, int] = self.client.delete(
                collection_name=self.collection_name, ids=doc_id
            )

            # 确保删除操作被持久化
            self.client.flush(collection_name=self.collection_name)

            logger.info(
                f"Milvus 数据删除成功, 共 {result['delete_count'] - 1} 条, doc_id={doc_id}"
            )
            return result["delete_count"]

        except Exception as e:
            logger.error(f"Milvus 数据删除失败: {str(e)}")
            return False

    def exists(self) -> bool:
        """
        检查集合是否存在

        Returns:
            bool: 集合是否存在
        """
        return self.client.has_collection(self.collection_name)

    def close(self):
        """关闭 Milvus 客户端"""
        self.client.close()


if __name__ == "__main__":
    from rich import print

    # 测试 FLAT collection 创建
    logger.info("开始测试 FLAT Collection 创建...")

    try:
        # 创建管理器
        flat_manager = FlatCollectionManager()

        # 删除 collection
        # flat_manager.drop_collection(True)

        # # 验证索引信息
        # collection_info = flat_manager.client.describe_collection(
        #     collection_name=flat_manager.collection_name
        # )
        # print(collection_info)
        # print("=" * 60)
        # index_info = flat_manager.client.describe_index(
        #     collection_name=flat_manager.collection_name, index_name="seg_sparse_vector"
        # )
        # print(index_info)
        #
        # print("=" * 60)
        #
        # # 验证数据插入
        # results = flat_manager.client.query(
        #     collection_name=flat_manager.collection_name,
        #     filter="doc_id == '308802d4082973cf8c3a548413585e753b4d37ffa8f8e16a3a005e8023066e52'",
        #     output_fields=["seg_content", "doc_id"],
        # )
        # print(results)
        # print("=" * 60)
        #
        # # # 测试稀疏向量
        # search_params = {"params": {"drop_ratio_search": 0.2}}
        #
        # search_results = flat_manager.client.search(
        #     collection_name=flat_manager.collection_name,
        #     data=["红楼梦"],
        #     anns_field="seg_sparse_vector",
        #     search_params=search_params,
        #     limit=5,
        #     output_fields=["seg_content", "doc_id"],
        # )
        # print(search_results)
        # print("=" * 60)

        # 初始化embedding
        embedding_manager = EmbeddingManager()
        # 测试混合检索
        hybrid_res: list[list[dict]] = flat_manager.optimized_hybrid_search(
            doc_id_list=[
                "308802d4082973cf8c3a548413585e753b4d37ffa8f8e16a3a005e8023066e52",
            ],
            query_text="红色",
            query_vector=embedding_manager.embed_text("红色"),
            limit=2,
        )
        print(len(hybrid_res))
        print(hybrid_res)
        print("=" * 60)
        # 获取统计信息
        # stats = flat_manager.get_collection_stats()
        # logger.info(f"[FLAT Milvus] Collection 统计信息：{stats}")

    except Exception as e:
        logger.error(f"[FLAT Milvus] 测试过程中出现错误：{str(e)}")
