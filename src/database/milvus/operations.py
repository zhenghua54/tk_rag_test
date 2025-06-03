"""向量库操作"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from config.settings import Config
from src.database.milvus.connection import MilvusDB
from src.utils.common.logger import logger
from src.utils.common.args_validator import Validator


class VectorOperation:
    """向量库操作类"""

    def __init__(self):
        """初始化向量库操作类"""
        self.milvus = MilvusDB()
        self.milvus.init_database()

    def insert_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """批量插入数据

        Args:
            data (List[Dict[str, Any]]): 要插入的数据列表

        Returns:
            List[str]: 插入成功的 segment_id 列表
        """
        Validator.validate_list_not_empty(data, "data")
        Validator.validate_type(data, list, "data")

        try:
            # 添加时间戳
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in data:
                item['create_time'] = current_time
                item['update_time'] = current_time

            # 插入数据
            inserted_ids = self.milvus.insert_data(data)
            logger.info(f"成功插入 {len(data)} 条数据")
            return inserted_ids
        except Exception as e:
            logger.error(f"插入数据失败: {e}")
            return []

    def insert_single(self, data: Dict[str, Any]) -> Optional[str]:
        """插入单条数据

        Args:
            data (Dict[str, Any]): 要插入的数据

        Returns:
            Optional[str]: 插入成功的 segment_id，失败返回 None
        """
        Validator.validate_type(data, dict, "data")
        result = self.insert_data([data])
        return result[0] if result else None

    def search_by_doc_id(self, doc_id: str) -> List[Dict[str, Any]]:
        """根据文档ID检索数据

        Args:
            doc_id (str): 文档ID

        Returns:
            List[Dict[str, Any]]: 检索结果列表
        """
        Validator.validate_doc_id(doc_id)
        try:
            results = self.milvus.collection.query(
                expr=f'doc_id == "{doc_id}"',
                output_fields=["*"]
            )
            return results
        except Exception as e:
            logger.error(f"根据文档ID检索失败: {e}")
            return []

    def search_by_segment_id(self, segment_id: str) -> Optional[Dict[str, Any]]:
        """根据段落ID检索数据

        Args:
            segment_id (str): 段落ID

        Returns:
            Optional[Dict[str, Any]]: 检索结果，未找到返回 None
        """
        Validator.validate_segment_id(segment_id)
        try:
            results = self.milvus.collection.query(
                expr=f'segment_id == "{segment_id}"',
                output_fields=["*"]
            )
            return results[0] if results else None
        except Exception as e:
            logger.error(f"根据段落ID检索失败: {e}")
            return None

    def update_by_doc_id(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """根据文档ID更新数据

        Args:
            doc_id (str): 文档ID
            data (Dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        Validator.validate_doc_id(doc_id)
        Validator.validate_type(data, dict, "data")

        try:
            # 添加更新时间
            data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 更新数据
            self.milvus.collection.upsert(
                data=[{**data, 'doc_id': doc_id}]
            )
            logger.info(f"成功更新文档 {doc_id} 的数据")
            return True
        except Exception as e:
            logger.error(f"更新数据失败: {e}")
            return False

    def update_by_segment_id(self, segment_id: str, data: Dict[str, Any]) -> bool:
        """根据段落ID更新数据

        Args:
            segment_id (str): 段落ID
            data (Dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        Validator.validate_segment_id(segment_id)
        Validator.validate_type(data, dict, "data")

        try:
            # 添加更新时间
            data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 更新数据
            self.milvus.collection.upsert(
                data=[{**data, 'segment_id': segment_id}]
            )
            logger.info(f"成功更新段落 {segment_id} 的数据")
            return True
        except Exception as e:
            logger.error(f"更新数据失败: {e}")
            return False

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """根据文档ID删除数据

        Args:
            doc_id (str): 文档ID

        Returns:
            bool: 是否删除成功
        """
        Validator.validate_doc_id(doc_id)
        try:
            self.milvus.collection.delete(
                expr=f'doc_id == "{doc_id}"'
            )
            logger.info(f"成功删除文档 {doc_id} 的数据")
            return True
        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            return False

    def delete_by_segment_id(self, segment_id: str) -> bool:
        """根据段落ID删除数据

        Args:
            segment_id (str): 段落ID

        Returns:
            bool: 是否删除成功
        """
        Validator.validate_segment_id(segment_id)
        try:
            self.milvus.collection.delete(
                expr=f'segment_id == "{segment_id}"'
            )
            logger.info(f"成功删除段落 {segment_id} 的数据")
            return True
        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            return False

def test_milvus_operations():
    """测试 Milvus 操作类的基本功能"""
    vector_op = VectorOperation()
    
    # 测试数据
    test_data = {
        "doc_id": "test_doc_001",
        "segment_id": "test_seg_001",
        "vector": [0.1] * 1024,  # 1024维向量
        "document_name": "测试文档",
        "summary_text": "这是一个测试文档的摘要",
        "type": "text",
        "page_idx": 1,
        "principal_ids": "['dept1', 'dept2']",
        "metadata": {"key": "value"}
    }
    
    # 测试插入
    logger.info("测试插入数据...")
    segment_id = vector_op.insert_single(test_data)
    assert segment_id is not None, "插入数据失败"
    
    # 测试检索
    logger.info("测试检索数据...")
    doc_results = vector_op.search_by_doc_id("test_doc_001")
    assert len(doc_results) > 0, "根据文档ID检索失败"
    
    segment_result = vector_op.search_by_segment_id("test_seg_001")
    assert segment_result is not None, "根据段落ID检索失败"
    
    # 测试更新
    logger.info("测试更新数据...")
    update_data = {
        "summary_text": "更新后的摘要",
        "metadata": {"key": "updated_value"}
    }
    assert vector_op.update_by_doc_id("test_doc_001", update_data), "更新文档数据失败"
    assert vector_op.update_by_segment_id("test_seg_001", update_data), "更新段落数据失败"
    
    # 验证更新结果
    updated_doc = vector_op.search_by_doc_id("test_doc_001")[0]
    assert updated_doc["summary_text"] == "更新后的摘要", "文档更新验证失败"
    
    # 测试删除
    logger.info("测试删除数据...")
    assert vector_op.delete_by_doc_id("test_doc_001"), "删除文档数据失败"
    
    # 验证删除结果
    deleted_doc = vector_op.search_by_doc_id("test_doc_001")
    assert len(deleted_doc) == 0, "文档删除验证失败"
    
    logger.info("所有测试通过！")


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