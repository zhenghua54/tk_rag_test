"""Milvus 查询测试工具

用于测试和验证 Milvus 数据库的查询功能，确保能正常获取所有数据。
支持多种查询方式：query、get、分批查询等。

使用示例：
    # 创建测试器
    tester = MilvusQueryTester("rag_collection")

    # 测试统计信息
    tester.test_statistics()

    # 测试查询所有数据
    tester.test_query_all_data()

    # 测试分批查询
    tester.test_batch_query()

    # 测试 get 方法
    tester.test_get_method()
"""

import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from databases.milvus.connection import MilvusDB
from utils.log_utils import logger


class MilvusQueryTester:
    """
    Milvus 查询测试器

    提供多种查询方式的测试，帮助诊断数据获取问题。

    Attributes:
        collection_name: 集合名称
        milvus_db: Milvus 数据库连接
    """

    def __init__(self, collection_name: str):
        """初始化测试器

        Args:
            collection_name: 集合名称
        """
        self.collection_name = collection_name
        self.milvus_db = MilvusDB()
        self.milvus_db.init_database()

        logger.info(f"[查询测试] 初始化测试器，集合：{collection_name}")

    def test_statistics(self) -> Dict[str, Any]:
        """测试集合统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            logger.info("=" * 50)
            logger.info("[查询测试] 开始测试集合统计信息")

            # 获取集合统计信息
            stats = self.milvus_db.client.get_collection_stats(
                collection_name=self.collection_name
            )

            # 获取加载状态
            load_state = self.milvus_db.client.get_load_state(
                collection_name=self.collection_name
            )

            # 获取集合信息
            collection_info = self.milvus_db.client.describe_collection(
                collection_name=self.collection_name
            )

            result = {
                "collection_name": self.collection_name,
                "row_count": stats.get("row_count", 0),
                "load_state": str(load_state),
                "collection_info": collection_info,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            logger.info(f"[查询测试] 统计信息：{result}")
            return result

        except Exception as e:
            logger.error(f"[查询测试] 获取统计信息失败：{str(e)}")
            return {"error": str(e)}

    def test_query_all_data(self) -> Dict[str, Any]:
        """测试查询所有数据（使用 query 方法）

        Returns:
            Dict[str, Any]: 查询结果信息
        """
        try:
            logger.info("=" * 50)
            logger.info("[查询测试] 开始测试查询所有数据")

            # 获取统计数量
            stats = self.milvus_db.client.get_collection_stats(
                collection_name=self.collection_name
            )
            total_count = stats.get("row_count", 0)

            logger.info(f"[查询测试] 集合总数据量：{total_count}")

            # 尝试不同的 limit 值
            test_limits = [100, 500, 1000, total_count, total_count + 1000]

            for limit in test_limits:
                logger.info(f"[查询测试] 测试 limit={limit}")

                start_time = time.time()

                # 执行查询
                results = self.milvus_db.client.query(
                    collection_name=self.collection_name,
                    filter='',
                    output_fields=["*"],
                    limit=limit,
                    offset=0
                )

                end_time = time.time()
                duration = end_time - start_time

                logger.info(f"[查询测试] limit={limit} 查询结果：{len(results)} 条，耗时：{duration:.3f} 秒")

                # 如果查询结果数量等于总数，说明成功获取所有数据
                if len(results) == total_count:
                    logger.info(f"[查询测试] ✅ 成功获取所有数据！limit={limit}")
                    return {
                        "success": True,
                        "total_count": total_count,
                        "query_count": len(results),
                        "limit_used": limit,
                        "duration": duration,
                        "method": "query"
                    }
                else:
                    logger.warning(f"[查询测试] ⚠️ 数据不完整：期望 {total_count}，实际 {len(results)}")

            logger.error("[查询测试] ❌ 所有 limit 值都无法获取完整数据")
            return {
                "success": False,
                "total_count": total_count,
                "method": "query",
                "error": "无法获取完整数据"
            }

        except Exception as e:
            logger.error(f"[查询测试] 查询所有数据失败：{str(e)}")
            return {"error": str(e)}

    def test_batch_query(self) -> Dict[str, Any]:
        """测试分批查询

        Returns:
            Dict[str, Any]: 分批查询结果信息
        """
        try:
            logger.info("=" * 50)
            logger.info("[查询测试] 开始测试分批查询")

            # 获取统计数量
            stats = self.milvus_db.client.get_collection_stats(
                collection_name=self.collection_name
            )
            total_count = stats.get("row_count", 0)

            logger.info(f"[查询测试] 集合总数据量：{total_count}")

            # 分批查询
            all_data = []
            batch_size = 100
            offset = 0

            start_time = time.time()

            while offset < total_count:
                logger.info(f"[查询测试] 分批查询：offset={offset}, batch_size={batch_size}")

                # 执行分批查询
                batch_data = self.milvus_db.client.query(
                    collection_name=self.collection_name,
                    filter='',
                    output_fields=["*"],
                    limit=batch_size,
                    offset=offset
                )

                all_data.extend(batch_data)
                logger.info(f"[查询测试] 分批查询进度：{len(all_data)}/{total_count}")

                offset += batch_size

                # 如果返回的数据量小于批次大小，说明已经获取完所有数据
                if len(batch_data) < batch_size:
                    break

            end_time = time.time()
            duration = end_time - start_time

            logger.info(f"[查询测试] 分批查询完成，总共获取 {len(all_data)} 条数据，耗时：{duration:.3f} 秒")

            if len(all_data) == total_count:
                logger.info("[查询测试] ✅ 分批查询成功获取所有数据！")
                return {
                    "success": True,
                    "total_count": total_count,
                    "query_count": len(all_data),
                    "batch_size": batch_size,
                    "duration": duration,
                    "method": "batch_query"
                }
            else:
                logger.error(f"[查询测试] ❌ 分批查询数据不完整：期望 {total_count}，实际 {len(all_data)}")
                return {
                    "success": False,
                    "total_count": total_count,
                    "query_count": len(all_data),
                    "method": "batch_query",
                    "error": "分批查询数据不完整"
                }

        except Exception as e:
            logger.error(f"[查询测试] 分批查询失败：{str(e)}")
            return {"error": str(e)}

    def test_get_method(self) -> Dict[str, Any]:
        """测试 get 方法（根据 ID 获取数据）

        Returns:
            Dict[str, Any]: get 方法测试结果
        """
        try:
            logger.info("=" * 50)
            logger.info("[查询测试] 开始测试 get 方法")

            # 先获取一些 doc_id
            sample_ids = self.milvus_db.client.query(
                collection_name=self.collection_name,
                filter='',
                output_fields=["doc_id"],
                limit=10,
                offset=0
            )

            if not sample_ids:
                logger.error("[查询测试] 无法获取样本 ID")
                return {"error": "无法获取样本 ID"}

            doc_ids = [item["doc_id"] for item in sample_ids]
            logger.info(f"[查询测试] 获取到 {len(doc_ids)} 个样本 ID")

            # 使用 get 方法获取数据
            start_time = time.time()

            results = self.milvus_db.client.get(
                collection_name=self.collection_name,
                ids=doc_ids,
                output_fields=["*"]
            )

            end_time = time.time()
            duration = end_time - start_time

            logger.info(f"[查询测试] get 方法获取到 {len(results)} 条数据，耗时：{duration:.3f} 秒")

            if len(results) == len(doc_ids):
                logger.info("[查询测试] ✅ get 方法测试成功！")
                return {
                    "success": True,
                    "requested_count": len(doc_ids),
                    "returned_count": len(results),
                    "duration": duration,
                    "method": "get"
                }
            else:
                logger.warning(f"[查询测试] ⚠️ get 方法数据不完整：期望 {len(doc_ids)}，实际 {len(results)}")
                return {
                    "success": False,
                    "requested_count": len(doc_ids),
                    "returned_count": len(results),
                    "method": "get",
                    "error": "get 方法数据不完整"
                }

        except Exception as e:
            logger.error(f"[查询测试] get 方法测试失败：{str(e)}")
            return {"error": str(e)}

    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试

        Returns:
            Dict[str, Any]: 所有测试结果
        """
        logger.info("=" * 60)
        logger.info("[查询测试] 开始运行所有测试")

        results = {
            "collection_name": self.collection_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tests": {}
        }

        # 运行各项测试
        results["tests"]["statistics"] = self.test_statistics()
        results["tests"]["query_all"] = self.test_query_all_data()
        results["tests"]["batch_query"] = self.test_batch_query()
        results["tests"]["get_method"] = self.test_get_method()

        # 总结
        logger.info("=" * 60)
        logger.info("[查询测试] 所有测试完成")
        logger.info(f"[查询测试] 测试结果：{results}")

        return results


def test_milvus_query(collection_name: str = "rag_collection") -> Dict[str, Any]:
    """测试 Milvus 查询功能

    Args:
        collection_name: 集合名称

    Returns:
        Dict[str, Any]: 测试结果
    """
    tester = MilvusQueryTester(collection_name)
    return tester.run_all_tests()


if __name__ == "__main__":
    # 运行测试
    results = test_milvus_query("rag_collection")

    # 打印结果摘要
    print("\n" + "=" * 60)
    print("测试结果摘要：")
    print(f"集合名称：{results['collection_name']}")
    print(f"测试时间：{results['timestamp']}")

    for test_name, test_result in results['tests'].items():
        print(f"\n{test_name}:")
        if 'success' in test_result:
            status = "✅ 成功" if test_result['success'] else "❌ 失败"
            print(f"  状态：{status}")
        if 'error' in test_result:
            print(f"  错误：{test_result['error']}")
        if 'total_count' in test_result:
            print(f"  总数：{test_result['total_count']}")
        if 'query_count' in test_result:
            print(f"  查询数：{test_result['query_count']}")