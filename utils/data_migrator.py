"""可靠的数据迁移工具

基于 Milvus 官方建议，使用 get 方法根据 ID 列表获取数据，
避免 query 方法的分页限制问题。

使用示例：
    # 创建迁移器
    migrator = ReliableMigrator("rag_collection", "rag_flat")

    # 执行迁移
    success = migrator.migrate_all_data()

    # 验证结果
    if success:
        migrator.verify_migration()
"""

import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from databases.milvus.connection import MilvusDB
from databases.milvus.flat_collection import FlatCollectionManager
from utils.log_utils import logger


class ReliableMigrator:
    """
    可靠的数据迁移器

    基于 Milvus 官方建议，使用 get 方法根据 ID 列表获取数据，
    完全避免 query 方法的分页限制问题。

    Attributes:
        source_collection: 源集合名称
        target_collection: 目标集合名称
        batch_size: 批量处理大小
    """

    def __init__(self, source_collection: str, target_collection: str, batch_size: int = 100):
        """初始化迁移器

        Args:
            source_collection: 源集合名称
            target_collection: 目标集合名称
            batch_size: 批量处理大小，默认100
        """
        self.source_collection = source_collection
        self.target_collection = target_collection
        self.batch_size = batch_size

        # 初始化源集合和目标集合
        self._init_collections()

    def _init_collections(self) -> None:
        """初始化源集合和目标集合"""
        try:
            # 初始化源集合
            self.source_milvus = MilvusDB()
            self.source_milvus.init_database()

            # 初始化目标集合
            self.target_manager = FlatCollectionManager(self.target_collection)
            self.target_manager.init_collection()

            logger.info(f"[可靠迁移] 源集合：{self.source_collection}")
            logger.info(f"[可靠迁移] 目标集合：{self.target_collection}")

        except Exception as e:
            logger.error(f"[可靠迁移] 初始化集合失败：{str(e)}")
            raise

    def get_all_doc_ids(self) -> List[str]:
        """获取源集合中所有的 doc_id 列表

        使用 query 方法只获取 doc_id 字段，避免大数据量传输。

        Returns:
            List[str]: doc_id 列表
        """
        try:
            # 获取集合统计信息
            stats = self.source_milvus.client.get_collection_stats(
                collection_name=self.source_collection
            )
            total_count = stats.get("row_count", 0)

            logger.info(f"[可靠迁移] 源集合总数据量：{total_count}")

            # 分批获取所有 doc_id
            all_doc_ids = []
            offset = 0

            while offset < total_count:
                # 每次只获取 doc_id 字段，减少数据传输
                batch_ids = self.source_milvus.client.query(
                    collection_name=self.source_collection,
                    filter='',
                    output_fields=["doc_id"],  # 只获取 doc_id 字段
                    limit=self.batch_size,
                    offset=offset,
                )

                doc_ids = [item["doc_id"] for item in batch_ids]
                all_doc_ids.extend(doc_ids)

                logger.info(f"[可靠迁移] 获取 doc_id 进度：{len(all_doc_ids)}/{total_count}")

                offset += self.batch_size

                # 如果返回的数据量小于批次大小，说明已经获取完所有数据
                if len(batch_ids) < self.batch_size:
                    break

            logger.info(f"[可靠迁移] 成功获取 {len(all_doc_ids)} 个 doc_id")
            return all_doc_ids

        except Exception as e:
            logger.error(f"[可靠迁移] 获取 doc_id 列表失败：{str(e)}")
            raise

    def get_data_by_doc_ids(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """根据 doc_id 列表获取完整数据

        使用 get 方法获取数据，避免 query 方法的分页限制。

        Args:
            doc_ids: doc_id 列表

        Returns:
            List[Dict[str, Any]]: 完整的数据列表
        """
        try:
            all_data = []

            # 分批处理，避免一次性传递过多 ID
            for i in range(0, len(doc_ids), self.batch_size):
                batch_ids = doc_ids[i:i + self.batch_size]

                # 使用 get 方法获取数据
                batch_data = self.source_milvus.client.get(
                    collection_name=self.source_collection,
                    ids=batch_ids,
                    output_fields=["*"]
                )

                all_data.extend(batch_data)
                logger.info(f"[可靠迁移] 获取数据进度：{len(all_data)}/{len(doc_ids)}")

            logger.info(f"[可靠迁移] 成功获取 {len(all_data)} 条完整数据")
            return all_data

        except Exception as e:
            logger.error(f"[可靠迁移] 根据 doc_id 获取数据失败：{str(e)}")
            raise

    def convert_data_format(self, source_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """转换数据格式

        将源集合的数据格式转换为目标集合的数据格式。

        Args:
            source_data: 源数据列表

        Returns:
            List[Dict[str, Any]]: 转换后的数据列表
        """
        converted_data = []

        for idx, item in enumerate(source_data):
            try:
                # 字段名映射：vector -> seg_dense_vector
                convert_item = {
                    "doc_id": item.get("doc_id", ""),
                    "seg_id": item.get("seg_id", ""),
                    "seg_parent_id": item.get("seg_parent_id", ""),
                    "seg_dense_vector": item.get("vector", []),  # 字段名映射
                    "seg_sparse_vector": item.get("seg_sparse_vector", {}),  # 保持原字段名
                    "seg_content": item.get("seg_content", ""),
                    "seg_type": item.get("seg_type", ""),
                    "seg_page_idx": item.get("seg_page_idx", 0),
                    "permission_ids": item.get("permission_ids", "{}"),
                    "create_time": item.get("create_time", ""),
                    "update_time": item.get("update_time", ""),
                    "metadata": item.get("metadata", {})
                }
                converted_data.append(convert_item)

            except Exception as e:
                logger.error(f"[可靠迁移] 第 {idx+1} 条数据转换失败：{str(e)}，数据：{item}")
                continue

        logger.info(f"[可靠迁移] 数据转换完成，成功转换 {len(converted_data)} 条，原始数据 {len(source_data)} 条")
        return converted_data

    def migrate_all_data(self) -> bool:
        """执行完整的数据迁移

        Returns:
            bool: 迁移是否成功
        """
        try:
            start_time = time.time()
            logger.info(f"[可靠迁移] 开始从 {self.source_collection} 迁移数据到 {self.target_collection}")

            # 步骤1：获取所有 doc_id
            doc_ids = self.get_all_doc_ids()
            if not doc_ids:
                logger.warning("[可靠迁移] 源集合无数据，跳过迁移")
                return True

            # 步骤2：根据 doc_id 获取完整数据
            source_data = self.get_data_by_doc_ids(doc_ids)
            if not source_data:
                logger.error("[可靠迁移] 获取源数据失败")
                return False

            # 步骤3：转换数据格式
            converted_data = self.convert_data_format(source_data)
            if not converted_data:
                logger.error("[可靠迁移] 数据格式转换失败")
                return False

            # 步骤4：插入到目标集合
            inserted_ids = self.target_manager.insert_data(converted_data)

            end_time = time.time()
            duration = end_time - start_time

            logger.info(f"[可靠迁移] 迁移完成！共迁移 {len(inserted_ids)} 条数据，耗时 {duration:.2f} 秒")

            # 验证迁移结果
            if len(inserted_ids) == len(doc_ids):
                logger.info("[可靠迁移] 数据数量验证通过")
                return True
            else:
                logger.warning(f"[可靠迁移] 数据数量不一致：期望 {len(doc_ids)}，实际 {len(inserted_ids)}")
                return False

        except Exception as e:
            logger.error(f"[可靠迁移] 迁移失败：{str(e)}")
            return False

    def verify_migration(self) -> Dict[str, Any]:
        """验证迁移结果

        Returns:
            Dict[str, Any]: 验证结果信息
        """
        try:
            # 获取源集合数据数量
            source_stats = self.source_milvus.client.get_collection_stats(
                collection_name=self.source_collection
            )
            source_count = source_stats.get("row_count", 0)

            # 获取目标集合数据数量
            target_stats = self.target_manager.get_collection_stats()
            target_count = target_stats.get("entity_count", 0)

            logger.info(f"[可靠迁移] 源集合数据数量：{source_count}")
            logger.info(f"[可靠迁移] 目标集合数据数量：{target_count}")

            verification_result = {
                "source_collection": self.source_collection,
                "target_collection": self.target_collection,
                "source_count": source_count,
                "target_count": target_count,
                "migration_success": source_count == target_count,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            if source_count == target_count:
                logger.info("[可靠迁移] 验证通过！数据数量一致")
            else:
                logger.error("[可靠迁移] 验证失败！数据数量不一致")

            return verification_result

        except Exception as e:
            logger.error(f"[可靠迁移] 验证失败：{str(e)}")
            return {"error": str(e)}


def run_reliable_migration(source_collection: str = "rag_collection",
                          target_collection: str = "rag_flat") -> bool:
    """执行可靠的数据迁移

    Args:
        source_collection: 源集合名称
        target_collection: 目标集合名称

    Returns:
        bool: 迁移是否成功
    """
    migrator = ReliableMigrator(source_collection, target_collection)

    try:
        success = migrator.migrate_all_data()

        if success:
            # 验证迁移结果
            verification = migrator.verify_migration()
            logger.info(f"[可靠迁移] 验证结果: {verification}")

        return success

    except Exception as e:
        logger.error(f"[可靠迁移] 迁移异常: {str(e)}")
        return False


if __name__ == "__main__":
    # 执行迁移
    success = run_reliable_migration("rag_collection", "rag_flat")

    if success:
        print("数据迁移成功！")
    else:
        print("数据迁移失败！")