"""更新跨页表格的表格标题和脚注"""

def update_cross_page_table_metadata(content_list: list) -> list:
    """更新跨页表格的表格标题和脚注
    
    Args:
        content_list: 文档内容列表
        
    Returns:
        list: 更新后的文档内容列表
    """
    
    for page_idx, page in enumerate(content_list):
        # 获取页面第一个元素
        item = page['content'][0]
        # 标题为空且上一页最后一个元素为表格时,标题复用
        if item['type'] == 'table' and item['table_caption'] is None:
            last_item = content_list[page_idx - 1]['content'][-1]
            if last_item['type'] == 'table':
                item['table_caption'] = last_item['table_caption']
                
    return content_list







