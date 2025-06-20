"""需要对所有数据库统一操作的代码工具"""
from typing import Dict, Any, Union, List

from databases.mysql.operations import FileInfoOperation, PermissionOperation, ChunkOperation, PageOperation
from databases.milvus.operations import VectorOperation
from databases.elasticsearch.operations import ElasticsearchOperation

from utils.log_utils import logger
from config.global_config import GlobalConfig
from utils.validators import validate_empty_param, validate_param_type

# 表明与操作类的映射
TABLE_OPERATION_MAPPING = {
    GlobalConfig.MYSQL_CONFIG["file_info_table"]: FileInfoOperation,
    GlobalConfig.MYSQL_CONFIG["segment_info_table"]: ChunkOperation,
    GlobalConfig.MYSQL_CONFIG["permission_info_table"]: PermissionOperation,
    GlobalConfig.MYSQL_CONFIG["doc_page_info_table"]: PageOperation,
}


def select_record_by_doc_id(table_name: str, doc_id: str) -> Dict[str, Any]:
    """根据 doc_id 查询数据库信息

    Args:
        table_name: 要查询的表名
        doc_id: 文档Id

    Returns:
        dict: 返回查询到的记录信息,未查到时为 None
    """

    if table_name not in TABLE_OPERATION_MAPPING:
        raise ValueError(f"未知表名: {table_name}")

    try:
        operation_cls = TABLE_OPERATION_MAPPING[table_name]
        with operation_cls() as op:
            return op.select_by_id(doc_id)
    except Exception as e:
        raise ValueError(f"记录查询失败, 失败原因: {str(e)}") from e


def delete_all_database_data(doc_id: str) -> None:
    """删除所有数据库中的相关数据

    Args:
        doc_id: 要删除的文档ID
    """
    try:
        logger.info(f"开始删除数据库记录, doc_id={doc_id}")
        # 删除 MySQL 数据库记录
        try:
            logger.info(f"MySQL 数据删除")
            with FileInfoOperation() as file_op, \
                    PermissionOperation() as permission_op, \
                    ChunkOperation() as chunk_op, \
                    PageOperation() as page_op:
                # 删除文件信息表
                logger.info(f"删除表 {GlobalConfig.MYSQL_CONFIG['file_info_table']} 记录...")
                file_op_nums = file_op.delete_by_doc_id(doc_id)
                logger.info(f"成功删除 {file_op_nums} 条")

                # 删除权限信息表
                logger.info(f"删除表 {GlobalConfig.MYSQL_CONFIG['permission_info_table']} 记录...")
                permission_op_nums = permission_op.delete_by_doc_id(doc_id)
                logger.info(f"成功删除 {permission_op_nums} 条")

                # 删除分块信息表
                logger.info(f"删除表 {GlobalConfig.MYSQL_CONFIG['segment_info_table']} 记录...")
                chunk_op_nums = chunk_op.delete_by_doc_id(doc_id)
                logger.info(f"成功删除 {chunk_op_nums} 条")

                # 删除分页信息表
                logger.info(f"删除表 {GlobalConfig.MYSQL_CONFIG['doc_page_info_table']} 记录...")
                page_op_nums = page_op.delete_by_doc_id(doc_id)
                logger.info(f"成功删除 {page_op_nums} 条")

                logger.info(f"MySQL 数据删除成功")
        except Exception as e:
            logger.error(f"MySQL 数据删除失败, 错误原因: {str(e)}")
            # MySQL删除失败不影响其他数据库的删除操作

        # 删除 Milvus 数据库记录
        try:
            logger.info(f"Milvus 数据删除, 集合: {GlobalConfig.MILVUS_CONFIG['collection_name']}")
            vector_op = VectorOperation()
            vector_op.delete_by_doc_id(doc_id)
        except Exception as e:
            logger.error(f"Milvus 数据删除失败, 错误原因: {str(e)}")
            # 不中断主流程

        # 删除ES中的数据
        try:
            logger.info(f"Elasticsearch 数据删除, 索引: {GlobalConfig.ES_CONFIG['index_name']}")
            es_op = ElasticsearchOperation()
            es_op.delete_by_doc_id(doc_id)
        except Exception as e:
            logger.error(f"Elasticsearch 数据删除: {str(e)}, doc_id: {doc_id}")
            # 不中断主流程

    except Exception as e:
        logger.error(f"数据库记录删除失败, 错误原因: {str(e)}, doc_id: {doc_id}")
        # 不中断主流程


def update_record_by_doc_id(table_name: str, doc_id: str, kwargs: Dict[str, Any]) -> bool:
    """通用表记录更新方法，根据表名和文档ID更新记录。

    Args:
        table_name (str): 要操作的数据库表名
        doc_id (str): 文档ID
        kwargs (Dict[str, Any]): 更新字段和值

    Returns:
        bool: 是否更新成功
    """

    if table_name not in TABLE_OPERATION_MAPPING:
        raise ValueError(f"未知表名: {table_name}")

    # 清洗输入
    if not table_name or not doc_id or not kwargs:
        raise ValueError("table_name, doc_id 和 args 均不能为空")

    # 清除 None 值可能导致的问题
    kwargs: Dict = {k: v for k, v in kwargs.items() if v is not None}

    try:
        operation_cls = TABLE_OPERATION_MAPPING[table_name]
        with operation_cls() as op:
            return op.update_by_doc_id(doc_id, kwargs)
    except Exception as e:
        raise e


def insert_record(table_name: str, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> int:
    """插入数据

    Args:
        table_name (str): 要插入数据的表
        data (Dict[str, Any]): 要插入的数据
    """
    if table_name not in TABLE_OPERATION_MAPPING:
        raise ValueError(f"未知表名: {table_name}")

    validate_empty_param(data, "插入到 mysql 的数据")

    try:
        operation_cls = TABLE_OPERATION_MAPPING[table_name]
        with operation_cls() as op:
            return op.insert(data=data)
    except Exception as e:
        logger.error(f"MySQL 数据插入失败, 失败原因: {str(e)}")
        raise ValueError(f"MySQL 数据插入失败, 失败原因: {str(e)}") from e
