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
from typing import Dict, Any, List

from pymilvus import connections, MilvusClient, FieldSchema, DataType, CollectionSchema

from config.global_config import GlobalConfig
from config.milvus_config import MilvusConfig
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

    def __init__(self, collection_name="rag_flat"):
        """初始化 FLAT Collection 管理器

        Args:
            collection_name (str): 集合名称，默认为 "rag_flat"
        """
        self.collection_name = collection_name
        self.config = MilvusConfig()

        # 初始化 Milvus 客户端
        self._init_client()

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
            logger.info(f"[FLAT Milvus] Collection 管理器初始化成功，数据库： {self.db_name}")

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

    def init_collection(self, force_recreate: bool = False) -> bool:
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
        required_fields = [field['name'] for field in schema_config['fields']]

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
        flat_manager.init_collection()

        # 删除 collection
        # flat_manager.drop_collection(True)

        # 获取统计信息
        stats = flat_manager.get_collection_stats()
        logger.info(f"[FLAT Milvus] Collection 统计信息：{stats}")

    except Exception as e:
        logger.error(f"[FLAT Milvus] 测试过程中出现错误：{str(e)}")


