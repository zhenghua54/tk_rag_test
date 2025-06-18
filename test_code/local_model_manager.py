"""本地大模型管理器，支持 VLLM 加速

该模块提供了本地大模型的管理功能，支持两种主要场景：
1. 摘要生成：用于提取表格标题和内容摘要，需要确定性输出
2. rag 生成：用于检索增强生成，需要更多样化的输出
"""

import os
from typing import Tuple, Optional
from transformers import AutoTokenizer
# from vllm import LLM, SamplingParams

from utils.log_utils import logger
from config.global_config import GlobalConfig


class LocalModelManager:
    """本地大模型管理器
    
    主要功能：
    1. 管理模型实例的加载和缓存
    2. 提供不同场景的采样参数配置
    3. 支持 VLLM 加速
    """

    def __init__(self):
        """初始化本地模型管理器
        
        初始化过程：
        1. 验证模型路径
        2. 设置 VLLM 基础配置
        3. 设置场景特定的采样参数
        """
        # 获取模型路径
        self.model_path = GlobalConfig.MODEL_PATHS["llm"]

        # 验证模型路径
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型路径不存在：{self.model_path}")

        # 设置环境变量
        os.environ['VLLM_ATTENTION_BACKEND'] = 'TORCH_SDPA'
        os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'

        # VLLM 基础配置
        self.vllm_config = {
            key: GlobalConfig.VLLM_CONFIG.get(key) for key in [
                "tensor_parallel_size",
                "gpu_memory_utilization",
                "trust_remote_code",
                "dtype",
                "max_model_len",
                "enforce_eager",
                "tokenizer_mode",
            ] if GlobalConfig.VLLM_CONFIG.get(key) is not None
        }

        # 场景特定的采样参数
        self.sampling_params = {
            # 摘要生成场景：需要确定性输出
            "summary": SamplingParams(
                temperature=GlobalConfig.VLLM_CONFIG.get("summary_temperature", 0.3),  # 较低的温度，使输出更确定
                max_tokens=GlobalConfig.VLLM_CONFIG.get("summary_max_tokens", 1024),  # 限制生成长度，摘要通常不需要太长
            ),
            # rag 生成场景：需要更多样化的输出
            "rag": SamplingParams(
                temperature=GlobalConfig.VLLM_CONFIG.get("rag_temperature", 0.7),  # 较高的温度，使输出更多样
                top_p=GlobalConfig.VLLM_CONFIG.get("rag_top_p", 0.95),  # 控制采样的概率阈值
                max_tokens=GlobalConfig.VLLM_CONFIG.get("rag_max_tokens", 4096),  # 较长的生成长度，用于详细回答
                presence_penalty=GlobalConfig.VLLM_CONFIG.get("rag_presence_penalty", 0.1),  # 避免重复
                frequency_penalty=GlobalConfig.VLLM_CONFIG.get("rag_frequency_penalty", 0.1),  # 增加多样性
            )
        }

        # 模型实例（懒加载）
        self._model: Optional[LLM] = None
        self._tokenizer: Optional[AutoTokenizer] = None

    @property
    def model(self) -> LLM:
        """获取 VLLM 模型实例（懒加载）
        
        Returns:
            LLM: VLLM 模型实例
            
        Raises:
            Exception: 模型加载失败时抛出
        """
        if self._model is None:
            try:
                logger.info(f"正在加载 VLLM 模型: {self.model_path}")
                # 检查模型目录
                if not os.path.exists(os.path.join(self.model_path, "config.json")):
                    raise FileNotFoundError(f"模型配置文件不存在：{os.path.join(self.model_path, 'config.json')}")

                self._model = LLM(model=self.model_path, **self.vllm_config)
                logger.info("VLLM 模型加载完成")
                # self._model = AutoModelForCausalLM.from_pretrained(self.model_path, trust_remote_code=True)
            except Exception as e:
                logger.error(f"VLLM 模型加载失败: {str(e)}")
                raise
        return self._model

    @property
    def tokenizer(self) -> AutoTokenizer:
        """获取分词器实例（懒加载）
        
        Returns:
            AutoTokenizer: 分词器实例
            
        Raises:
            Exception: 分词器加载失败时抛出
        """
        if self._tokenizer is None:
            try:
                logger.info(f"正在加载分词器: {self.model_path}")
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_path,
                    trust_remote_code=True
                )
                logger.info("分词器加载完成")
            except Exception as e:
                logger.error(f"分词器加载失败: {str(e)}")
                raise
        return self._tokenizer

    def get_model(self, scene: str = "summary") -> Tuple[LLM, AutoTokenizer, SamplingParams]:
        """获取模型、分词器和采样参数
        
        Args:
            scene: 使用场景，可选值：summary（摘要生成）, rag（rag 生成）
            
        Returns:
            Tuple[LLM, AutoTokenizer, SamplingParams]: 模型实例、分词器和采样参数
            
        Raises:
            ValueError: 当场景不支持时抛出
        """
        if scene not in self.sampling_params:
            raise ValueError(f"不支持的场景：{scene}，可选值：summary, rag")
        return self.model, self.tokenizer, self.sampling_params[scene]
