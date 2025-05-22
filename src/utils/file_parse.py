"""
文档解析模块,目前使用 MinerU 工具进行解析
1. 根据 mysql 数据库的文件路径提取文件
2. 将所有文件使用 libreoffice 转换为 PDF 格式
3. 调用 MinerU 工具进行解析
4. 保存解析后的文件
5. 更新解析后的文件路径到 mysql 记录
"""


from src.api.mineru_api import parse_pdf
from src.database.mysql_connect import connect_mysql
from src.utils.get_logger import logger



def get_pdf_file_path_from_db() -> list[dict]:
    """
    从数据库获取文件的 PDF 地址

    Returns:
        file_paths (list[dict]): 文件的 PDF 地址，包含 doc_id、source_document_name 和 source_document_pdf_path
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = '''select doc_id, source_document_name, source_document_pdf_path 
                from file_info 
                where source_document_pdf_path is not null'''
        pdf_paths = mysql.select_data(sql)   
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
        return []
    finally:
        if 'mysql' in locals():
            mysql.close()

    return pdf_paths if pdf_paths is not None else []


def parse_file_from_db() -> list[dict]:
    """
    从数据库获取文件地址并交由 MinerU 解析后, 返回 markdown 和 json 文件的保存路径
    
    Returns:
        list: 解析后的文件路径信息列表，每个元素包含 doc_id 和输出路径信息
    """
    # 从数据库获取文件地址
    output_paths = []
    pdf_paths = get_pdf_file_path_from_db()
    
    if not pdf_paths:
        logger.info("没有需要解析的 PDF 文件")
        return output_paths

    logger.info(f"开始解析 {len(pdf_paths)} 个 PDF 文件")
    
    for pdf_path in pdf_paths:
        try:
            logger.info(f"正在解析文件: {pdf_path['source_document_name']}")
            output_path = parse_pdf(pdf_path['source_document_pdf_path'])
            if output_path:
                # 添加 doc_id 到输出路径信息中
                output_path['doc_id'] = pdf_path['doc_id']
                output_paths.append(output_path)
                logger.info(f"文件 {pdf_path['source_document_name']} 解析成功")
            else:
                logger.error(f"文件 {pdf_path['source_document_name']} 解析失败: 未返回输出路径")
        except Exception as e:
            logger.error(f"解析文件 {pdf_path.get('source_document_name', 'unknown')} 失败: {str(e)}")
            continue
            
    logger.info(f"PDF 文件解析完成: 成功 {len(output_paths)} 个, 失败 {len(pdf_paths) - len(output_paths)} 个")
    return output_paths


# 将解析后的文件路径信息保存至 Mysql 中
def parse_file_to_db():
    """
    将解析后的文件路径信息保存至 Mysql 中
    """
    output_paths = parse_file_from_db()
    
    if not output_paths:
        logger.info("没有需要更新的文件路径信息")
        return

    success_count = 0
    fail_count = 0
    
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = '''update file_info 
                set source_document_markdown_path = %s, 
                    source_document_json_path = %s, 
                    source_document_images_path = %s 
                where doc_id = %s'''
                
        for output_path in output_paths:
            try:
                mysql.update_data(sql, (
                    output_path['output_markdown_path'],
                    output_path['output_json_list_path'],
                    output_path['output_image_path'],
                    output_path['doc_id']
                ))
                success_count += 1
            except Exception as e:
                logger.error(f"更新文件 {output_path.get('doc_id', 'unknown')} 路径失败: {str(e)}")
                fail_count += 1
                
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if 'mysql' in locals():
            mysql.close()
            
    if success_count > 0 or fail_count > 0:
        logger.info(f"文件路径更新完成: 成功 {success_count} 条, 失败 {fail_count} 条")




if __name__ == "__main__":
    parse_file_to_db()
