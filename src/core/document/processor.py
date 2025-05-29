"""处理文档内容, 包括表格、图片、文本等"""

import pandas as pd
from bs4 import BeautifulSoup


def extract_key_fields(segment):
    """从 HTML 表格中提取关键字段
    
    Args:
        segment: 文档片段
    
    Returns:
        str: 关键字段文本
    """
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(segment, 'lxml')
    
    # 提取所有 td 文本
    tds = soup.find_all('td')
    texts = [td.get_text().strip() for td in tds]
    
    # 过滤空文本
    texts = [t for t in texts if t]
    
    return ' '.join(texts)


def html_table_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table')
    if not table:
        return ""

    # 解析为二维列表（按渲染位置展开 colspan/rowspan）
    grid = []
    max_cols = 0

    for row in table.find_all('tr'):
        row_data = []
        cells = row.find_all(['td', 'th'])
        for cell in cells:
            colspan = int(cell.get('colspan', 1))
            rowspan = int(cell.get('rowspan', 1))
            text = cell.get_text(strip=True)
            for _ in range(colspan):
                row_data.append(text)
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
    """更新跨页表格的表格标题和脚注
    
    Args:
        content_list: 文档内容列表
        
    Returns:
        list: 更新后的文档内容列表
    """
    
    # 更新跨页表格的表格标题
    for page_idx, page in enumerate(content_list):
        # 获取页面第一个元素
        item = page['content'][0]
        # 标题为空且上一页最后一个元素为表格时,标题复用
        if item['type'] == 'table' and item['table_caption'] is None:
            last_item = content_list[page_idx - 1]['content'][-1]
            if last_item['type'] == 'table':
                item['table_caption'] = last_item['table_caption']
                
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
    
    for page_idx, page in enumerate(content_list):
        # 遍历当前页的所有元素
        for idx, item in enumerate(page['content']):
            if item['type'] == 'image':
                total_images += 1
                
                # 已有标题
                if item.get('img_caption'):
                    existing_captions += 1
                    continue
                    
                # 不是当前页的第一个元素,且上一个元素type=text
                if idx > 0 and page['content'][idx-1]['type'] == 'text':
                    item['img_caption'] = page['content'][idx-1]['text']
                    updated_captions += 1
                    # logger.info(f"第 {page_idx+1} 页图片更新标题: {item['img_caption']}")
                
                # 当前页的第一个元素,需要从上一个页的最后一个元素获取图片标题
                elif idx == 0 and page_idx > 0:
                    # 获取上一个页的最后一个元素
                    last_item = content_list[page_idx-1]['content'][-1]
                    if last_item['type'] == 'text':
                        item['img_caption'] = last_item['text']
                        updated_captions += 1
                        # logger.info(f"第 {page_idx+1} 页图片更新标题: {item['img_caption']}")
                    else:
                        missing_captions += 1
                        # logger.warning(f"第 {page_idx+1} 页图片未找到标题")
                else:
                    missing_captions += 1
                    # logger.warning(f"第 {page_idx+1} 页图片未找到标题")
    
    # 输出统计信息
    logger.info(f"图片标题处理完成, 总图片数: {total_images}, 已有标题: {existing_captions}, 已更新标题: {updated_captions}, 缺少标题: {missing_captions}")
                
    return content_list

def format_html_table_to_markdown(html: str) -> str:
    """将 HTML 表格转换为 Markdown 表格
    
    Args:
        html: HTML 表格
        
    Returns:
        str: Markdown 表格
    """
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table')
    if not table:
        return ""

    # 解析为二维列表（按渲染位置展开 colspan/rowspan）
    grid = []
    max_cols = 0

    for row in table.find_all('tr'):
        row_data = []
        cells = row.find_all(['td', 'th'])
        for cell in cells:
            colspan = int(cell.get('colspan', 1))
            rowspan = int(cell.get('rowspan', 1))
            text = cell.get_text(strip=True)
            for _ in range(colspan):
                row_data.append(text)
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