"""索引对比测试工具

对比 IVF 和 FLAT 两种索引的搜索结果差异，评估稳定性改进效果。
"""

import time
from typing import List, Dict, Any, Tuple
import numpy as np

from config.global_config import GlobalConfig
from databases.milvus.connection import MilvusDB
from databases.milvus.flat_collection import FlatCollectionManager
from utils.log_utils import logger


class IndexComparisonTester:
    """
    索引对比测试器

    对比 IVF 和 FLAT 两种索引的搜索结果，评估稳定性改进效果。
    """

    def __init__(self):
        """初始化测试器"""
        # IVF collection (原有)
        self.ivf_milvus = MilvusDB()
        self.ivf_milvus.collection_name = "rag_collection"  # 原有的 IVF collection

        # FLAT collection (新的)
        self.flat_manager = FlatCollectionManager("rag_flat")

    def compare_search_results(self, test_queries: List[str], iterations: int = 5) -> Dict[str, Any]:
        """
        对比两种索引的搜索结果

        Args:
            test_queries: 测试查询列表
            iterations: 每个查询的测试次数

        Returns:
            Dict[str, Any]: 对比结果
        """
        results = {
            "test_queries": test_queries,
            "iterations": iterations,
            "ivf_results": {},
            "flat_results": {},
            "comparison": {}
        }

        for query in test_queries:
            logger.info(f"[索引对比测试] 测试查询: {query}")

            # 测试 IVF 索引
            ivf_results = self._test_ivf_search(query, iterations)
            results["ivf_results"][query] = ivf_results

            # 测试 FLAT 索引
            flat_results = self._test_flat_search(query, iterations)
            results["flat_results"][query] = flat_results

            # 对比结果
            comparison = self._compare_results(ivf_results, flat_results)
            results["comparison"][query] = comparison

            logger.info(f"[索引对比测试] IVF稳定性: {comparison['ivf_stability']:.4f}")
            logger.info(f"[索引对比测试] FLAT稳定性: {comparison['flat_stability']:.4f}")
            logger.info(f"[索引对比测试] 稳定性提升: {comparison['stability_improvement']:.4f}")

        return results

    def _test_ivf_search(self, query: str, iterations: int) -> List[List[Dict[str, Any]]]:
        """
        测试 IVF 索引搜索

        Args:
            query: 查询文本
            iterations: 测试次数

        Returns:
            List[List[Dict[str, Any]]]: 多次搜索结果
        """
        search_results = []

        for i in range(iterations):
            try:
                # 使用 IVF 搜索参数
                search_params = {
                    "search_type": "similarity",
                    "k": 10,
                    "nprobe": 50  # IVF 特有的参数
                }

                # 这里需要实现真正的搜索逻辑
                result = self._mock_ivf_search(query, search_params)
                search_results.append(result)

                time.sleep(0.1)

            except Exception as e:
                logger.error(f"[IVF测试] 第 {i+1} 次搜索失败: {e}")
                search_results.append([])

        return search_results

    def _test_flat_search(self, query: str, iterations: int) -> List[List[Dict[str, Any]]]:
        """
        测试 FLAT 索引搜索

        Args:
            query: 查询文本
            iterations: 测试次数

        Returns:
            List[List[Dict[str, Any]]]: 多次搜索结果
        """
        search_results = []

        for i in range(iterations):
            try:
                # 使用 FLAT 搜索参数
                search_params = GlobalConfig.MILVUS_CONFIG["search_params"].copy()
                search_params["search_type"] = "similarity"
                search_params["k"] = 10

                # 这里需要实现真正的搜索逻辑
                result = self._mock_flat_search(query, search_params)
                search_results.append(result)

                time.sleep(0.1)

            except Exception as e:
                logger.error(f"[FLAT测试] 第 {i+1} 次搜索失败: {e}")
                search_results.append([])

        return search_results

    def _mock_ivf_search(self, query: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        模拟 IVF 搜索（临时实现）

        Args:
            query: 查询文本
            search_params: 搜索参数

        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        # 模拟 IVF 索引可能的不稳定性
        base_scores = [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45]

        # 添加随机扰动，模拟 IVF 的不稳定性
        noise = np.random.normal(0, 0.05, len(base_scores))
        scores = [max(0, min(1, score + noise[i])) for i, score in enumerate(base_scores)]

        return [
            {"seg_id": f"seg_{i}", "score": scores[i]}
            for i in range(search_params["k"])
        ]

    def _mock_flat_search(self, query: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        模拟 FLAT 搜索（临时实现）

        Args:
            query: 查询文本
            search_params: 搜索参数

        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        # 模拟 FLAT 索引的稳定性
        base_scores = [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45]

        # 添加很小的随机扰动，模拟 FLAT 的稳定性
        noise = np.random.normal(0, 0.001, len(base_scores))
        scores = [max(0, min(1, score + noise[i])) for i, score in enumerate(base_scores)]

        return [
            {"seg_id": f"seg_{i}", "score": scores[i]}
            for i in range(search_params["k"])
        ]

    def _compare_results(self, ivf_results: List[List[Dict[str, Any]]],
                        flat_results: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        对比两种索引的结果

        Args:
            ivf_results: IVF 搜索结果
            flat_results: FLAT 搜索结果

        Returns:
            Dict[str, Any]: 对比结果
        """
        # 计算稳定性分数
        ivf_stability = self._calculate_stability_score(ivf_results)
        flat_stability = self._calculate_stability_score(flat_results)

        # 计算稳定性提升
        stability_improvement = flat_stability - ivf_stability

        # 计算结果一致性
        result_consistency = self._calculate_result_consistency(ivf_results, flat_results)

        return {
            "ivf_stability": ivf_stability,
            "flat_stability": flat_stability,
            "stability_improvement": stability_improvement,
            "result_consistency": result_consistency,
            "recommendation": "FLAT" if stability_improvement > 0.1 else "IVF"
        }

    def _calculate_stability_score(self, search_results: List[List[Dict[str, Any]]]) -> float:
        """
        计算稳定性分数

        Args:
            search_results: 多次搜索结果列表

        Returns:
            float: 稳定性分数 (0-1，越高越稳定)
        """
        if not search_results or len(search_results) < 2:
            return 0.0

        # 提取每次搜索的 seg_id 列表
        seg_id_lists = []
        for result in search_results:
            seg_ids = [item["seg_id"] for item in result]
            seg_id_lists.append(seg_ids)

        # 计算结果一致性
        consistency_scores = []
        for i in range(len(seg_id_lists) - 1):
            for j in range(i + 1, len(seg_id_lists)):
                # 计算两个结果列表的 Jaccard 相似度
                set1 = set(seg_id_lists[i])
                set2 = set(seg_id_lists[j])

                if len(set1 | set2) == 0:
                    similarity = 1.0
                else:
                    similarity = len(set1 & set2) / len(set1 | set2)

                consistency_scores.append(similarity)

        # 返回平均一致性分数
        return np.mean(consistency_scores) if consistency_scores else 0.0

    def _calculate_result_consistency(self, ivf_results: List[List[Dict[str, Any]]],
                                    flat_results: List[List[Dict[str, Any]]]) -> float:
        """
        计算两种索引结果的一致性

        Args:
            ivf_results: IVF 搜索结果
            flat_results: FLAT 搜索结果

        Returns:
            float: 结果一致性分数
        """
        if not ivf_results or not flat_results:
            return 0.0

        # 取第一次搜索结果进行对比
        ivf_first = set(item["seg_id"] for item in ivf_results[0])
        flat_first = set(item["seg_id"] for item in flat_results[0])

        if len(ivf_first | flat_first) == 0:
            return 1.0

        return len(ivf_first & flat_first) / len(ivf_first | flat_first)


def run_index_comparison():
    """运行索引对比测试"""
    logger.info("开始索引对比测试...")

    tester = IndexComparisonTester()

    # 测试查询
    test_queries = [
        "我在公司4年，年假几天？",
        "我去宁波出差，酒店可以报销多少",
        "如果我一个月迟到了3天，后果是什么",
        "我的工资条里一个月有哪些补贴",
        "滨江区的AI补贴政策有哪些",
        "浙江省有什么补贴政策",
        "杭州市有什么补贴政策",
        "滨江区有什么补贴政策",
        "我是一家滨江区的人工智能企业，我可以享受什么政策政策",
        "算力券和语料券可以叠加吗？",
        "杭州市和滨江区政策补贴可以叠加吗？",
    ]

    # 执行对比测试
    results = tester.compare_search_results(test_queries, iterations=5)

    # 输出总结
    logger.info("=== 索引对比测试总结 ===")
    total_ivf_stability = np.mean([results["comparison"][q]["ivf_stability"] for q in test_queries])
    total_flat_stability = np.mean([results["comparison"][q]["flat_stability"] for q in test_queries])
    total_improvement = total_flat_stability - total_ivf_stability

    logger.info(f"IVF 平均稳定性: {total_ivf_stability:.4f}")
    logger.info(f"FLAT 平均稳定性: {total_flat_stability:.4f}")
    logger.info(f"稳定性提升: {total_improvement:.4f}")

    if total_improvement > 0.1:
        logger.info("✅ 推荐使用 FLAT 索引，稳定性显著提升")
    elif total_improvement > 0.05:
        logger.info("⚠️  FLAT 索引稳定性略有提升，建议使用")
    else:
        logger.info("❌ FLAT 索引稳定性提升不明显，建议继续使用 IVF")


if __name__ == '__main__':
    run_index_comparison()