"""
全局信号处理器模块

该模块提供统一的资源清理机制，确保在进程异常终止时能够正确清理所有资源。
主要功能：
1. 注册和管理各种清理函数
2. 处理系统信号（SIGTERM, SIGINT）
3. 在应用退出时自动执行清理
4. 提供资源清理的统一接口

使用场景：
- 进程被强制终止时清理缓存目录
- 关闭数据库连接池
- 卸载模型资源
- 清理临时文件
"""

import atexit
import shutil
import signal
import sys
from collections.abc import Callable
from pathlib import Path

from utils.log_utils import logger


class GlobalSignalHandler:
    """
    全局信号处理器类

    负责统一管理所有需要在进程退出时清理的资源。
    使用单例模式确保全局只有一个实例。
    """

    _instance = None

    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化信号管理器"""
        # 避免重复初始化
        if hasattr(self, "_cleanup_functions"):
            return

        # 存储清理函数的列表，每个元素为 (清理函数, 函数名称)
        self._cleanup_functions: list[tuple[Callable, str]] = []

        # 标记是否正在关闭，防止重复清理
        self._is_shutting_down = False

        logger.info("全局信号处理器初始化完成")

    def register_cleanup(self, cleanup_func: Callable, name: str = "unknown"):
        """
        注册清理函数

        Args:
            cleanup_func: 要注册的清理函数，应该是无参数的函数
            name: 清理函数的名称，用于日志记录
        """
        self._cleanup_functions.append((cleanup_func, name))
        logger.debug(f"注册清理函数 {name} ")

    def cleanup_all(self):
        """
        执行所有注册的清理函数

        按照注册的相反顺序执行，确保依赖关系正确。
        如果某个清理函数执行失败，不会影响其他清理函数的执行。
        """
        if self._is_shutting_down:
            logger.debug("清理过程已在进行中，跳过重复清理")
            return

        self._is_shutting_down = True
        logger.info("开始执行全局清理...")

        # 按照注册的相反顺序执行清理函数
        # 这样可以确保依赖关系正确（后注册的先清理）
        cleaned_count = 0
        for cleanup_func, name in reversed(self._cleanup_functions):
            try:
                logger.debug(f"开始执行清理: {name}")
                cleanup_func()
                cleaned_count += 1
                logger.info(f"清理完成: {name}")
            except Exception as e:
                logger.error(f"清理失败: {name}, error={str(e)}")
                # 继续执行其他清理函数，不因为一个失败而停止
        logger.info(f"全局清理完成, 共执行 {cleaned_count} 个清理函数")

    def signal_handler(self, signum, frame):
        """
        信号处理器

        当收到系统信号时调用此函数，执行清理后退出程序。

        Args:
            signum: 信号编号
            frame: 当前栈帧（通常不使用）
        """
        signal_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        logger.info(f"收到信号 {signal_name}({signum})，开始清理...")
        self.cleanup_all()

        logger.info("清理完成, 程序即将退出...")
        sys.exit(0)


# 全局实例
global_handler = GlobalSignalHandler()


def register_global_cleanup():
    """
    注册全局清理函数

    这是主要的初始化函数，需要在应用启动时调用。
    它会：
    1. 注册信号处理器
    2. 注册退出清理函数
    3. 注册各种资源的清理函数
    """
    logger.info("开始注册全局清理函数...")

    # 注册信号处理器
    # SIGTERM: 终止信号，通常由 kill 命令发送
    # SIGINT: 中断信号，通常由 Ctrl+C 发送
    signal.signal(signal.SIGINT, global_handler.signal_handler)
    signal.signal(signal.SIGTERM, global_handler.signal_handler)
    logger.info("信号处理器已注册")

    # 注册退出清理函数
    # atexit.register 会在程序正常退出时调用注册的函数
    atexit.register(global_handler.cleanup_all)

    # 注册各种资源的清理函数
    # 注意：注册顺序决定了清理顺序，依赖关系要正确
    global_handler.register_cleanup(cleanup_cache_directories, "缓存目录")
    global_handler.register_cleanup(cleanup_database_connections, "数据库连接")
    global_handler.register_cleanup(cleanup_models, "模型资源")
    global_handler.register_cleanup(cleanup_temp_files, "临时文件")

    logger.info("全局清理函数注册完成")


def cleanup_cache_directories():
    """
    清理缓存目录

    清理 page_cache 目录下的所有子目录。
    这些目录是文档处理过程中创建的临时缓存。
    """
    try:
        temp_root = Path("page_cache")
        if not temp_root.exists():
            logger.debug("缓存根目录不存在，跳过清理")
            return

        cleaned_count = 0
        for sub_dir in temp_root.iterdir():
            if sub_dir.is_dir():
                try:
                    shutil.rmtree(sub_dir)
                    cleaned_count += 1
                    logger.info(f"清理缓存目录: {sub_dir}")
                except Exception as e:
                    logger.error(f"清理缓存目录失败: {sub_dir}, error={str(e)}")

        # 如果根目录为空，删除根目录
        if temp_root.exists() and not list(temp_root.iterdir()):
            temp_root.rmdir()
            logger.info("清理缓存根目录")

        if cleaned_count > 0:
            logger.info(f"缓存目录清理完成，共清理 {cleaned_count} 个目录")

    except Exception as e:
        logger.error(f"清理缓存目录失败: {str(e)}")


def cleanup_database_connections():
    """
    清理数据库连接

    关闭所有数据库连接池，确保连接被正确释放。
    """
    try:
        # 导入数据库相关模块
        from databases.milvus.flat_collection import FlatCollectionManager
        from databases.mysql.base import MySQLConnectionPool

        # 关闭 MySQL 连接池
        MySQLConnectionPool().close()
        logger.info("MySQL 连接池已关闭")

        # 关闭 Milvus 连接
        FlatCollectionManager().close()
        logger.info("Milvus 连接已关闭")

        # 如果有其他数据库连接，也可以在这里添加

        logger.info("数据库连接清理完成")
    except Exception as e:
        logger.error(f"清理数据库连接失败: {str(e)}")


def cleanup_models():
    """
    清理模型资源

    卸载所有已加载的模型，释放 GPU 内存和系统资源。
    """
    try:
        # 导入模型管理器
        from utils.llm_utils import embedding_manager, llm_manager, rerank_manager

        # 卸载各个模型
        embedding_manager.unload_model()
        logger.info("Embedding 模型已卸载")

        rerank_manager.unload_model()
        logger.info("Rerank 模型已卸载")

        llm_manager.unload_model()
        logger.info("LLM 模型已卸载")

        logger.info("模型资源清理完成")
    except Exception as e:
        logger.error(f"清理模型资源失败: {str(e)}")


def cleanup_temp_files():
    """
    清理临时文件

    清理系统临时目录中与项目相关的临时文件。
    """
    try:
        import tempfile

        # 获取系统临时目录
        temp_dir = Path(tempfile.gettempdir())
        cleaned_count = 0

        # 查找并清理项目相关的临时文件
        for item in temp_dir.iterdir():
            # 检查文件名是否与项目相关
            if (
                item.name.startswith("tk_rag_")
                or "libreoffice" in item.name.lower()
                or "page_cache" in item.name.lower()
            ):
                try:
                    if item.is_file():
                        item.unlink()
                        cleaned_count += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        cleaned_count += 1
                    logger.debug(f"清理临时文件: {item}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {item}, error={str(e)}")

        if cleaned_count > 0:
            logger.info(f"临时文件清理完成，共清理 {cleaned_count} 个文件/目录")

    except Exception as e:
        logger.error(f"清理临时文件失败: {str(e)}")


# 便捷函数，用于手动触发清理（用于测试或调试）
def manual_cleanup():
    """
    手动触发清理

    用于测试或调试时手动执行清理操作。
    """
    logger.info("手动触发清理...")
    global_handler.cleanup_all()
    logger.info("手动清理完成")


# 获取清理状态
def get_cleanup_status():
    """
    获取清理状态信息

    Returns:
        dict: 包含清理函数列表和关闭状态的信息
    """
    return {
        "registered_functions": [name for _, name in global_handler._cleanup_functions],
        "is_shutting_down": global_handler._is_shutting_down,
        "function_count": len(global_handler._cleanup_functions),
    }
