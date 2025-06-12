"""Embedding 模块"""
from sentence_transformers import SentenceTransformer
from torch import Tensor
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings


from config.settings import Config
from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.utils.common.logger import logger



def init_embedding_model() -> SentenceTransformer:
    """初始化向量化模型
    
    Returns:
        SentenceTransformer: 向量化模型实例
    """
    try:
        embed_model = SentenceTransformer(Config.MODEL_PATHS["embedding"])
    except Exception as e :
        raise APIException(ErrorCode.EMBEDDING_MODEL_LOAD_FAILED,str(e))
    return embed_model



def init_langchain_embeddings() -> HuggingFaceEmbeddings:
    """初始化 Langchain 的 HuggingFaceEmbeddings
    
    Returns:
        HuggingFaceEmbeddings: Langchain 的 embedding 实例
    """
    return HuggingFaceEmbeddings(
        model_name=Config.MODEL_PATHS["embedding"],
        model_kwargs={'device': Config.DEVICE}
    )


def embed_text(text: str) -> list:
    """文本向量化
    
    Args:
        text (str): 输入文本
        
    Returns:
        list: 1024维的浮点数列表
    """
    try:
        model = init_embedding_model()
        # 获取向量
        vector = model.encode(text)
        # 如果是tensor,转换为numpy数组
        if isinstance(vector, Tensor):
            vector = vector.numpy()
        # 如果是numpy数组,转换为list
        if isinstance(vector, np.ndarray):
            vector = vector.tolist()
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