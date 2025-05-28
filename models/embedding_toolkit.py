from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from config import Config

# tokenizer = AutoTokenizer.from_pretrained(Config.MODEL_PATHS['embedding'])
# model = AutoModel.from_pretrained(Config.MODEL_PATHS['embedding']).eval()

def get_embedding(model, tokenizer, text: str) -> np.ndarray:
    """获取文本的向量表示
    
    Args:
        model: Embedding 模型
        text: 文本内容
        
    Returns:
        np.ndarray: 文本的向量表示
    """
    
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    model.eval()
    
    with torch.no_grad():
        outputs = model(**inputs)
    emb = outputs.last_hidden_state[:, 0, :]  # 取 CLS token
    return emb.squeeze().cpu().numpy()

# # 假设你已有 N 个分段文本
# segments = [segment_1, segment_2, ..., segment_N]
# segment_vectors = [get_embedding(s) for s in segments]

# # 表级向量（可存到另一个向量库中）
# table_vector = np.mean(segment_vectors, axis=0)