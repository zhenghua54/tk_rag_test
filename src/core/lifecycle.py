from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from src.database.mysql.connection import MySQLConnectionPool
from src.utils.common.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用生命周期管理器
    
    Args:
        app: FastAPI 应用实例
        
    Yields:
        None
    """
    # 启动时执行
    logger.info("应用启动，开始初始化资源...")
    try:
        # 初始化数据库连接池
        MySQLConnectionPool()
        logger.info("数据库连接池初始化成功")
        
        # 其他初始化操作...
        
        yield  # 应用运行期间
        
    finally:
        # 关闭时执行
        logger.info("应用关闭，开始清理资源...")
        try:
            # 关闭数据库连接池
            MySQLConnectionPool().close()
            logger.info("数据库连接池已关闭")
            
            # 其他清理操作...
            
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")