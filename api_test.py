"""
API 测试模块
用于测试项目中所有主要功能的接口

测试流程：
1. 文件上传测试
2. 文件格式转换测试
3. 文件解析测试
"""

import sys
from pathlib import Path
from rich import print

# 测试相似度
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.utils.common.logger import logger

# 1. 测试文件处理流程
from src.utils.file_toolkit import (
    file_filter,
    update_file_records_in_db,
    translate_file,
    update_file_path_in_db,
    parse_pdf_file,
    update_parse_file_records_in_db
)
from src.utils.database.file_db import get_non_pdf_files, get_pdf_files

# 2. 测试内容清洗
from src.utils.json_toolkit.parser import parse_json_file
from src.utils.table_toolkit.table_merge import TableMerge






if __name__ == "__main__":
    # 1. 测试文件处理流程
    # file_path = "/home/wumingxing/tk_rag/datas/raw/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225.pdf"
    # file_path = Config.PATHS['origin_data']

    # 1.1 过滤非法文件
    # file_infos = file_filter(file_path)
    # print(file_infos)
    # - 将文件信息保存到数据库中
    # update_file_records_in_db(file_infos)

    # 1.2 获取非 PDF 文件
    # non_pdf_file_paths = get_non_pdf_files()
    # print(non_pdf_file_paths)
    # - 测试文件转换
    # non_pdf_file_paths = [
    #     {
    #         'doc_id': '20a75788dfafe066ca059b1ede6bb9e49ba207946586c1f03f2ae7816ead0f57',
    #         'source_document_path': '/home/wumingxing/tk_rag/datas/raw/公司能力交流口径-202502定稿版.docx'
    #     },
    # ]
    # pdf_file_paths = translate_file(non_pdf_file_paths)
    # print(pdf_file_paths)
    # - 更新转换后的文件信息到数据库中
    # update_file_path_in_db(pdf_file_paths)

    # 1.3 获取所有 PDF 文件信息
    # pdf_file_paths = get_pdf_files()
    # print(pdf_file_paths)

    # 1.4 测试文件解析
    # output_paths = parse_pdf_file(pdf_file_paths)
    # print(output_paths)
    # - 更新解析结果到数据库
    # update_parse_file_records_in_db(output_paths)

    # 2. 测试内容清洗
    json_file_path = "/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225_content_list.json"

    # 2.1 文档合并
    content_list = parse_json_file(json_file_path)
    # print(content_list)

    # 2.2 表格合并
    table_merge = TableMerge()
    new_content_list = table_merge.process_tables(content_list)
    # print(new_content_list)


    


