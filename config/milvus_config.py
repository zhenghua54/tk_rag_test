"""Milvus 配置管理模块

提供 Milvus 向量检索的配置管理，专注于解决当前小数据量的稳定性问题。
当前阶段使用 FLAT 索引，确保 100% 精确的搜索结果。

使用示例：
    # 使用默认 FLAT 配置
    config = MilvusFlatConfig()

    # 使用自定义配置
    config = MilvusFlatConfig(top_k=10, round_decimal=8)
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class MilvusFlatConfig:
    """
    Milvus FLAT Collection 配置类

    FLAT 索引提供 100% 精确的搜索结果，适合小数据（<100万）量场景。

    Attributes:
        top_k: 返回结果数量，默认 20
        round_decimal: 分数精度，用于提高结果稳定性，默认 8
        use_round_robin: 是否使用轮询策略处理相同分数，默认 True
        random_seed: 随机种子，确保结果一致性，默认 42
    """

    top_k: int = 20
    round_decimal: int = 8
    use_round_robin: bool = True
    random_seed: int = 42

    def __post_init__(self):
        """数据验证"""
        if self.top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        if self.round_decimal < 0 or self.round_decimal > 10:
            raise ValueError("round_decimal 必须在 0-10 之间")

    @staticmethod
    def get_dense_index_params() -> dict[str, Any]:
        """
        获取稠密向量索引参数

        Returns:
            Dict[str, Any]: FLAT 索引参数字典
        """
        return {
            "field_name": "seg_dense_vector",
            "index_type": "FLAT",
            "metric_type": "IP",
        }

    @staticmethod
    def get_sparse_index_params() -> dict[str, Any]:
        """
        获取稀疏向量索引参数

        Returns:
            Dict[str, Any]: FLAT 索引参数字典
        """
        return {
            "field_name": "seg_sparse_vector",
            "index_type": "SPARSE_INVERTED_INDEX",
            "metric_type": "BM25",
            "params": {
                "inverted_index_algo": "DAAT_MAXSCORE",
                "bm25_k1": 1.2,
                "bm25_b": 0.75,
            },
        }

    def get_search_params(self) -> dict[str, Any]:
        """
        获取搜索参数

        Returns:
            Dict[str, Any]: 搜索参数字典
        """
        return {
            "top_k": self.top_k,
            "round_decimal": self.round_decimal,
            "consistency_level": "STRONG",
        }

    def get_config_summary(self) -> dict[str, Any]:
        """
        获取配置摘要

        Returns:
            Dict[str, Any]: 配置摘要字典
        """
        return {
            "index_type": "FLAT",
            "metric_type": "IP",
            "top_k": self.top_k,
            "round_decimal": self.round_decimal,
            "use_round_robin": self.use_round_robin,
            "random_seed": self.random_seed,
        }

