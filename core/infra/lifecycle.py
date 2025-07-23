import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.infra.singal_handler import register_global_cleanup
from databases.mysql.base import MySQLConnectionPool
from utils.log_utils import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用生命周期管理器"""
    # 启动时执行
    logger.info("应用启动，开始初始化资源...")
    try:
        # 注册全局信号处理器
        register_global_cleanup()
        logger.info("全局信号处理器已注册")

        # 初始化数据库连接池
        MySQLConnectionPool()
        logger.info("数据库连接池初始化成功")

        # 启动模型状态检查任务
        task = asyncio.create_task(periodic_check_models())
        logger.info("模型状态检查任务已启动")

        # 其他初始化操作...

        yield  # 应用运行期间

    finally:
        # 关闭时执行
        logger.info("应用关闭，开始清理资源...")
        try:
            # # 关闭数据库连接池
            # MySQLConnectionPool().close()
            # logger.info("数据库连接池已关闭")

            # 取消模型检查任务
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("模型检查任务已取消")

            # 下列清理工作由全局信号处理器处理
            # # 卸载所有模型
            # from utils.llm_utils import embedding_manager, rerank_manager, llm_manager
            # embedding_manager.unload_model()
            # rerank_manager.unload_model()
            # llm_manager.unload_model()
            # logger.info("所有模型已卸载")
            #
            # # 其他清理操作...
            logger.info("应用关闭完成")

        except Exception as e:
            logger.error(f"应用关闭时发生错误: {str(e)}")


async def periodic_check_models():
    """定期检查模型状态"""
    while True:
        try:
            from utils.llm_utils import check_models_status

            check_models_status()
        except Exception as e:
            logger.error(f"检查模型状态失败: {str(e)}")
        await asyncio.sleep(300)  # 每5分钟检查一次
