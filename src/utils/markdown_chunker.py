# -*- coding: utf-8 -*-
"""
本模块用于将 Markdown 文件按章节结构（若存在）或语义块进行切分，
并将切块内容写入 JSONL 文件，供后续向量化与检索使用。
"""

import json
import logging
import os
import re
import sys
from typing import List

from codes.config import Config, get_doc_output_dir

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# 解析md文档内容
def extract_md_structure(md_text):
    """
    从 Markdown 文本中提取章节结构,若没有任何标题,则整体作为"全文"处理.
    :param md_text: Markdown 文件路径
    :return:解析后的 md 文档内容(List)
    """

    # 存储章节路径、内容缓冲、输出结果
    current_path, buffer, sections = [], [], []

    # 新标题前，输出已处理内容
    def flush():
        # 如果缓冲区有内容则将章节路径和内容追加保存
        if buffer:
            sections.append(('>'.join(current_path), '\n'.join(buffer).strip()))
            buffer.clear()

    # 逐行处理
    lines = md_text.split('\n')
    has_heading = False

    for line in lines:
        # 匹配 markdown 的标题行，使用正确的正则表达式
        head_match = re.match(r'^(#+)\s+(.*)', line)
        if head_match:
            has_heading = True
            # 进入到新的标题，输出保存上一节的内容
            flush()
            # 根据#号数量判断标题级别
            level = len(head_match.group(1))
            # 获取标题名称
            title = head_match.group(2).strip()
            # 动态更新章节路径
            current_path = current_path[:level - 1] + [title]
        else:
            # 内容行，保存到内容缓冲列表
            buffer.append(line)
    # 最后内容也要输出保存
    flush()

    if not has_heading:
        logging.warning('未检测到章节标题, 文档将整体作为一个章节处理')
        return [("全文", md_text.strip())]
    return sections


# md 章节解析结果判断
def validate_title(sections: List, result=False) -> bool:
    """判断 markdown 解析后是否有标题"""

    # 提取失败,直接使用语义切割
    if len(sections) == 1 and sections[0][0] == '全文':
        return False
    else:
        return True


# 主函数
def process_md_to_json(config, md_input_file: str):
    """
    对 markdown 文件内容切块
    :param config: 全局配置对象
    :param md_input_file: markdown 文件
    :return: 输出文件路径
    """

    # 输出路径
    output_paths = get_doc_output_dir(config, md_input_file)
    output_jsonl_path = output_paths['output_jsonl_path']  # jsonl 文件输出目录

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_jsonl_path), exist_ok=True)

    # 读取markdown文档内容
    with open(md_input_file, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # 提取章节结构
    sections = extract_md_structure(md_text)
    print(sections)

    # 判断章节情况
    # 有章节,按照章节切块
    if validate_title(sections):
        logging.info('已检测到章节标题, 正在处理...')
        # 打开 jsonl 输出文件
        with open(output_jsonl_path, 'w', encoding='utf-8') as f:
            # 读取每条记录的章节路径和章节内容
            for title_path, content in sections:
                # 拼接章节路径和内容
                full_text = f'{title_path}\n{content}'
                # 内容转 ids
                tokens = config.embedding_tokenizer.encode(full_text)

                json_record = {
                    'title': title_path,  # 章节路径
                    'content': content.strip(),  # 文档内容
                    'tokens': len(tokens)  # token数量
                }
                f.write(json.dumps(json_record, ensure_ascii=False) + '\n')
                logging.info(f'已写入章节:{title_path}[{len(tokens)} tokens]')



    # 没有章节,按照语义切块
    else:
        logging.warning('未检测到章节标题, 文档将整体作为一个章节处理')
        chunks = segment_text(md_text, model_name=config.ollama_model, api_base=config.ollama_url)
        logging.info(f'语义切块完成,写入文件...')
        # 打开 jsonl 输出文件
        with open(output_jsonl_path, 'w', encoding='utf-8') as f:
            # 读取每条记录的章节路径和章节内容
            for content in chunks:
                # 内容转 ids
                tokens = config.embedding_tokenizer.encode(content)

                json_record = {
                    'title': '',  # 章节路径
                    'content': content.strip(),  # 文档内容
                    'tokens': len(tokens)  # token数量
                }
                f.write(json.dumps(json_record, ensure_ascii=False) + '\n')
                logging.info(f'已写入内容:{title_path}[{len(tokens)} tokens]')

    logging.info('Markdown 文档处理为 JSONL 完成')


# 示例调用
if __name__ == '__main__':
    config = Config()

    # 输入文件
    input_file = "/Users/jason/Library/Mobile Documents/com~apple~CloudDocs/PycharmProjects/tk_rag_demo/datas/output_data/公司能力交流口径-2025:02定稿版/公司能力交流口径-2025:02定稿版.md"

    process_md_to_json(config, md_input_file=input_file)
