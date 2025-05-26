"""文档内容清洗
1. 对每页内容进行清洗, 清洗内容包括:
    1.1 提取表格类型的表格数据和图片地址
    1.2 提取图片类型的图片地址和标题信息
    1.3 提取 text 类型的 text 内容
"""

def clean_content(content_list: list) -> list:
    """
    对每页内容进行清洗, 清洗内容包括:
        1.1 提取表格类型的表格数据和图片地址
        1.2 提取图片类型的图片地址和标题信息
        1.3 提取 text 类型的 text 内容
    """
    content_text = ""
    for page in content_list:
        for item in page['content']:
            if item['type'] == 'table':
                table_content = f"表格标题:{item['table_caption']}\n表格内容:{item['table_body']}\n表格图片地址:{item['img_path']}\n"
                content_text += table_content
            elif item['type'] == 'image':
                image_content = f"图片标题:{item['img_caption']}\n图片地址:{item['img_path']}\n"
                content_text += image_content
            elif item['type'] == 'text':
                text_content = f"{item['text']}\n"
                content_text += text_content
    return content_text.strip()