"""定义系统日志服务"""

import logging
import os
import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")

from config import Config


def get_logger(config: Config):
    """配置全局日志"""
    LOG_FILE_PATH = os.path.join(config.PATHS["logs_dir"], "rag_project.log")

    logger = logging.getLogger("RAGProject")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:  # 避免重复添加 handler
        # 控制台 handle (INFO 级别)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        console_handler.setFormatter(console_formatter)

        # 文件 handler (DEBUG 级别)
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
                                           "%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)

        # 添加 handler 到 logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    # 启动提示
    logger.info("日志服务初始化成功!")
    return logger


logger = get_logger(Config)
