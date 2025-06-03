"""向量库操作"""

from typing import List, Dict, Optional
from datetime import datetime
import numpy as np
from config.settings import Config
from src.utils.common.logger import logger
from src.utils.common.args_validator import Validator
from pymilvus import connections, Collection, utility


class MilvusOperation:
    """向量库操作类"""

    def __init__(self):
        """初始化向量库连接"""
        self.collection_name = Config.MILVUS_CONFIG['collection_name']
        self._connect()
        self._init_collection()

    def _connect(self):
        """连接 Milvus 服务器"""
        try:
            connections.connect(
                alias="default",
                host=Config.MILVUS_CONFIG['host'],
                port=Config.MILVUS_CONFIG['port']
            )
            logger.info("Milvus 连接成功")
        except Exception as e:
            logger.error(f"Milvus 连接失败: {e}")
            raise

    def _init_collection(self):
        """初始化集合"""
        try:
            if not utility.has_collection(self.collection_name):
                raise ValueError(f"集合 {self.collection_name} 不存在，请先运行初始化脚本")
            self.collection = Collection(self.collection_name)
            logger.info(f"集合 {self.collection_name} 加载成功")
        except Exception as e:
            logger.error(f"初始化集合失败: {e}")
            raise

    def insert_vectors(self, vectors: List[Dict]) -> bool:
        """批量插入向量数据

        Args:
            vectors (List[Dict]): 向量数据列表

        Returns:
            bool: 插入是否成功
        """
        try:
            Validator.validate_list_not_empty(vectors, "vectors")
            
            # 准备数据
            data = {
                "vector": [],
                "segment_id": [],
                "doc_id": [],
                "document_name": [],
                "summary_text": [],
                "type": [],
                "page_idx": [],
                "principal_ids": [],
                "create_time": [],
                "update_time": [],
                "metadata": []
            }
            
            # 填充数据
            for vector in vectors:
                # 将向量转换为 numpy 数组
                if isinstance(vector.get("vector"), list):
                    vector["vector"] = np.array(vector["vector"], dtype=np.float32)
                for key in data.keys():
                    data[key].append(vector.get(key, ""))
            
            # 插入数据
            self.collection.insert(data)
            self.collection.flush()
            logger.info(f"成功插入 {len(vectors)} 条向量数据")
            return True
        except Exception as e:
            logger.error(f"插入向量数据失败: {e}")
            return False

    def search_vectors(self, query_vector: List[float], top_k: int = 5) -> List[Dict]:
        """搜索相似向量

        Args:
            query_vector (List[float]): 查询向量
            top_k (int, optional): 返回结果数量. Defaults to 5.

        Returns:
            List[Dict]: 相似向量列表
        """
        try:
            Validator.validate_list_not_empty(query_vector, "query_vector")
            
            # 将查询向量转换为 numpy 数组
            query_vector = np.array(query_vector, dtype=np.float32)
            
            # 加载集合
            self.collection.load()
            
            # 执行搜索
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10}
            }
            results = self.collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=["segment_id", "doc_id", "document_name", "summary_text", "type", "page_idx", "metadata"]
            )
            
            # 处理结果
            hits = []
            for hit in results[0]:
                hit_dict = {
                    "score": hit.score,
                    "segment_id": hit.entity.get("segment_id"),
                    "doc_id": hit.entity.get("doc_id"),
                    "document_name": hit.entity.get("document_name"),
                    "summary_text": hit.entity.get("summary_text"),
                    "type": hit.entity.get("type"),
                    "page_idx": hit.entity.get("page_idx"),
                    "metadata": hit.entity.get("metadata")
                }
                hits.append(hit_dict)
            
            return hits
        except Exception as e:
            logger.error(f"搜索向量失败: {e}")
            return []

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """根据文档ID删除向量数据

        Args:
            doc_id (str): 文档ID

        Returns:
            bool: 删除是否成功
        """
        try:
            Validator.validate_doc_id(doc_id)
            
            expr = f'doc_id == "{doc_id}"'
            self.collection.delete(expr)
            logger.info(f"成功删除文档 {doc_id} 的向量数据")
            return True
        except Exception as e:
            logger.error(f"删除向量数据失败: {e}")
            return False

    def delete_by_segment_id(self, segment_id: str) -> bool:
        """根据片段ID删除向量数据

        Args:
            segment_id (str): 片段ID

        Returns:
            bool: 删除是否成功
        """
        try:
            Validator.validate_segment_id(segment_id)
            
            expr = f'segment_id == "{segment_id}"'
            self.collection.delete(expr)
            logger.info(f"成功删除片段 {segment_id} 的向量数据")
            return True
        except Exception as e:
            logger.error(f"删除向量数据失败: {e}")
            return False

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        try:
            connections.disconnect("default")
            logger.info("Milvus 连接已关闭")
        except Exception as e:
            logger.error(f"关闭 Milvus 连接失败: {e}")
            
def test_milvus_operations():
    """测试 Milvus 操作类的基本功能"""
    try:
        # 初始化操作类
        with MilvusOperation() as milvus:
            # 测试数据
            test_vectors = [{
                "vector": np.array([0.1] * 1024, dtype=np.float32),  # bge-m3 模型向量维度为1024
                "segment_id": "test_segment_1",
                "doc_id": "test_doc_1",
                "document_name": "test_doc.pdf",
                "summary_text": "测试文档摘要",
                "type": "text",
                "page_idx": 1,
                "principal_ids": "test_principal",
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "metadata": {"key": "value"}
            }]
            
            # 测试插入
            assert milvus.insert_vectors(test_vectors), "向量插入失败"
            
            # 测试删除
            assert milvus.delete_by_doc_id("test_doc_1"), "按文档ID删除失败"
            assert milvus.delete_by_segment_id("test_segment_1"), "按片段ID删除失败"
            
            logger.info("Milvus 操作测试通过")
            return True
            
    except Exception as e:
        logger.error(f"Milvus 操作测试失败: {e}")
        return False


def test_milvus_connection():
    """测试 Milvus 连接功能"""
    try:
        with MilvusOperation() as milvus:
            # 测试连接是否成功
            assert milvus.collection is not None, "集合加载失败"
            logger.info("Milvus 连接测试通过")
            return True
    except Exception as e:
        logger.error(f"Milvus 连接测试失败: {e}")
        return False

def test_milvus_insert():
    """测试 Milvus 插入功能"""
    try:
        with MilvusOperation() as milvus:
            # 准备测试数据
            test_vectors = [{
                "vector": np.array([0.1] * 1024, dtype=np.float32),
                "segment_id": "test_segment_1",
                "doc_id": "test_doc_1",
                "document_name": "test_doc.pdf",
                "summary_text": "测试文档摘要",
                "type": "text",
                "page_idx": 1,
                "principal_ids": "test_principal",
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "metadata": {"key": "value"}
            }]
            
            # 测试插入
            result = milvus.insert_vectors(test_vectors)
            assert result, "向量插入失败"
            logger.info("Milvus 插入测试通过")
            return True
    except Exception as e:
        logger.error(f"Milvus 插入测试失败: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    tests = [
        ("连接测试", test_milvus_connection),
        ("插入测试", test_milvus_insert),
        ("操作测试", test_milvus_operations)
    ]
    
    success_count = 0
    for test_name, test_func in tests:
        logger.info(f"开始 {test_name}...")
        if test_func():
            success_count += 1
            logger.info(f"{test_name} 通过")
        else:
            logger.error(f"{test_name} 失败")
    
    logger.info(f"测试完成: {success_count}/{len(tests)} 通过")
    return success_count == len(tests)

if __name__ == "__main__":
    run_all_tests()
    test_milvus_operations()
