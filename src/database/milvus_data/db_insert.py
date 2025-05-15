"""
将处理后的数据插入到 Milvus 中
"""

import os
import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")
from rich import print
import pandas as pd
from sentence_transformers import SentenceTransformer
from src.database.build_milvus_db import create_milvus_db
from src.database.file_chunk import process_directory

from config import Config

# 创建数据库实例:初始化数据库
db = create_milvus_db()

# 加载集合
try:
    db.client.load_collection(Config.MILVUS_CONFIG["collection_name"])
    print(f"成功加载集合: {Config.MILVUS_CONFIG['collection_name']}")
except Exception as e:
    print(f"加载集合时出错: {str(e)}")

# 获取文件切块内容,存入向量数据库
df = process_directory(Config.PATHS["origin_data"])
df_to_dict = df.to_dict(orient="records")

# 初始化 Embedding 模型
model = SentenceTransformer(Config.MODEL_PATHS["embedding"])

# 遍历数据,进行Embedding
for row in df_to_dict:
    row['vector'] = model.encode(row['text_chunk'])

print(f"总共处理了 {len(df_to_dict)} 条数据")


def truncate_text(text: str, max_length: int) -> str:
    """截断文本到指定长度"""
    if not isinstance(text, str):
        return ""
    return text[:max_length]


# 准备插入数据，只保留集合中定义的字段
insert_data = []
for row in df_to_dict:
    # 确保所有字段的长度符合要求
    text_chunk = truncate_text(row['text_chunk'], 100000)
    title = truncate_text(row['text_chunk'], 1000)
    document_source = truncate_text(row['document_source'], 1000)
    partment = truncate_text(row['partment'], 1000)
    role = truncate_text(row['role'], 1000)
    doc_id = truncate_text(row['doc_id'], 1000)

    insert_data.append({
        'id': row['id'],
        'vector': row['vector'],
        'text_chunk': text_chunk,
        'title': title,
        'document_source': document_source,
        'partment': partment,
        'role': role,
        'doc_id': doc_id
    })

print(f"准备插入 {len(insert_data)} 条数据")

# 插入数据
try:
    result = db.insert_data(insert_data)
    print("数据插入成功！")
except Exception as e:
    print(f"插入数据时出错: {str(e)}")
