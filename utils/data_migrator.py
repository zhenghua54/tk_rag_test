"""基于 query_iterator 的数据迁移工具

使用 Milvus 官方的 query_iterator 方法分批遍历所有数据，
确保能获取并迁移全部数据，目标集合数量才会和源集合一致。

使用示例：
    # 创建迁移器
    migrator = IteratorMigrator("rag_collection", "rag_flat")

    # 执行迁移
    success = migrator.migrate_all_data()

    # 验证结果
    if success:
        migrator.verify_migration()
"""

import time
from typing import List, Dict, Any
from datetime import datetime


from pymilvus.bulk_writer import LocalBulkWriter,BulkFileType

from databases.milvus.connection import MilvusDB
from databases.milvus.flat_collection import FlatCollectionManager
from utils.log_utils import logger


class IteratorMigrator:
    """
    基于 query_iterator 的数据迁移器

    使用 Milvus 官方的 query_iterator 方法分批遍历所有数据，
    确保能获取并迁移全部数据，目标集合数量才会和源集合一致。

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
            self.target_manager._init_collection()

            logger.info(f"[迭代迁移] 源集合：{self.source_collection}")
            logger.info(f"[迭代迁移] 目标集合：{self.target_collection}")

        except Exception as e:
            logger.error(f"[迭代迁移] 初始化集合失败：{str(e)}")
            raise

    def get_all_data_by_iterator(self) -> List[Dict[str, Any]]:
        """使用 query_iterator 获取所有数据

        使用 Milvus 官方的 query_iterator 方法分批遍历所有数据，
        确保能获取全部数据。

        Returns:
            List[Dict[str, Any]]: 所有数据列表
        """
        try:
            # 获取集合统计信息
            stats = self.source_milvus.client.get_collection_stats(
                collection_name=self.source_collection
            )
            total_count = stats.get("row_count", 0)

            logger.info(f"[迭代迁移] 源集合总数据量：{total_count}")

            # 使用 query_iterator 分批获取所有数据
            all_data = []

            # 创建迭代器
            logger.info(f"[迭代迁移] 创建 query_iterator，批次大小：{self.batch_size}")
            iterator = self.source_milvus.client.query_iterator(
                collection_name=self.source_collection,
                filter='',  # 空过滤条件，获取所有数据
                output_fields=["*"],  # 获取所有字段
                batch_size=self.batch_size
            )

            batch_count = 0
            total_fetched = 0

            logger.info(f"[迭代迁移] 开始迭代获取数据...")

            while True:
                try:
                    # 获取下一批数据
                    batch_data = iterator.next()

                    if not batch_data:
                        logger.info(f"[迭代迁移] 迭代器返回空数据，迭代结束")
                        break

                    # 添加批次数据到总数据列表
                    all_data.extend(batch_data)
                    batch_count += 1
                    total_fetched += len(batch_data)

                    logger.info(
                        f"[迭代迁移] 批次 {batch_count}：获取 {len(batch_data)} 条，累计 {total_fetched}/{total_count} 条")

                    # 如果累计获取的数据量已经达到或超过总数，说明已经获取完所有数据
                    if total_fetched >= total_count:
                        logger.info(f"[迭代迁移] 已获取所有数据，停止迭代")
                        break

                except Exception as e:
                    logger.error(f"[迭代迁移] 迭代器获取数据失败：{str(e)}")
                    break

            logger.info(f"[迭代迁移] 迭代完成！总共获取 {len(all_data)} 条数据，期望 {total_count} 条")

            # 验证数据完整性
            if len(all_data) == total_count:
                logger.info(f"[迭代迁移] ✅ 成功获取所有数据！")
            elif len(all_data) > total_count:
                logger.warning(f"[迭代迁移] ⚠️ 获取数据量超过统计数量：{len(all_data)} > {total_count}")
            else:
                logger.error(f"[迭代迁移] ❌ 数据不完整：{len(all_data)} < {total_count}")

            return all_data

        except Exception as e:
            logger.error(f"[迭代迁移] 使用迭代器获取数据失败：{str(e)}")
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
                logger.error(f"[迭代迁移] 第 {idx + 1} 条数据转换失败：{str(e)}，数据：{item}")
                continue

        logger.info(f"[迭代迁移] 数据转换完成，成功转换 {len(converted_data)} 条，原始数据 {len(source_data)} 条")
        return converted_data

    def migrate_all_data(self) -> bool:
        """执行完整的数据迁移

        Returns:
            bool: 迁移是否成功
        """
        try:
            start_time = time.time()
            logger.info(f"[迭代迁移] 开始从 {self.source_collection} 迁移数据到 {self.target_collection}")

            # 步骤1：使用迭代器获取所有数据
            source_data = self.get_all_data_by_iterator()
            if not source_data:
                logger.warning("[迭代迁移] 源集合无数据，跳过迁移")
                return True

            # 步骤2：转换数据格式
            converted_data = self.convert_data_format(source_data)
            if not converted_data:
                logger.error("[迭代迁移] 数据格式转换失败")
                return False

            # 步骤3：分批插入到目标集合
            total_inserted = 0
            insert_batch_size = 100  # 插入批次大小

            for i in range(0, len(converted_data), insert_batch_size):
                batch_data = converted_data[i:i + insert_batch_size]

                try:
                    inserted_ids = self.target_manager.insert_data(batch_data)
                    total_inserted += len(inserted_ids)

                    logger.info(f"[迭代迁移] 插入进度：{total_inserted}/{len(converted_data)}")

                except Exception as e:
                    logger.error(f"[迭代迁移] 插入批次 {i // insert_batch_size + 1} 失败：{str(e)}")
                    continue

            end_time = time.time()
            duration = end_time - start_time

            logger.info(f"[迭代迁移] 迁移完成！共迁移 {total_inserted} 条数据，耗时 {duration:.2f} 秒")

            # 验证迁移结果
            if total_inserted == len(source_data):
                logger.info("[迭代迁移] 数据数量验证通过")
                return True
            else:
                logger.warning(f"[迭代迁移] 数据数量不一致：期望 {len(source_data)}，实际 {total_inserted}")
                return False

        except Exception as e:
            logger.error(f"[迭代迁移] 迁移失败：{str(e)}")
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

            logger.info(f"[迭代迁移] 源集合数据数量：{source_count}")
            logger.info(f"[迭代迁移] 目标集合数据数量：{target_count}")

            verification_result = {
                "source_collection": self.source_collection,
                "target_collection": self.target_collection,
                "source_count": source_count,
                "target_count": target_count,
                "migration_success": source_count == target_count,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            if source_count == target_count:
                logger.info("[迭代迁移] 验证通过！数据数量一致")
            else:
                logger.error("[迭代迁移] 验证失败！数据数量不一致")

            return verification_result

        except Exception as e:
            logger.error(f"[迭代迁移] 验证失败：{str(e)}")
            return {"error": str(e)}


def run_iterator_migration(source_collection: str = "rag_collection",
                          target_collection: str = "rag_flat") -> bool:
    """执行基于迭代器的数据迁移

    Args:
        source_collection: 源集合名称
        target_collection: 目标集合名称

    Returns:
        bool: 迁移是否成功
    """
    migrator = IteratorMigrator(source_collection, target_collection)

    try:
        success = migrator.migrate_all_data()

        if success:
            # 验证迁移结果
            verification = migrator.verify_migration()
            logger.info(f"[迭代迁移] 验证结果: {verification}")

        return success

    except Exception as e:
        logger.error(f"[迭代迁移] 迁移异常: {str(e)}")
        return False


if __name__ == "__main__":
    # 执行迁移
    success = run_iterator_migration("rag_collection", "rag_flat")

    if success:
        print("数据迁移成功！")
    else:
        print("数据迁移失败！")