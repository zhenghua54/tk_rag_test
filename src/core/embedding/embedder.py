"""Embedding 模块"""
import numpy as np
from sentence_transformers import SentenceTransformer
from torch import Tensor

from config.settings import Config
from src.utils.common.args_validator import Validator


def init_embedding_model() -> SentenceTransformer:
    """初始化向量化模型"""
    return SentenceTransformer(Config.MODEL_PATHS["embedding"])

def embed_text(text: str) -> Tensor:
    """文本向量化"""
    Validator.validate_not_empty(text,"embed_text")

    model = init_embedding_model()
    return model.encode(text)