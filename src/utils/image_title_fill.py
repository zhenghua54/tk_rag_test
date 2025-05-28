"""文档中的图片处理"""

from src.utils.common.logger import logger

def extract_image_title(content_list: list) -> list:
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
    
    