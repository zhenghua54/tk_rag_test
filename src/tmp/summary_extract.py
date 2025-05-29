"""摘要提取"""

from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from src.config.settings import Config




def extract_summary(model, tokenizer, text: str) -> str:
    """提取摘要
    
    Args:
        model: 模型
        tokenizer: 分词器
        text: 文本内容
        
    Returns:
        str: 摘要
    """

    model.eval()

    with torch.no_grad():
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        outputs = model(**inputs)
        summary = outputs.last_hidden_state[:, 0, :]
    
    
