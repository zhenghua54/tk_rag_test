import os
import hashlib
import pandas as pd
from pathlib import Path

base_dir = Path("/home/zh/gitClone/tk_rag/data/ragbench")
output_dir = Path("./ragbench_txt_export")
datasets = ["delucionqa", "hagrid", "msmarco", "techqa", "emanual", "hotpotqa", "tatqa"]

def export_dataset_to_txt(dataset_name: str):
    dataset_path = base_dir / dataset_name
    if not dataset_path.exists():
        print(f"❌ 数据集路径不存在: {dataset_path}")
        return

    save_dir = output_dir / dataset_name
    save_dir.mkdir(parents=True, exist_ok=True)

    unique_docs = set()
    count = 0

    for file in os.listdir(dataset_path):
        if file.endswith(".parquet"):
            df = pd.read_parquet(dataset_path / file)
            if "documents" not in df.columns:
                continue
            for docs in df["documents"]:
                if isinstance(docs, str):
                    items = [docs]
                elif hasattr(docs, "__iter__") and not isinstance(docs, str):
                    try:
                        items = [str(d) for d in docs if str(d).strip()]
                    except Exception:
                        items = [str(docs)]
                else:
                    items = [str(docs)]
                
                for doc in items:
                    text = doc.strip()
                    if not text:
                        continue
                    h = hashlib.md5(text.encode()).hexdigest()
                    if h not in unique_docs:
                        unique_docs.add(h)
                        count += 1
                        with open(save_dir / f"doc_{count:05d}.txt", "w", encoding="utf-8") as f:
                            f.write(text)

    print(f"✅ {dataset_name}: {count} 个唯一文档导出完成 -> {save_dir}")

if __name__ == "__main__":
    output_dir.mkdir(parents=True, exist_ok=True)
    for ds in datasets:
        export_dataset_to_txt(ds)
