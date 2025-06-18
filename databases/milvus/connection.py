""" Milvus 数据库操作工具 """

from typing import List, Dict, Any
import json
from pymilvus import MilvusClient, CollectionSchema, FieldSchema, DataType, Collection, connections

from config.global_config import GlobalConfig
from utils.log_utils import logger


class MilvusDB:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MilvusDB, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化 Milvus 客户端

        从配置文件中读取 Milvus 服务器配置信息并初始化客户端连接
        """
        if self._initialized:
            return

        self._collection = None

        try:
            self.client = MilvusClient(
                uri=GlobalConfig.MILVUS_CONFIG["uri"],
                token=GlobalConfig.MILVUS_CONFIG["token"]
            )

            connections.connect(
                alias="default",
                host=GlobalConfig.MILVUS_CONFIG["host"],
                port=GlobalConfig.MILVUS_CONFIG["port"],
                token=GlobalConfig.MILVUS_CONFIG["token"],
            )

            self.db_name = GlobalConfig.MILVUS_CONFIG["db_name"]
            self.collection_name = GlobalConfig.MILVUS_CONFIG["collection_name"]
            self._initialized = True
        except Exception as e:
            logger.error(f"Milvus 客户端初始化失败: {str(e)}")
            raise

    @property
    def collection(self) -> Collection:
        """获取当前集合实例"""
        if self._collection is None or self._collection.name != self.collection_name:
            self._collection = Collection(self.collection_name)
        return self._collection

    def _load_schema(self) -> Dict:
        """加载 Milvus schema 配置"""
        schema_path = GlobalConfig.PATHS.get("milvus_schema_path")
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def init_database(self):
        """项目初始化时调用一次,初始化数据库和集合"""
        # 创建数据库（如果不存在）
        db_list = self.client.list_databases()
        if self.db_name not in db_list:
            logger.info(f"数据库 {self.db_name} 不存在，正在创建...")
            self.client.create_database(db_name=self.db_name)
        # 切换到指定数据库
        self.client.using_database(self.db_name)

        # 检查并创建集合
        collections = self.client.list_collections()
        if self.collection_name not in collections:
            logger.info(f"集合 {self.collection_name} 不存在，正在创建...")
            self._create_collection()

    def _create_collection(self) -> None:
        """创建集合和索引"""
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
                **{k: v for k, v in field_config.items()
                   if k not in ["name", "type", "description", "is_primary"]}
            )
            fields.append(field)

        # 创建 schema
        schema = CollectionSchema(
            fields=fields,
            description="天宽认知大模型文档向量库",
            enable_dynamic_field=True
        )

        # 创建集合
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema
        )
        logger.info(f"集合 {self.collection_name} 创建成功")

        # 创建索引
        self._create_index()

    def _create_index(self) -> None:
        """创建向量索引"""
        index_params = self.client.prepare_index_params()
        index_params.add_index(**GlobalConfig.MILVUS_CONFIG['index_params'])

        logger.info(f"正在为字段 '{GlobalConfig.MILVUS_CONFIG['vector_field']}' 创建索引...")
        self.client.create_index(
            collection_name=self.collection_name,
            index_params=index_params
        )

        indexes = self.client.list_indexes(collection_name=self.collection_name)
        logger.info(f"集合 {self.collection_name} 当前索引列表: {indexes}")

    def insert_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """插入数据到集合
        
        Args:
            data: 要插入的数据列表，每个元素是一个字典

        Returns:
            插入数据的主键 ID 列表

        Raises:
            ValueError: 当数据格式不符合要求输出
        """
        # 加载 schema 配置
        schema_config = self._load_schema()
        required_fields = [field["name"] for field in schema_config["fields"]]

        # 验证数据格式
        for idx, item in enumerate(data):
            missing_fields = set(required_fields) - set(item.keys())
            if missing_fields:
                raise ValueError(f"第 {idx + 1} 条数据缺少必要字段: {missing_fields}")

        try:
            result = self.client.insert(
                collection_name=self.collection_name,
                data=data
            )
            inserted_ids = result['ids']
            logger.info(f"Milvus 数据插入成功, 共 {len(data)} 条")
            return inserted_ids
        except Exception as e:
            logger.info(f"Milvus 数据插入出错: {str(e)}")
            raise

    def drop_collection(self, force: bool = False) -> None:
        """删除集合
        
        Args:
            force: 是否强制删除

        Raises:
            ValueError: 当集合不存在时抛出
        """
        if not self.client.has_collection(self.collection_name):
            raise ValueError(f"集合 {self.collection_name} 不存在")

        if not force:
            logger.warning(f"集合 {self.collection_name} 存在, 需要手动确认删除")
            confirm = input(f"确定要删除集合 {self.collection_name} 吗? 此操作不可恢复! (y/n): ")
            if confirm.lower() != 'y':
                logger.info("已取消删除操作")
                return

        try:
            self.client.drop_collection(self.collection_name)
            logger.info(f"集合 {self.collection_name} 已删除")
        except Exception as e:
            logger.error(f"删除集合时出错: {str(e)}")
            raise


def create_milvus_db() -> MilvusDB:
    """创建并初始化 Milvus 数据库实例
    
    Returns:
        MilvusDB 实例
    """
    db = MilvusDB()
    db.init_database()
    return db


if __name__ == "__main__":
    # 示例用法
    db = create_milvus_db()
    print("数据库初始化完成！")
    # db.drop_collection()
    # print("集合删除完成！")
