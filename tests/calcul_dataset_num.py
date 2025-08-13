import os
import hashlib
import pandas as pd
from pathlib import Path

# 统计每个数据集的“唯一文档数”（基于文档内容的 md5 去重），而不是数据行数

base_dir = Path("/home/zh/gitClone/tk_rag/data/ragbench")
datasets = [
    "covidqa", "delucionqa", "expertqa", "hagrid",
    "msmarco", "techqa", "cuad", "emanual",
    "finqa", "hotpotqa", "pubmedqa", "tatqa"
]

def iter_documents_from_df(df: pd.DataFrame):
    # 兼容 documents 字段为 str / list / numpy 对象等情况
    if "documents" not in df.columns:
        return
    for docs in df["documents"].tolist():
        # 标准化为 list[str]
        if isinstance(docs, str):
            yield docs
        elif hasattr(docs, "__iter__") and not isinstance(docs, str):
            try:
                for d in list(docs):
                    yield str(d)
            except Exception:
                yield str(docs)
        elif docs:
            yield str(docs)

for dataset in datasets:
    dataset_dir = base_dir / dataset
    if not dataset_dir.exists():
        print(f"{dataset}: 路径不存在，跳过")
        continue

    unique_docs = set()
    for file in os.listdir(dataset_dir):
        if file.endswith(".parquet"):
            path = dataset_dir / file
            df = pd.read_parquet(path)
            for doc in iter_documents_from_df(df):
                doc_str = (doc or "").strip()
                if not doc_str:
                    continue
                h = hashlib.md5(doc_str.encode()).hexdigest()
                unique_docs.add(h)

    print(f"{dataset}: {len(unique_docs)} 个唯一文档")
