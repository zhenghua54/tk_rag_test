import sys
import os
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)

from src.core.document.parser import parse_pdf_file, parse_office_file
from config.settings import Config
from src.utils.common.logger import logger
from src.database.mysql.connection import connect_mysql
async def process_document(file_path: str) -> dict:
    """处理文档主流程
    
    1. 获取文件后缀, 根据文件类型进行转换并解析
    2. 保存解析文件信息保存到数据库
    3. 清洗 json 文件信息, 对表格\图片等内容进行处理
    4. 进行分块\嵌入,分别保存到 mysql 和 milvus 中
    
    Args:
        file_path: 文件路径
        
    Returns:
        处理结果字典
    """
    # 判断文件是否存在
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return None
    
    # 获取文档后缀
    file_ext = os.path.splitext(file_path)[1]
    
    # 根据文档类型进行转换并解析
    if file_ext == '.pdf':
        pdf_path = file_path
        file_info = parse_pdf_file(pdf_path)
    elif file_ext in Config.SUPPORTED_FILE_TYPES["libreoffice"]:
        pdf_path = parse_office_file(file_path)
        if not pdf_path:
            logger.error(f"未获取到转换后的 PDF 文件: {file_path}")
            return None
        file_info = parse_pdf_file(pdf_path)
    else:
        logger.error(f"暂不支持该格式文件,目前支持的格式为: {Config.SUPPORTED_FILE_TYPES['all']}")
        return None
    
    json_path = file_info["json_path"]
    image_path = file_info["image_path"]
    doc_name = file_info["doc_name"]
    output_dir = file_info["output_dir"]
    
    
    
    # 更新 mysql 数据库信息: pdf_path, json_path, image_path
    
    


    
    # 读取 JSON 文件
    with open(json_path, 'r', encoding='utf-8') as f:
        content_list = json.load(f)
    

    
    # 4. 保存到数据库
    doc_id = save_document_info({
        "file_path": file_path,
        "content": markdown_content
    })
    
    return {"doc_id": doc_id, "content": markdown_content}

if __name__ == "__main__":
    # 测试数据库连接
    try:
        # 运行测试
        mysql = connect_mysql()
        mysql.use_db()
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
    finally:
        if 'mysql' in locals():
            mysql.close()