"""用来排查未存储到 mysql 数据库中的本地文档有哪些, 包括 raw 目录和 processed 目录

使用方法:
- 只查找: python scripts/check_or_clean_unused_docs.py
- 查找并删除未入库数据: python scripts/check_or_clean_unused_docs.py --delete

"""
import argparse
import os
from pathlib import Path

import pymysql
from typing import Set
import sys

sys.path.append('/home/wumingxing/tk_rag')

from config.global_config import GlobalConfig


# ==== 1. 获取数据库中所有 doc_name ====
def fetch_doc_names_from_db() -> Set[str]:
    conn = pymysql.connect(
        host=GlobalConfig.MYSQL_CONFIG["host"],
        user="root",
        password="Tk@654321",
        database=GlobalConfig.MYSQL_CONFIG["database"],
        port=GlobalConfig.MYSQL_CONFIG["port"],
        charset=GlobalConfig.MYSQL_CONFIG["charset"],
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT doc_name,doc_ext FROM doc_info")
            rows = cursor.fetchall()
            return set(row[0] for row in rows)
    finally:
        conn.close()


# ==== 2. 遍历目录并查找未入库项目 ====
def find_untracked_files(doc_names: Set[str]) -> dict:
    raw_dir = Path(GlobalConfig.PATHS["origin_data"])
    processed_dir = Path(GlobalConfig.PATHS["processed_data"])

    # 1. 获取原始文件的 stem 名（去后缀）
    raw_file_stems = set(f.stem for f in raw_dir.rglob('*') if f.is_file())

    # 2. processed 目录名（与 doc_name 对齐）
    processed_dirs = set(d for d in os.listdir(processed_dir)
                         if (processed_dir / d).is_dir())

    # 3. 直接对比
    untracked_raw = sorted(raw_file_stems - doc_names)
    untracked_processed = sorted(processed_dirs - doc_names)

    return {
        "untracked_raw_files": untracked_raw,
        "untracked_processed_dirs": untracked_processed
    }

# ==== 3. 删除未入库的文件和目录 ====
def delete_untracked_files(untracked: dict):
    raw_dir = Path(GlobalConfig.PATHS["origin_data"])
    processed_dir = Path(GlobalConfig.PATHS["processed_data"])

    print("\n=== 删除 RAW 中未入库文件 ===")
    for f in raw_dir.rglob('*'):
        if f.is_file() and f.stem in untracked["untracked_raw_files"]:
            print(f"删除文件: {f}")
            f.unlink()

    print("\n=== 删除 PROCESSED 中未入库文件夹 ===")
    for d in processed_dir.iterdir():
        if d.is_dir() and d.name in untracked["untracked_processed_dirs"]:
            print(f"删除目录: {d}")
            os.system(f'rm -rf "{d}"')  # 更稳妥做法是 shutil.rmtree(d)


# ==== 4. 主程序入口 ====
def main():
    parser = argparse.ArgumentParser(description="查找或删除未入库文档")
    parser.add_argument("--delete", action="store_true", help="启用后将删除未入库的文件或目录")
    args = parser.parse_args()

    doc_names_in_db = fetch_doc_names_from_db()
    result = find_untracked_files(doc_names=doc_names_in_db)

    print("=== 未入库 RAW 文件 ===")
    print(" - 无" if not result["untracked_raw_files"]
          else "\n".join(f" - {x}" for x in result["untracked_raw_files"]))

    print("\n=== 未入库 PROCESSED 文件夹 ===")
    print(" - 无" if not result["untracked_processed_dirs"]
          else "\n".join(f" - {x}" for x in result["untracked_processed_dirs"]))

    if args.delete:
        delete_untracked_files(result)


if __name__ == "__main__":
    main()
