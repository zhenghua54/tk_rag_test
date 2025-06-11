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
import json
from pathlib import Path
from rich import print

from src.utils.doc_toolkit import compute_file_hash

# 测试相似度

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from config.settings import Config
from src.utils.common.logger import logger


def get_file_info(doc_path: str) -> dict:
    """获取文件信息

    Args:
        doc_path (str): 文件路径

    Returns:
        dict: 文件信息，包含 doc_id、source_document_name、source_document_type 等
    """
    doc_path = Path(doc_path)

    # 获取文件 SHA256 哈希值
    file_sha256 = compute_file_hash(str(doc_path.resolve()))

    # 构建文件信息数据
    # PDF 文件直接更新 PDF 文件路径
    if doc_path.suffix == '.pdf':
        file_info = {
            'doc_id': file_sha256,
            'source_document_name': doc_path.stem,
            'source_document_type': doc_path.suffix,
            'source_document_pdf_path': str(doc_path.resolve()),
        }
    else:
        file_info = {
            'doc_id': file_sha256,
            'source_document_name': doc_path.stem,
            'source_document_type': doc_path.suffix,
            'source_document_path': str(doc_path.resolve()),
        }

    return file_info

def file_filter(doc_dir: str) -> list[dict]:
    """文档过滤, 去除系统文件和配置文件中未指定的文件格式

    Args:
        doc_dir (str): 源文件路径

    Returns:
        list[dict]: 文件信息列表
    """
    file_infos = []
    doc_dir = Path(doc_dir)
    # 递归获取指定目录下的所有文件及文件夹
    for file in doc_dir.rglob("*"):
        # 非文件或以 '.' 开头的文件（如隐藏文件）直接跳过
        if not file.is_file() or file.name.startswith('.'):
            continue
        if file.suffix not in Config.SUPPORTED_FILE_TYPES["all"]:
            continue
        file_info = get_file_info(str(file.resolve()))
        file_infos.append(file_info)
    return file_infos


def test_parse_file(pdf_file_paths: list[dict] = None):
    """测试文件解析
    
    Args:
        pdf_file_paths (list[dict]): 文件路径列表
    """
    
        
    # 测试文件解析
    output_paths = parse_pdf_file(pdf_file_paths)
    # 更新解析结果到数据库
    update_parse_file_records_in_db(output_paths)
    print(f'文件解析完成,共计{len(pdf_file_paths)}个文件')

def files_translate_test(doc_path: str):
    """测试文件转换
    
    Args:
        doc_path (str): 文件路径
    """
    
    if doc_path is None:
        doc_path = Config.PATHS['origin_data']

    # 过滤非法文件
    file_infos = file_filter(doc_path)
    # 将文件信息保存到数据库中
    update_file_records_in_db(file_infos)

    # 1.2 获取非 PDF 文件
    non_pdf_file_paths = select_non_pdf_files()
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
    file_info = select_file_info(doc_id)
    
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
    doc_content = parse_json_file(json_file_path)
    
    # 跨页表格合并
    # table_merge = TableMerge()
    # merged_content_list = table_merge.merge_cross_page_tables(doc_content)
    # 更新跨页表格的表格标题和脚注
    merged_content_list = process_tables(doc_content)
    
    # 图片标题处理
    merged_content_list = process_images(merged_content_list)
    
    # 文档内容提取格式化
    content_text = clean_content(merged_content_list)
    
    # 保存清洗后的文档内容
    output_path = os.path.join(output_path,  f"{file_name}_cleaned.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content_text)
    
    return output_path



if __name__ == "__main__":
    # 测试文件转换
    # file_dir = "/home/wumingxing/tk_rag/datas/raw"
    # test_files_translate(file_dir)
    
    # 测试文件解析
    # file_path = "/home/wumingxing/tk_rag/datas/raw/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225.pdf"
    # test_parse_file([{'source_document_pdf_path': file_path,'source_document_name':'天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225'}])
    
    # 测试文件清洗
    doc_id = "215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83"
    output_cleaned_path = clean_content_test(doc_id)
    # print(f"文档内容清洗完成,保存到: {output_cleaned_path}")
    
    # 测试文本分块
    with open(output_cleaned_path, "r", encoding="utf-8") as f:
        file_content = f.read()
    chunks = segment_content(file_content)
    # 保存分块内容到目标文件
    chunk_filename = os.path.basename(output_cleaned_path).replace(".txt", "_chunks.json")
    output_chunks_path = os.path.join(Config.PATHS['processed_data'], "天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225",chunk_filename)
    with open(output_chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=4)
    # print(f"文本分块完成,保存到: {output_chunks_path}, 共计{len(chunks['chunks'])}个文本块")
    # 最长文本块
    max_chunk_len = max(len(chunk['content']) for chunk in chunks['chunks'])
    # 最长文本块内容
    max_chunk_content = max(chunks['chunks'], key=lambda x: len(x['content']))['content']
    print(f"最长文本块长度: {max_chunk_len}")
    print(f"最长文本块内容: {max_chunk_content}")
    
    # 提取表格文本内容后计算长度
    # table_body_df = format_html_table(max_chunk_content)['table_df']
    # 使用新的表格格式化函数
    formatted_table = format_table_to_str(max_chunk_content)
    print(f"\n=== 格式化后的表格内容 ===")
    print(formatted_table)
    print(f"\n格式化后表格长度: {len(formatted_table)}")
    
    # 保存格式化后的表格内容
    with open("formatted_table_for_embedding.txt", "w", encoding="utf-8") as f:
        f.write(formatted_table)
    print("格式化表格已保存到 formatted_table_for_embedding.txt")
    
    
    

    # 检查文档内容中的所有元素类型
    # type_set = {}
    # for page in doc_content:
    #     for item in page['content']:
    #         type_set[item['type']] = type_set.get(item['type'], 0) + 1
    # print(type_set)
    

    # # 遍历所有页面,打印包含图片的页面信息
    # for page in doc_content:
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
    
    
    # 测试文本分块
    # 初始化向量库连接
    # milvus_db = MilvusDB()
    # milvus_db.init_database()

    # # 加载集合 （如果已经加载过，则不需要加载）
    # try:
    #     milvus_db.client.load_collection(milvus_db.collection_name)
    #     logger.info(f"成功加载集合: {milvus_db.collection_name}")
    # except Exception as e:
    #     logger.error(f"加载集合时出错: {str(e)}")
    
    
