"""
API 测试模块
用于测试项目中所有主要功能的接口

测试流程：
1. 文件上传测试
2. 文件格式转换测试
3. 文件解析测试
"""
import os
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
from src.utils.database.file_db import get_non_pdf_files, get_pdf_files,search_file_info

# 2. 测试跨页表格合并
from src.utils.json_toolkit.parser import parse_json_file
from src.utils.table_toolkit.table_merge import TableMerge

# 3. 测试图片标题提取
from src.utils.image_toolkit.image_title import extract_image_title

# 4. 测试文档内容清洗
from src.utils.content_cleaner import clean_content
from src.utils.document_path import get_doc_output_path


def test_parse_file(pdf_file_paths: list[dict]):
    """测试文件解析
    
    Args:
        pdf_file_paths (list[dict]): 文件路径列表
    """
    
    if pdf_file_paths is None:
        pdf_file_paths = get_pdf_files()
        
    # 测试文件解析
    output_paths = parse_pdf_file(pdf_file_paths)
    # 更新解析结果到数据库
    update_parse_file_records_in_db(output_paths)
    print(f'文件解析完成,共计{len(pdf_file_paths)}个文件')

def files_translate_test(file_path: str):
    """测试文件转换
    
    Args:
        file_path (str): 文件路径
    """
    
    if file_path is None:
        file_path = Config.PATHS['origin_data']

    # 过滤非法文件
    file_infos = file_filter(file_path)
    # 将文件信息保存到数据库中
    update_file_records_in_db(file_infos)

    # 1.2 获取非 PDF 文件
    non_pdf_file_paths = get_non_pdf_files()
    # 测试文件转换
    pdf_file_paths = translate_file(non_pdf_file_paths)
    # 更新转换后的文件信息到数据库中
    update_file_path_in_db(pdf_file_paths)
    print(f'文件转换完成,共计{len(non_pdf_file_paths)}个文件')    
    

def clean_content_test(doc_id: str):
    """测试文档内容清洗"""
    
    if doc_id is None:
        logger.error(f"文档ID不存在")
        return
    
    # 获取文档信息
    logger.info(f"查询文档: {doc_id}")
    file_info = search_file_info(doc_id)
    
    if file_info is None:
        logger.error(f"未查询到文档信息")
        return
    elif file_info['source_document_json_path'] is None:
        logger.error(f"文档未解析")
        return
    
    source_file_path = file_info['source_document_pdf_path']
    
    if source_file_path is None:
        logger.error(f"文档未转换为 PDF 格式")
        return
        
    
    # 获取文档内容
    file_name = file_info['source_document_name']
    json_file_path = file_info['source_document_json_path']
    
    # 获取输出路径
    output_path = get_doc_output_path(source_file_path)['output_path']
    
    logger.info(f"开始清洗文档, doc_id: {doc_id}, 文件名: {file_name}")
    # 按页合并内容
    content_list = parse_json_file(json_file_path)
    
    # 跨页表格合并
    table_merge = TableMerge()
    merged_content_list = table_merge.merge_cross_page_tables(content_list)
    
    # 图片标题处理
    merged_content_list = extract_image_title(merged_content_list)
    
    # 文档内容提取格式化
    content_text = clean_content(merged_content_list)
    
    # 保存清洗后的文档内容
    with open(os.path.join(output_path,  f"{file_name}_cleaned.txt"), "w", encoding="utf-8") as f:
        f.write(content_text)
    logger.info(f"文档内容清洗完成,保存到: {output_path}")



if __name__ == "__main__":
    # 测试文件转换
    file_dir = "/home/wumingxing/tk_rag/datas/raw"
    test_files_translate(file_dir)
    
    # 测试文件解析
    file_path = "/home/wumingxing/tk_rag/datas/raw/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225.pdf"
    test_parse_file([file_path])
    
    # 测试文件清洗
    doc_id = "215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83"
    clean_content_test(doc_id)
    

    


    # 检查文档内容中的所有元素类型
    # type_set = {}
    # for page in content_list:
    #     for item in page['content']:
    #         type_set[item['type']] = type_set.get(item['type'], 0) + 1
    # print(type_set)
    

    # # 遍历所有页面,打印包含图片的页面信息
    # for page in content_list:
    #     # 检查页面是否包含图片且图片标题为空
    #     has_image = any(item['type'] == 'image' for item in page['content'])
    #     if has_image:
    #         print(f"页码: {page['page_idx']}")
    #         print("页面内容:")
    #         for idx,item in enumerate(page['content']):
    #             if item['type'] == 'image':
    #                 print(f'上一个元素内容:{page["content"][idx-1]}')
    #                 print(item)
    #                 print(f'下一个元素内容:{page["content"][idx+1] if idx+1 < len(page["content"]) else "None"}')
    #                 print("-" * 50)