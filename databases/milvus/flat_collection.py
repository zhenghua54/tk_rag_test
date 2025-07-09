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
from typing import Dict, Any, List

from pymilvus import connections, MilvusClient, FieldSchema, DataType, CollectionSchema, Function, FunctionType

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
        if hasattr(self, '_initialized') and self._initialized:
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
                uri=GlobalConfig.MILVUS_CONFIG["uri"],
                token=GlobalConfig.MILVUS_CONFIG.get("token")
            )

            # 建立连接
            connections.connect(
                alias='default',
                host=GlobalConfig.MILVUS_CONFIG["host"],
                port=GlobalConfig.MILVUS_CONFIG["port"],
                token=GlobalConfig.MILVUS_CONFIG.get("token")
            )

            self.db_name = GlobalConfig.MILVUS_CONFIG["db_name"]
            self._current_db = 'default'  # 初始化为 default 数据库

            logger.info(f"[FLAT Milvus] Collection 管理器初始化成功，数据库： {self._current_db}")

        except  Exception as e:
            logger.error(f"[FLAT Milvus] Collection 管理器初始化失败: {e}")
            raise

    @staticmethod
    def _load_schema() -> Dict[str, Any]:
        """加载集合 schema 配置

        使用与原有 collection 相同的字段结构，确保数据兼容性。

        Returns:
            Dict[str, Any]: schema 配置字典
        """
        schema_path = GlobalConfig.PATHS.get("milvus_flat_schema")
        with open(schema_path, "r", encoding='utf-8') as f:
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
                logger.info(f"[FLAT Milvus] 切换Database成功!")

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
        for field_config in schema_config['fields']:
            field = FieldSchema(
                name=field_config['name'],
                dtype=getattr(DataType, field_config['type']),
                description=field_config.get('description', ''),
                is_primary=field_config.get('is_primary', False),
                **{k: v for k, v in field_config.items()
                   if k not in ['name', 'type', 'description', 'is_primary']}
            )
            fields.append(field)

        # 创建 schema
        schema = CollectionSchema(
            fields=fields,
            description=schema_config.get('description', 'FLAT 索引向量库，搜索结果稳定性高'),
            enable_dynamic_field=schema_config.get('enable_dynamic_field', False)
        )

        # 创建函数
        if 'functions' in schema_config:
            # 添加函数到 schema
            for func in schema_config['functions']:
                # 创建 BM25 函数
                function = Function(
                    name=func['name'],
                    input_field_names=func['input_field_names'],
                    output_field_names=func['output_field_names'],
                    function_type=getattr(FunctionType, func['function_type'])
                )
                schema.add_function(function)

        # 创建集合
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema
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

            logger.info(f"[FLAT Milvus] 正在为向量字段创建 FLAT 索引 ...")
            self.client.create_index(
                collection_name=self.collection_name,
                index_params=index_params
            )

            # 验证索引创建
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            logger.info(f'[FLAT Milvus] Collection {self.collection_name} 索引列表: {indexes}')

            # 加载集合
            self.client.load_collection(collection_name=self.collection_name)
            logger.info(f"[FLAT Milvus] FLAT 索引创建成功, Collection 已加载")

        except Exception as e:
            logger.error(f"[FLAT Milvus] 创建 FLAT 索引失败：{str(e)}")
            raise

    def insert_data(self, data: List[Dict[str, Any]]) -> List[str]:
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
            result = self.client.insert(
                collection_name=self.collection_name,
                data=data
            )

            inserted_ids = result['ids']

            # 执行持久化操作，确保数据持久化
            self.client.flush(collection_name=self.collection_name)

            logger.info(f"[FLAT Milvus] Collection 数据插入成功，共 {len(inserted_ids)} 条")
            return inserted_ids
        except Exception as e:
            logger.error(f"[FLAT Milvus] Collection 数据插入失败：{str(e)}")
            raise

    def search(self, query_vector: List[float], top_k: int = 10,
               output_fields: List[str] = None) -> List[Dict[str, Any]]:
        """
        执行向量相似性搜索

        使用项目统一的 EmbeddingManager 生成查询向量，确保向量归一化一致性。

        Args:
            query_vector: 查询文本向量(1024维浮点数)
            top_k: 返回结果数量，默认20
            output_fields: 返回字段，默认使用配置的输出字段

        Returns:
            List[Dict[str, Any]]: 检索结果列表，包含 seg_id, score, seg_content 等字段

        Raises:
            ValueError: 当查询向量格式不正确时抛出
            Exception: 当搜索失败时抛出
        """
        try:
            # 验证查询向量格式
            if not isinstance(query_vector, list) or len(query_vector) != 1024:
                raise ValueError(
                    f"查询向量必须是1024维的浮点数列表，当前维度: {len(query_vector) if isinstance(query_vector, list) else '非列表'}")

            # 设置默认输出字段
            if output_fields is None:
                output_fields = GlobalConfig.MILVUS_CONFIG['output_fields']

            # 构建搜索参数
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],  # 查询向量列表
                anns_field="seg_dense_vector",  # 向量字段名
                search_params={"metric_type": "IP", "params": {}},  # 搜索参数
                limit=top_k,  # 返回结果数量
                output_fields=output_fields,  # 返回字段
            )

            # 处理搜索结果
            if results and len(results) > 0:
                # 单个查询向量，只会有一个 hits，取第一个结果列表
                search_results = results[0]
                logger.info(f"[FLAT Milvus] 向量搜索成功，返回 {len(search_results)} 条结果")
                return search_results
            else:
                logger.warning(f"[FLAT Milvus] 向量搜索未返回结果")
                return []

        except Exception as e:
            logger.error(f"[FLAT Milvus] 向量搜索未返回结果: {str(e)}")
            return []

    def _validate_data(self, data: List[Dict[str, Any]]):
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
        required_fields = [field['name'] for field in schema_config['fields'] if field['name'] != 'seg_sparse_vector']

        for idx, item in enumerate(data):
            # 检查必须字段
            missing_fields = set(required_fields) - set(item.keys())
            if missing_fields:
                raise ValueError(f"[FLAT Milvus] 第 {idx + 1} 条数据缺少必须字段：{missing_fields}")

            # 验证向量字段
            if not isinstance(item['seg_dense_vector'], list) or len(item['seg_dense_vector']) != 1024:
                raise ValueError(f"[FLAT Milvus] 第 {idx + 1} 条数据的 seg_dense_vector 字段必须是 1024维的浮点数列表")

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息

        Returns:
            Dict[str, Any]: 集合统计信息
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
                "config": self.config.get_config_summary()
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
                if confirm.lower() != 'y':
                    logger.info("已取消删除操作")
                    return False

            self.client.drop_collection(self.collection_name)
            logger.info(f"[FLAT Milvus] Collection {self.collection_name} 已删除")
            return True
        except Exception as e:
            logger.error(f"[FLAT MIlvus] 删除 Collection 失败：{str(e)}")
            return False

    def exists(self) -> bool:
        """
        检查集合是否存在

        Returns:
            bool: 集合是否存在
        """
        return self.client.has_collection(self.collection_name)


if __name__ == '__main__':
    # 测试 FLAT collection 创建
    logger.info("开始测试 FLAT Collection 创建...")

    try:
        # 创建管理器
        flat_manager = FlatCollectionManager()

        # 删除 collection
        # flat_manager.drop_collection(True)

        # 获取统计信息
        stats = flat_manager.get_collection_stats()
        logger.info(f"[FLAT Milvus] Collection 统计信息：{stats}")

    except Exception as e:
        logger.error(f"[FLAT Milvus] 测试过程中出现错误：{str(e)}")
