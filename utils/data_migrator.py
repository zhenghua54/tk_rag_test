"""数据迁移工具

提供从原有 IVF collection 到新 FLAT collection 的数据迁移功能。
支持批量迁移、数据验证和迁移进度监控。

使用示例：
    # 创建迁移器
    migrator = DataMigrator()

    # 执行迁移
    migrator.migrate_all_data()

    # 验证迁移结果
    migrator.verify_migration()
"""
import time
from datetime import datetime
from typing import List, Dict, Any

from databases.milvus.connection import MilvusDB
from databases.milvus.flat_collection import FlatCollectionManager
from utils.log_utils import logger


class DataMigrator:
    """
    数据迁移器

    负责将数据从原有的 IVF collection（rag_collection）中迁移到新的 FLAT collection（rag_flat）。
    提供完整的迁移流程，包括数据读取、格式转换、批量插入和验证。

    Attributes:
        source_collection：源集合名称（rag_collection）
        target_collection：目标集合名称（rag_flat）
        batch_size：批量处理大小，默认 1000
    """

    def __init__(self, batch_size: int = 1000):
        """初始化数据迁移器

        Args：
            batch_size：批量处理大小，默认 1000
        """
        self.source_collection = "rag_collection"  # 原有的 IVF collection
        self.target_collection = "rag_flat"  # 新的 FLAT Collection
        self.batch_size = batch_size

        # 初始化源集合和目标集合
        self._init_collection()

    def _init_collection(self):
        """初始化源集合和目标集合"""
        try:
            # 初始化源集合
            self.source_milvus = MilvusDB()
            self.source_milvus.init_database()

            # 初始化目标集合
            self.target_manager = FlatCollectionManager(self.target_collection)
            self.target_manager.init_collection()

            logger.info(f"[数据迁移] 源集合：{self.source_collection}")
            logger.info(f"[数据迁移] 目标集合：{self.target_collection}")
        except Exception as e:
            logger.error(f"[数据迁移] 初始化集合失败：{str(e)}")
            raise

    def get_source_data_count(self) -> int:
        """
        获取源集合中的数据总数

        Returns：
            int：目标总数
        """
        try:
            stats = self.source_milvus.client.get_collection_stats(
                collection_name=self.source_collection
            )
            count = stats.get("row_count", 0)
            logger.info(f"[数据迁移] 源集合数据总数：{count}")
            return count
        except Exception as e:
            logger.error(f"[数据迁移] 获取源集合数据总数失败：{str(e)}")
            return 0

    def _convert_data_format(self, source_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        转换数据格式

        将源集合的数据格式转换为目标集合的数据格式。
        主要处理字段名映射和数据类型转换。

        Args：
            source_data：源数据列表

        Returns:
            List[Dict[str,Any]]：转换后的数据列表
        """
        converted_data = []

        for item in source_data:
            # 字段名映射： vector -> seg_dense_vector
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

        return converted_data

    def migrate_batch(self, offset: int, limit: int) -> int:
        """
        迁移一批数据

        Args：
            offset：数据偏移量
            limit：数据限制数量

        Returns：
            int：实际迁移的数据数量
        """
        try:
            # 从源集合查询数据
            source_data = self.source_milvus.client.query(
                collection_name=self.source_collection,
                filter='',
                output_fields=["*"],
                limit=limit,
                offset=offset,
            )

            if not source_data:
                logger.info(f"[数据迁移] 批次 {offset}-{offset + limit} 无数据")
                return 0

            # 转换数据格式
            converted_data = self._convert_data_format(source_data)

            # 插入到目标集合
            inserted_ids = self.target_manager.insert_data(converted_data)

            logger.info(f"[数据迁移] 批次 {offset}-{offset + limit} 迁移完成，共 {len(inserted_ids)} 条")
            return len(inserted_ids)

        except Exception as e:
            logger.error(f"[数据迁移] 批次 {offset}-{offset + limit} 迁移失败：{str(e)}")
            raise

    def migrate_all_data(self) -> bool:
        """
        迁移所有数据

        分批迁移源集合中的所有数据到目标集合。

        Returns:
            bool：迁移是否成功
        """
        try:
            # 获取源集合数据总数
            total_count = self.get_source_data_count()
            if total_count == 0:
                logger.info(f"[数据迁移] 源集合无数据，跳过迁移。")
                return True

            logger.info(f"[数据迁移] 开始迁移 {total_count} 条数据...")
            start_time = time.time()

            # 分批迁移
            migrate_count = 0
            for offset in range(0, total_count, self.batch_size):
                # 获取迁移的数据量
                batch_count = self.migrate_batch(offset, self.batch_size)
                migrate_count += batch_count

                # 显示进度
                progress = (migrate_count / total_count) * 100
                logger.info(f"[数据迁移] 进度：{progress:.1f}% {migrate_count}/{total_count}")

                # 短暂休息，避免过度占用资源
                time.sleep(0.5)

            end_time = time.time()
            duration = end_time - start_time

            logger.info(f"[数据迁移] 迁移完成！共迁移 {migrate_count} 条数据，耗时 {duration} 秒")
            return True

        except Exception as e:
            logger.error(f"[数据迁移] 验证失败：{str(e)}")
            return False

    def verify_migration(self) -> bool:
        """
        验证迁移结果

        比较源集合和目标集合的数据数量，确保迁移完整性。

        Returns:
            bool: 验证是否通过
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

            logger.info(f"[数据迁移] 源集合数据数量：{source_count}")
            logger.info(f"[数据迁移] 目标集合数据数量：{target_count}")

            if source_count == target_count:
                logger.info(f"[数据迁移] 验证通过！数据数量一致")
                return True
            else:
                logger.error(f"[数据迁移] 验证失败！数据数量不一致")
                return False

        except Exception as e:
            logger.error(f"[数据迁移] 验证失败：{str(e)}")
            return False

    def get_migrate_summary(self) -> Dict[str, Any]:
        """
        获取迁移摘要

        Returns:
            Dict[str,Any]：迁移摘要信息
        """
        try:
            source_stats = self.source_milvus.client.get_collection_stats(
                collection_name=self.source_collection
            )
            target_stats = self.target_manager.get_collection_stats()

            return {
                "source_collection": self.source_collection,
                "target_collection": self.target_collection,
                "source_count": source_stats.get("row_count", 0),
                "target_count": target_stats.get("entity_count", 0),
                "source_indexes": self.source_milvus.client.list_indexes(
                    collection_name=self.source_collection
                ),
                "target_indexes": target_stats.get("indexes", []),
                "migration_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            logger.error(f"[数据迁移] 获取迁移摘要失败：{str(e)}")
            return {}


def run_migrate():
    """执行数据迁移"""
    logger.info(f"[数据迁移] 开始执行数据迁移...")

    try:
        # 创建迁移器
        migrator = DataMigrator(batch_size=1000)

        # 执行迁移
        success = migrator.migrate_all_data()

        if success:
            # 验证迁移结果
            verified = migrator.verify_migration()

            if verified:
                # 获取迁移摘要
                summary = migrator.get_migrate_summary()
                logger.info(f"[数据迁移] 迁移摘要：{summary}")
                logger.info("[数据迁移]数据迁移成功完成！")
            else:
                logger.error("[数据迁移] 数据迁移验证失败！")
        else:
            logger.error(f"[数据迁移] 数据迁移失败！")

    except Exception as e:
        logger.error(f"[数据迁移] 数据迁移过程中出现错误：{str(e)}")


if __name__ == '__main__':
    # 执行
    run_migrate()
