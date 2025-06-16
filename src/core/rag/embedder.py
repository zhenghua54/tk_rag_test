"""Embedding 模块"""
from sentence_transformers import SentenceTransformer
from torch import Tensor
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings
import torch
import gc

from config.settings import Config
from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.utils.common.logger import logger


class EmbeddingManager:
    """Embedding模型管理器，实现单例模式"""
    _instance = None
    _model = None
    _langchain_model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_model(self) -> SentenceTransformer:
        """获取或初始化SentenceTransformer模型"""
        if self._model is None:
            try:
                self._model = SentenceTransformer(Config.MODEL_PATHS["embedding"])
            except Exception as e:
                logger.error(f"Embedding模型加载失败: {str(e)}")
                raise APIException(ErrorCode.EMBEDDING_MODEL_LOAD_FAILED, str(e))
        return self._model

    def get_langchain_model(self) -> HuggingFaceEmbeddings:
        """获取或初始化Langchain Embedding模型"""
        if self._langchain_model is None:
            try:
                self._langchain_model = HuggingFaceEmbeddings(
                    model_name=Config.MODEL_PATHS["embedding"],
                    model_kwargs={'device': Config.DEVICE}
                )
            except Exception as e:
                logger.error(f"Langchain Embedding模型加载失败: {str(e)}")
                raise APIException(ErrorCode.EMBEDDING_MODEL_LOAD_FAILED, str(e))
        return self._langchain_model

    def clear_cache(self):
        """清理模型缓存"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()


def embed_text(text: str) -> list:
    """文本向量化
    
    Args:
        text (str): 输入文本
        
    Returns:
        list: 1024维的浮点数列表
    """
    try:
        # 获取模型实例
        model = EmbeddingManager.get_instance().get_model()
        
        # 获取向量
        vector = model.encode(text)
        
        # 如果是tensor,转换为numpy数组
        if isinstance(vector, Tensor):
            vector = vector.cpu().numpy()
            
        # 如果是numpy数组,转换为list
        if isinstance(vector, np.ndarray):
            vector = vector.tolist()
            
        # 清理缓存
        EmbeddingManager.get_instance().clear_cache()
        
        return vector
    except Exception as e:
        logger.error(f"文本向量化失败: {str(e)}")
        raise


if __name__ == '__main__':
    import sys

    query = 'Ni好啊'
    result = embed_text(query)
    print(result)
    print(len(result))
    print(type(result))  # 验证返回类型