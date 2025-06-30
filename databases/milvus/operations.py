"""向量库操作"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from databases.milvus.connection import MilvusDB
from utils.log_utils import logger
from config.global_config import GlobalConfig
import json


class VectorOperation:
    """向量库操作类"""

    def __init__(self):
        """初始化向量库操作类"""
        try:
            # 初始化 Milvus 数据库连接
            self.milvus = MilvusDB()
            # 初始化数据库和集合
            self.milvus.init_database()
            logger.info("向量库操作类初始化完成")

        except Exception as e:
            logger.error(f"向量库操作类初始化失败: {str(e)}")
            raise

    def flush(self):
        """执行 Milvus 的 flush 操作，确保数据被持久化"""
        try:
            self.milvus.client.flush(self.milvus.collection_name)
            logger.info("Milvus 数据已成功持久化")
        except Exception as e:
            logger.error(f"Milvus flush 操作失败: {str(e)}")
            raise

    def _validate_milvus_data(self, data: List[Dict[str, Any]]) -> None:
        """验证 Milvus 数据格式

        Args:
            data (List[Dict[str, Any]]): 要验证的数据列表

        Raises:
            ValueError: 当数据格式不符合要求时抛出
        """
        # 从配置文件中读取 Milvus schema 以获取必需字段
        schema_path = GlobalConfig.PATHS.get("milvus_schema_path")
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_config = json.load(f)

        # 提取字段名作为必需字段列表
        required_fields = [field["name"] for field in schema_config["fields"]]

        for idx, item in enumerate(data):
            # 验证必需字段
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                raise ValueError(f"第 {idx + 1} 条数据缺少必需字段: {missing_fields}")

            # 验证字段类型和格式
            if not isinstance(item["vector"], list) or len(item["vector"]) != 1024:
                raise ValueError(f"第 {idx + 1} 条数据的 vector 字段必须是 1024 维的浮点数列表")

            # 验证字符串类型字段
            string_fields = ["seg_id", "seg_parent_id", "doc_id", "seg_content",
                             "seg_type", "permission_ids", "create_time", "update_time"]
            for field in string_fields:
                if field in item and not isinstance(item[field], str):
                    raise ValueError(
                        f"第 {idx + 1} 条数据的 {field} 字段必须是字符串, 内容: {item[field]}, 类型: {type(item[field])}")

            # 验证 metadata 字段
            if "metadata" in item and not isinstance(item["metadata"], dict):
                raise ValueError(f"第 {idx + 1} 条数据的 metadata 字段必须是字典")

    def insert_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """批量插入数据

        Args:
            data (List[Dict[str, Any]]): 要插入的数据列表

        Returns:
            List[str]: 插入成功的 seg_id 列表

        Raises:
            ValueError: 当数据格式不符合要求时抛出
        """

        try:
            # 验证数据格式
            self._validate_milvus_data(data)

            # 插入数据
            inserted_ids = self.milvus.insert_data(data)
            if not inserted_ids:
                raise ValueError("插入数据失败：未返回插入ID")

            return inserted_ids
        except Exception as e:
            logger.error(f"插入数据失败: {str(e)}")
            raise  # 向上抛出异常

    def insert_single(self, data: Dict[str, Any]) -> Optional[str]:
        """插入单条数据

        Args:
            data (Dict[str, Any]): 要插入的数据

        Returns:
            Optional[str]: 插入成功的 seg_id，失败返回 None
        """
        result = self.insert_data([data])
        return result[0] if result else None

    def search_by_doc_id(self, doc_id: str) -> List[Dict[str, Any]]:
        """根据文档ID检索数据

        Args:
            doc_id (str): 文档ID

        Returns:
            List[Dict[str, Any]]: 检索结果列表
        """
        try:
            results = self.milvus.client.get(
                collection_name=self.milvus.collection_name,
                ids=doc_id,
                output_fields=["*"],
            )
            logger.info(f"Milvus 检索到 {len(results)} 条记录, doc_id={doc_id}")
            return results
        except Exception as e:
            logger.error(f"根据文档ID检索失败: {str(e)}")
            return []

    def search_by_seg_id(self, seg_id: str) -> Optional[Dict[str, Any]]:
        """根据段落ID检索数据

        Args:
            seg_id (str): 段落ID

        Returns:
            Optional[Dict[str, Any]]: 检索到的实体结果，未找到返回 None
        """
        try:
            results = self.milvus.client.get(
                collection_name=self.milvus.collection_name,
                ids=seg_id,
                output_fields=["*"],
            )
            return None
        except Exception as e:
            logger.error(f"根据段落ID检索失败: {str(e)}")
            return None

    def update_by_doc_id(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """根据文档ID更新数据

        Args:
            doc_id (str): 文档ID
            data (Dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        try:
            # 添加更新时间
            data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 更新数据
            self.milvus.client.upsert(
                collection_name=self.milvus.collection_name,
                data=[{**data, 'doc_id': doc_id}]
            )
            logger.info(f"成功更新文档 {doc_id} 的数据")
            return True
        except Exception as e:
            logger.error(f"更新数据失败: {str(e)}")
            return False

    def update_by_seg_id(self, seg_id: str, data: Dict[str, Any]) -> bool:
        """根据段落ID更新数据

        Args:
            seg_id (str): 段落ID
            data (Dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        try:
            # 添加更新时间
            data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 更新数据
            self.milvus.client.upsert(
                collection_name=self.milvus.collection_name,
                data=[{**data, 'seg_id': seg_id}]
            )
            logger.info(f"成功更新段落 {seg_id} 的数据")
            return True
        except Exception as e:
            logger.error(f"更新数据失败: {str(e)}")
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
            result: Dict[str, int] = self.milvus.client.delete(
                collection_name=self.milvus.collection_name,
                ids=doc_id
            )

            # 确保删除操作被持久化
            self.flush()

            logger.info(f"Milvus 数据删除成功, 共 {result['delete_count']-1} 条, doc_id={doc_id}")
            return result['delete_count']

        except Exception as e:
            logger.error(f"Milvus 数据删除失败: {str(e)}")
            return False

    def delete_by_seg_id(self, seg_id: str) -> bool:
        """根据段落ID删除数据

        Args:
            seg_id (str): 段落ID

        Returns:
            bool: 是否删除成功
        """
        try:
            self.milvus.client.delete(
                collection_name=self.milvus.collection_name,
                filter=f'seg_id == "{seg_id}"'
            )
            logger.info(f"成功删除段落 {seg_id} 的数据")
            return True
        except Exception as e:
            logger.error(f"删除数据失败: {str(e)}")
            return False


def test_milvus_operations():
    """测试 Milvus 操作类的基本功能"""
    vector_op = VectorOperation()

    # 测试数据
    test_data = {
        "doc_id": "test_doc_001",
        "seg_id": "test_seg_001",
        "seg_parent_id": "test_parent_001",
        "vector": [0.1] * 1024,  # 1024维向量
        "seg_content": "这是一个测试文档的内容",
        "seg_type": "text",
        "permission_ids": "['dept1', 'dept2']",
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metadata": {"key": "value"}
    }

    # 测试插入
    logger.info("测试插入数据...")
    seg_id = vector_op.insert_single(test_data)
    assert seg_id is not None, "插入数据失败"

    # 测试检索
    logger.info("测试检索数据...")
    doc_results = vector_op.search_by_doc_id("test_doc_001")
    assert len(doc_results) > 0, "根据文档ID检索失败"

    segment_result = vector_op.search_by_seg_id("test_seg_001")
    assert segment_result is not None, "根据段落ID检索失败"

    # 测试更新
    logger.info("测试更新数据...")
    update_data = {
        "seg_content": "更新后的内容",
        "metadata": {"key": "updated_value"}
    }
    assert vector_op.update_by_doc_id("test_doc_001", update_data), "更新文档数据失败"
    assert vector_op.update_by_seg_id("test_seg_001", update_data), "更新段落数据失败"

    # 验证更新结果
    updated_doc = vector_op.search_by_doc_id("test_doc_001")[0]
    assert updated_doc["seg_content"] == "更新后的内容", "文档更新验证失败"

    # 测试删除
    logger.info("测试删除数据...")
    assert vector_op.delete_by_doc_id("test_doc_001"), "删除文档数据失败"

    # 验证删除结果
    deleted_doc = vector_op.search_by_doc_id("test_doc_001")
    assert len(deleted_doc) == 0, "文档删除验证失败"


def run_all_tests():
    """运行所有测试"""
    try:
        test_milvus_operations()
        logger.info("所有测试完成！")
    except AssertionError as e:
        logger.error(f"测试失败: {str(e)}")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")


if __name__ == "__main__":
    run_all_tests()
