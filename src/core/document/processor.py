"""处理文档内容, 包括表格、图片、文本等"""

import json
import pandas as pd
from bs4 import BeautifulSoup

from src.utils.common.logger import logger
from src.utils.common.args_validator import Validator
from src.core.llm.extract_summary import extract_table_summary


def extract_key_fields(table_html: str):
    """从 HTML 表格中提取关键字段
    
    Args:
        table_html: 文档片段
    
    Returns:
        str: 关键字段文本
    """
    # 参数验证
    Validator.validate_html_table(table_html)

    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(table_html, 'lxml')

    # 提取所有 td 文本
    tds = soup.find_all('td')
    texts = [td.get_text().strip() for td in tds]

    # 过滤空文本
    texts = [t for t in texts if t]

    return ' '.join(texts)


def html_table_to_markdown(table_html: str) -> str:
    """将 HTML 表格转换为 Markdown 格式
    
    Args:
        table_html (str): HTML 表格字符串
        
    Returns:
        str: Markdown 格式的表格
    """
    # 参数验证
    Validator.validate_html_table(table_html)

    soup = BeautifulSoup(table_html, 'lxml')
    table = soup.find('table')
    if not table:
        return ""

    # 解析为二维列表（按渲染位置展开 col_span/rowspan）
    grid = []
    max_cols = 0
    row_spans = {}  # 记录每个列的 rowspan 状态

    for row_idx, row in enumerate(table.find_all('tr')):
        row_data = []
        col_idx = 0

        # 处理当前行的 rowspan
        for col_idx in range(max_cols):
            if col_idx in row_spans and row_spans[col_idx] > 0:
                row_data.append(row_spans[col_idx])
                row_spans[col_idx] -= 1
            else:
                row_data.append("")

        # 处理当前行的单元格
        cells = row.find_all(['td', 'th'])
        for cell in cells:
            # 跳过已经被 rowspan 占用的列
            while col_idx < len(row_data) and row_data[col_idx] != "":
                col_idx += 1

            colspan = int(cell.get('colspan', '1'))
            rowspan = int(cell.get('rowspan', '1'))
            text = cell.get_text(strip=True)

            # 处理 colspan
            for i in range(colspan):
                if col_idx + i >= len(row_data):
                    row_data.append(text)
                else:
                    row_data[col_idx + i] = text

            # 处理 rowspan
            if rowspan > 1:
                for i in range(colspan):
                    row_spans[col_idx + i] = rowspan - 1

            col_idx += colspan

        max_cols = max(max_cols, len(row_data))
        grid.append(row_data)

    # 规范化所有行的长度
    for i in range(len(grid)):
        if len(grid[i]) < max_cols:
            grid[i].extend([""] * (max_cols - len(grid[i])))

    # 构造 DataFrame
    df = pd.DataFrame(grid)

    # 如果首行可能是 header，则设为表头
    if len(df) > 1:
        df.columns = df.iloc[0]
        df = df[1:]
        df.reset_index(drop=True, inplace=True)

    # 转为 markdown
    return df.to_markdown(index=False)


def process_tables(content_list: list) -> list:
    """更新跨页表格的表格标题
    
    Args:
        content_list: 文档内容列表
        
    Returns:
        list: 更新后的文档内容列表
    """

    # 统计信息
    logger.info(f"开始处理表格标题...")
    total_tables = 0
    existing_captions = 0
    updated_captions = 0
    missing_captions = 0

    # 更新跨页表格的标题信息
    for idx, item in enumerate(content_list):
        # 如果是表格且没有标题
        if item['type'] == 'table':
            total_tables += 1
            # 提取表格摘要个标题
            summary = extract_table_summary(item["table_body"])
            # 增加摘要信息，后续 embedding 使用
            item['table_summary'] = summary['summary'].strip()
            # 提取总结的标题
            summary_title = str(summary.get('title', '')).strip()

            # 表格标题存在
            if item['table_caption'].strip():
                existing_captions += 1
                continue

            # 表格标题不存在，逻辑处理
            else:
                # 获取上一个元素
                last_item = content_list[idx - 1] if idx > 0 else None
                # 获取上个元素的信息作为标题
                last_caption = None
                if last_item:
                    if last_item['type'] == 'table':
                        last_caption = str(last_item.get('table_caption', '')).strip()
                    elif last_item['type'] == 'text':
                        last_caption = str(last_item.get('text', '')).strip()

                # 如果last_caption和summary_title都存在，拼接；否则选择其中一个
                item['table_caption'] = ', '.join([last_caption, summary_title]) if last_caption and summary_title else (last_caption or summary_title)

                # 统计更新标题情况
                if item['table_caption'].strip():
                    updated_captions += 1
                else:
                    missing_captions += 1

    # 输出统计信息
    logger.info(
        f"标题处理完成, 总表格数: {total_tables}, 已有标题: {existing_captions}, 已更新标题: {updated_captions}, 缺少标题: {missing_captions}")

    return content_list


def process_images(content_list: list) -> list:
    """图片批处理脚本,从上一个元素中获取图片标题,并更新图片标题
        1. 遍历所有页面,找出所有type=image且img_caption为空的图片
        2. 从上一个元素中获取图片标题,并更新图片标题,如遇跨页,则从上一个的最后一个元素获取图片标题
        3. 返回处理后的文档内容列表
    Args:
        content_list: 文档内容列表
        
    Returns:
        处理后的文档内容列表
    """
    logger.info(f"开始处理图片标题...")

    # 统计信息
    total_images = 0
    existing_captions = 0
    updated_captions = 0
    missing_captions = 0

    # 更新跨页表格的标题信息
    for idx, item in enumerate(content_list):
        # 如果是图片且没有标题
        if item['type'] == 'image':
            total_images += 1
            # 如果图片标题存在
            if item['img_caption'].strip():
                existing_captions += 1
            else:
                last_item = content_list[idx - 1] if idx > 0 else None
                last_caption = None
                if last_item:
                    if last_item['type'] == 'text':
                        last_caption = str(last_item.get('text', '')).strip()

                # 如果识别到标题，则使用，否则置空
                item['img_caption'] = last_caption if last_caption else ''

                 # 统计更新标题情况
                if item['img_caption'].strip():
                    updated_captions += 1
                else:
                    missing_captions += 1

    # 输出统计信息
    logger.info(
        f"图片标题处理完成, 总图片数: {total_images}, 已有标题: {existing_captions}, 已更新标题: {updated_captions}, 缺少标题: {missing_captions}")

    return content_list


def process_json_file(json_file: str) -> list:
    """处理 JSON 文件中的表格和图片标题

    Args:
        json_file: JSON 文件路径

    Returns:
        list: 处理后的文档内容列表
    """
    # 参数验证
    Validator.validate_file(json_file)

    # 读取 JSON 文件
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            content_list = json.load(f)

        # 验证内容类型
        if not isinstance(content_list, list):
            raise ValueError("JSON 内容必须是列表类型")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析错误: {str(e)}")

    # 处理表格标题
    content_list = process_tables(content_list)

    # 处理图片标题
    content_list = process_images(content_list)

    return content_list
