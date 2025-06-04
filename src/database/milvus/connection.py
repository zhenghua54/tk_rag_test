""" Milvus 数据库操作工具 """

from typing import List, Dict, Any
import json
from pathlib import Path
from pymilvus import MilvusClient, CollectionSchema, FieldSchema, DataType, Collection, connections

from config.settings import Config
from src.utils.common.logger import logger


class MilvusDB:
    def __init__(self):
        """初始化 Milvus 客户端

        从配置文件中读取 Milvus 服务器配置信息并初始化客户端连接
        """
        self.client = MilvusClient(
            uri=Config.MILVUS_CONFIG["uri"],
            token=Config.MILVUS_CONFIG["token"]
        )
        self.db_name = Config.MILVUS_CONFIG["db_name"]

        connections.connect(
            alias="default",
            host=Config.MILVUS_CONFIG["host"],
            port=Config.MILVUS_CONFIG["port"],
            token=Config.MILVUS_CONFIG["token"],
            db_name=self.db_name
        )
        self.collection_name = Config.MILVUS_CONFIG["collection_name"]
        self.collection = None  # 集合不存在时,初始化时不会创建集合实例

    def _load_schema(self) -> Dict:
        """加载 Milvus schema 配置"""
        schema_path = Config.MILVUS_CONFIG["schema_path"]
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def init_database(self) -> None:
        """初始化数据库和集合"""
        # 创建数据库（如果不存在）
        db_list = self.client.list_databases()
        if self.db_name not in db_list:
            logger.info(f"数据库 {self.db_name} 不存在，正在创建...")
            self.client.create_database(db_name=self.db_name)

        # 切换到指定数据库
        logger.info(f"切换到数据库 {self.db_name}...")
        self.client.using_database(self.db_name)

        # 检查集合是否存在
        collections = self.client.list_collections()
        if self.collection_name not in collections:
            # 如果集合不存在，则创建新的集合
            logger.info(f"集合 {self.collection_name} 不存在，正在创建...")
            self._create_collection()
        # else:
        # logger.info(f"集合 {self.collection_name} 已存在，跳过创建")

        # 初始化完成后设置 collection 实例
        self.collection = Collection(self.collection_name)

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
            description="企业知识库文档向量库 (支持文档管理 + 部门/角色过滤)",
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
        index_params.add_index(**Config.MILVUS_CONFIG['index_params'])

        logger.info(f"正在为字段 '{Config.MILVUS_CONFIG['vector_field']}' 创建索引...")
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
            logger.info(f"成功插入 {len(data)} 条数据,主键 ID : {inserted_ids}")
            return inserted_ids
        except Exception as e:
            logger.info(f"插入数据时出错: {str(e)}")
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

    def get_all_text_chunks(self) -> List[str]:
        """从 Milvus 集合中获取所有 text_chunk 字段内容"""
        # 查询所有记录的 text_chunk 字段
        results = self.collection.query(
            expr="",  # 无过滤条件,返回所有
            output_fields=["text_chunk"],
            limit=16384  # 设置一个足够大的限制
        )
        logger.info(f"从 Milvus 中获取到 {len(results)} 个 text_chunk 文本块")
        return [r["text_chunk"] for r in results if "text_chunk" in r]


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
