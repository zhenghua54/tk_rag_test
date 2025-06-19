"""需要对所有数据库统一操作的代码工具"""
from databases.mysql.operations import FileInfoOperation, PermissionOperation, ChunkOperation, check_duplicate_doc
from databases.milvus.operations import VectorOperation
from databases.elasticsearch.operations import ElasticsearchOperation

from utils.log_utils import logger
from config.global_config import GlobalConfig


async def delete_all_database_data(doc_id: str, is_soft_delete: bool) -> None:
    """删除所有数据库中的相关数据

    Args:
        doc_id: 要删除的文档ID
        is_soft_delete: 是否软删除
    """
    try:
        logger.info(f"开始删除数据库记录, doc_id={doc_id}")
        # 删除 MySQL 数据库记录
        try:
            logger.info(f"MySQL 数据删除")
            with FileInfoOperation() as file_op, \
                    PermissionOperation() as permission_op, \
                    ChunkOperation() as chunk_op:
                # 删除文件信息表
                if file_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete):
                    logger.info(f"表 {GlobalConfig.MYSQL_CONFIG['file_info_table']} 数据删除成功")
                else:
                    logger.warning(f"表 {GlobalConfig.MYSQL_CONFIG['file_info_table']} 数据不存在")

                # 删除权限信息表
                if permission_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete):
                    logger.info(f"表 {GlobalConfig.MYSQL_CONFIG['permission_info_table']} 数据删除成功")
                else:
                    logger.warning(f"表 {GlobalConfig.MYSQL_CONFIG['permission_info_table']} 数据不存在")

                # 删除分块信息表
                if chunk_op.delete_by_doc_id(doc_id, is_soft_deleted=is_soft_delete):
                    logger.info(f"表 {GlobalConfig.MYSQL_CONFIG['segment_info_table']} 数据删除成功")
                else:
                    logger.warning(f"表 {GlobalConfig.MYSQL_CONFIG['segment_info_table']} 数据不存在")

                operation = "软删除文件" if is_soft_delete else "物理删除文件"
                logger.info(f"{operation}成功")
        except Exception as e:
            logger.error(f"MySQL 数据删除失败, 错误原因: {str(e)}")
            # MySQL删除失败不影响其他数据库的删除操作

        # 删除 Milvus 数据库记录
        try:
            logger.info(f"Milvus 数据删除")
            vector_op = VectorOperation()
            if vector_op.delete_by_doc_id(doc_id):
                logger.info(f"Milvus 数据删除成功")
            else:
                logger.warning(f"Milvus 数据不存在")
        except Exception as e:
            logger.error(f"Milvus 数据删除失败, 错误原因: {str(e)}")
            # 不中断主流程

        # 删除ES中的数据
        try:
            logger.info(f"Elasticsearch 数据删除")
            es_op = ElasticsearchOperation()
            if es_op.delete_by_doc_id(doc_id):
                logger.info(f"Elasticsearch 数据删除成功")
            else:
                logger.warning(f"Elasticsearch 数据不存在")
        except Exception as e:
            logger.error(f"Elasticsearch 数据删除: {str(e)}, doc_id: {doc_id}")
            # 不中断主流程

    except Exception as e:
        logger.error(f"数据库记录删除失败, 错误原因: {str(e)}, doc_id: {doc_id}")
        # 不中断主流程
