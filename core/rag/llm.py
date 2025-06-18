# 检查环境变量
import os
import torch
import gc
from typing import Optional

from openai import OpenAI
from utils.common.logger import logger


class LLMManager:
    """LLM模型管理器，实现单例模式"""
    _instance = None
    _client = None
    _local_model = None
    _local_tokenizer = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """初始化LLM管理器"""
        # 检查环境变量
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")

    def get_client(self) -> OpenAI:
        """获取或初始化OpenAI客户端"""
        if self._client is None:
            try:
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                )
            except Exception as e:
                logger.error(f"OpenAI客户端初始化失败: {str(e)}")
                raise
        return self._client

    def get_local_model(self):
        """获取或初始化本地模型（预留接口）"""
        if self._local_model is None:
            try:
                # TODO: 实现本地模型加载逻辑
                # 这里预留本地模型加载的接口
                pass
            except Exception as e:
                logger.error(f"本地模型加载失败: {str(e)}")
                raise
        return self._local_model

    def clear_cache(self):
        """清理模型缓存"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()


# 为了保持向后兼容性，创建全局客户端实例
llm_client = LLMManager.get_instance().get_client()


def create_completion(
    prompt: str,
    model: str = "qwen-turbo-1101",
    temperature: float = 0.2,
    system_prompt: Optional[str] = None,
    use_local: bool = False
) -> str:
    """模型调用
    
    Args:
        prompt: 提示词
        model: 模型名称
        temperature: 温度参数
        system_prompt: 系统提示词
        use_local: 是否使用本地模型
        
    Returns:
        str: 模型响应文本
    """
    try:
        if use_local:
            # TODO: 实现本地模型调用逻辑
            raise NotImplementedError("本地模型调用尚未实现")
        
        # 使用在线API
        client = LLMManager.get_instance().get_client()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=False
        )
        
        return completion.choices[0].message.content
    
    except Exception as e:
        logger.error(f"模型调用失败: {str(e)}")
        raise