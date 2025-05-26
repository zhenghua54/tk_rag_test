"""文件数据库操作模块

提供文件信息相关的数据库操作，包括：
1. 获取文件信息
2. 更新文件信息
3. 插入文件信息
"""

from src.utils.database.mysql_connect import connect_mysql, check_table_exists
from src.utils.common.logger import logger


def get_non_pdf_files() -> list[dict]:
    """获取所有非 PDF 格式的文件信息

    Returns:
        non_pdf_file_paths (list[dict]): 非 PDF 文件地址列表，每个元素包含 doc_id, source_document_name, source_document_path
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = (
            'select doc_id, source_document_name, source_document_path from file_info '
            'where source_document_pdf_path is null'
        )
        non_pdf_file_paths = mysql.select_data(sql)
        return non_pdf_file_paths if non_pdf_file_paths is not None else []
    except Exception as e:
        logger.error(f"获取非 PDF 文件失败: {e}")
        return []
    finally:
        if 'mysql' in locals():
            mysql.close()


def get_pdf_files() -> list[dict]:
    """获取所有 PDF 格式的文件信息

    Returns:
        list[dict]: PDF 文件地址列表，包含 doc_id、source_document_name 和 source_document_pdf_path
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = '''select doc_id, source_document_name, source_document_pdf_path
                 from file_info
                 where source_document_pdf_path is not null'''
        pdf_paths = mysql.select_data(sql)
        return pdf_paths if pdf_paths is not None else []
    except Exception as e:
        logger.error(f"获取 PDF 文件失败: {e}")
        return []
    finally:
        if 'mysql' in locals():
            mysql.close()


def update_pdf_paths(pdf_file_paths: list[dict]) -> tuple[int, int]:
    """更新文件的 PDF 路径信息

    Args:
        pdf_file_paths (list[dict]): PDF 文件路径信息列表

    Returns:
        tuple[int, int]: (成功数量, 失败数量)
    """
    if not pdf_file_paths:
        logger.info("没有需要更新的文件")
        return 0, 0

    success_count = 0
    fail_count = 0

    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = (
            'update file_info set source_document_pdf_path = %s '
            'where doc_id = %s'
        )
        for pdf_file_path in pdf_file_paths:
            try:
                mysql.update_data(
                    sql,
                    (pdf_file_path['source_document_pdf_path'],
                     pdf_file_path['doc_id'])
                )
                success_count += 1
            except Exception as e:
                logger.error(
                    f"更新文件 {pdf_file_path['doc_id']} 失败: {str(e)}"
                )
                fail_count += 1
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if 'mysql' in locals():
            mysql.close()

    return success_count, fail_count


def update_parse_paths(output_paths: list[dict]) -> tuple[int, int]:
    """更新文件解析后的路径信息

    Args:
        output_paths (list[dict]): 解析后的文件路径信息列表

    Returns:
        tuple[int, int]: (成功数量, 失败数量)
    """
    if not output_paths:
        logger.info("没有需要更新的文件路径信息")
        return 0, 0

    success_count = 0
    fail_count = 0

    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = '''update file_info
                 set source_document_markdown_path = %s,
                     source_document_json_path     = %s,
                     source_document_images_path   = %s
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
                logger.error(
                    f"更新文件 {output_path.get('doc_id', 'unknown')} 路径失败: "
                    f"{str(e)}"
                )
                fail_count += 1
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if 'mysql' in locals():
            mysql.close()

    return success_count, fail_count


def insert_file_info(file_paths: list[dict], debug: bool = False) -> tuple[int, int]:
    """插入文件信息到数据库

    Args:
        file_paths (list[dict]): 文件信息列表
        debug (bool): 是否开启调试模式，开启后会打印插入的数据信息

    Returns:
        tuple[int, int]: (成功数量, 失败数量)
    """
    if not file_paths:
        logger.info("没有需要上传的文件")
        return 0, 0

    if debug:
        logger.info(f"准备插入 {len(file_paths)} 条数据:")
        for file_path in file_paths:
            logger.info(f"文件信息: {file_path}")

    success_count = 0
    fail_count = 0
    mysql = None

    try:
        mysql = connect_mysql()
        mysql.use_db()
        if not check_table_exists(mysql, 'file_info'):
            logger.error("数据库表 'file_info' 不存在, 退出流程")
            return 0, 0

        for file_path in file_paths:
            try:
                if mysql.insert_data(file_path, 'file_info'):
                    success_count += 1
                    if debug:
                        logger.info(f"成功插入文件: {file_path['source_document_name']}")
                        data = mysql.select_data(
                            sql='select * from file_info where doc_id = %s',
                            args=(file_path['doc_id'],)
                        )
                        logger.info(f"数据库中的记录: {data}")
            except Exception as e:
                fail_count += 1
                logger.error(
                    f"插入文件 {file_path.get('source_document_name', 'unknown')} 失败: {str(e)}"
                )
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if mysql:
            mysql.close()

    if debug:
        logger.info(f"插入结果统计:")
        logger.info(f"- 成功: {success_count} 条")
        logger.info(f"- 失败: {fail_count} 条")
        if fail_count > 0:
            logger.info("失败的文件:")
            for file_path in file_paths:
                try:
                    data = mysql.select_data(
                        sql='select * from file_info where doc_id = %s',
                        args=(file_path['doc_id'],)
                    )
                    if not data:
                        logger.info(f"- {file_path['source_document_name']}")
                except:
                    pass

    return success_count, fail_count

def search_file_info(doc_id: str) -> dict:
    """查询文件信息

    Args:
        doc_id (str): 文件 ID

    Returns:
        file_info(dict): 文件信息
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = 'select * from file_info where doc_id = %s'
        data = mysql.select_data(sql, (doc_id,))
        file_info = data[0] if data else None
        return file_info
    except Exception as e:
        logger.error(f"查询文件信息失败: {e}")
        return None