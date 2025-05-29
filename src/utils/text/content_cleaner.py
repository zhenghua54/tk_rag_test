"""文档内容清洗
1. 对每页内容进行清洗, 清洗内容包括:
    1.1 提取表格类型的表格数据和图片地址
    1.2 提取图片类型的图片地址和标题信息
    1.3 提取 text 类型的 text 内容
"""

def clean_content(content_list: list) -> list:
    """
    对每页内容进行清洗, 按页分组存储, 返回清洗后的内容列表
    
    清洗内容包括:
        1.1 提取表格类型的表格数据和图片地址
        1.2 提取图片类型的图片地址和标题信息
        1.3 提取 text 类型的 text 内容
        
    Args:
        content_list: 每页内容列表
        
    Returns:
        cleaned_content: 清洗后的内容列表
    """
    
    # 处理每页内容
    cleaned_content = []
    for page in content_list:
        # 获取页码
        page_idx = page['page_idx']
        
        # 提取页面的表格、图片、text 内容
        page_content = []
        for item in page['content']:
            if item['type'] == 'table' or item['type'] == 'merged_table':
                # 表格前后增加特殊标记
                content = f"\n===TABLE_START===\n表格标题:{item['table_caption']}\n表格内容:{item['table_body']}\n表格脚注:{item['table_footnote']}\n表格图片地址:{item['img_path']}\n===TABLE_END===\n"
                page_content.append(content)
            elif item['type'] == 'image':
                # 图片前后增加特殊标记
                content = f"\n===IMAGE_START===\n图片标题:{item['img_caption']}\n图片地址:{item['img_path']}\n图片脚注:{item['img_footnote']}\n===IMAGE_END===\n"
                page_content.append(content)
            elif item['type'] == 'text':
                content = f"{item['text']}\n"
                page_content.append(content)
                
        # 将每页内容组合,并添加页码标记
        page_text = f"\n===PAGE_{page_idx}_START===\n{''.join(page_content)}"
        cleaned_content.append(page_text)
        
    # 返回格式化后的文本内容
    return ''.join(cleaned_content)