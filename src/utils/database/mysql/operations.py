"""数据库操作"""

from src.utils.common.logger import logger
from src.utils.database.mysql.connection import connect_mysql, check_table_exists

FILE_INFO_TABLE = 'file_info'

def select_file_info(doc_id: str) -> dict:
    """查询文件信息
    
    Args:
        doc_id (str): 文件 ID
        
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = f'select * from {table_name} where doc_id = %s'
        data = mysql.select_data(sql, (doc_id,))
        file_info = data[0] if data else None
        return file_info
    except Exception as e:
        logger.error(f"获取文件信息失败: {e}")
        return []
    finally:
        if 'mysql' in locals():
            mysql.close()
    

def select_non_pdf_files() -> list[dict]:
    """获取所有非 PDF 格式的文件信息

    Returns:
        non_pdf_file_paths (list[dict]): 非 PDF 文件的数据库记录
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = (
            f'select * from {table_name} '
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


def select_pdf_files() -> list[dict]:
    """获取所有 PDF 格式的文件信息

    Returns:
        list[dict]: PDF 文件的数据库记录
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        sql = f'select * from {table_name} where source_document_pdf_path is not null'
        pdf_paths = mysql.select_data(sql)
        return pdf_paths if pdf_paths is not None else []
    except Exception as e:
        logger.error(f"获取 PDF 文件失败: {e}")
        return []
    finally:
        if 'mysql' in locals():
            mysql.close()


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
        if not check_table_exists(mysql, table_name):
            logger.error(f"数据库表 '{FILE_INFO_TABLE}' 不存在, 退出流程")
            return 0, 0

        for file_path in file_paths:
            try:
                if mysql.insert_data(file_path, table_name):
                    success_count += 1
                    if debug:
                        logger.info(f"成功插入文件: {file_path['source_document_name']}")
                        data = mysql.select_data(
                            sql=f'select * from {table_name} where doc_id = %s',
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
                        sql=f'select * from {table_name} where doc_id = %s',
                        args=(file_path['doc_id'],)
                    )
                    if not data:
                        logger.info(f"- {file_path['source_document_name']}")
                except:
                    pass

    return success_count, fail_count


def update_file_info(doc_id: str, file_info: dict) -> None:
    """更新文件信息
    
    Args:
        table_name (str): 表名
        doc_id (str): 文件 ID
        file_info (dict): 文件信息
    """
    try:
        mysql = connect_mysql()
        mysql.use_db()
        # 构建更新语句
        set_clause = ', '.join([f"{key} = %s" for key in file_info.keys()])
        sql = f'update {FILE_INFO_TABLE} set {set_clause} where doc_id = %s'
        
        # 构建参数列表
        values = list(file_info.values())
        values.append(doc_id)
        
        # 执行更新
        mysql.update_data(sql, tuple(values))
    except Exception as e:
        logger.error(f"更新文件信息失败: {e}")
    

