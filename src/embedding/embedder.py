"""Embedding 模块"""

from sentence_transformers import SentenceTransformer

from config.settings import Config

def init_embedding_model() -> SentenceTransformer:
    """初始化向量化模型"""
    return SentenceTransformer(Config.MODEL_PATHS["embedding"])

def embed_text(text: str, model: SentenceTransformer) -> np.ndarray:
    """文本向量化"""
    return model.encode(text)