"""文档内容词嵌入"""

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel


from models.embedding_toolkit import get_embedding


# 获取文本块,进行 embedding
def get_text_embedding(segment_list: List[str]) -> np.ndarray:
    """获取文本的向量表示
    
    Args:
        segment_list: 文本内容列表
        
    Returns:
        np.ndarray: 文本的向量表示
    """
    
    # 初始化模型和分词器
    model = AutoModel.from_pretrained(Config.MODEL_PATHS['embedding'])
    tokenizer = AutoTokenizer.from_pretrained(Config.MODEL_PATHS['embedding'])
    
    # 初始化向量列表:vector, doc_id, segment_id, document_name, summary_text, partment, create_time, update_time
    segment_vectors = []
    # 遍历文档,逐条存储向量
    for segment in segment_list:
        segment_embedding = get_embedding(model, tokenizer, segment)




# 处理表格内容,若表格内容过长,则进行二次切分, 返回切分后的文本列表
            
            table_content = match.group(3).strip()
            table_str = format_table_to_str(table_content)
            
            
            
            if len(table_str) > 800:
                # 根据固定长度进行切割
                chunk_list = text_splitter.split_text(table_str)
                
                # 
                segment_vectors = [get_embedding(s) for s in chunk_list]
                # 获取表格的向量表示
            table_vector = get_embedding(table_str)
                table_vector = np.mean(segment_vectors, axis=0)