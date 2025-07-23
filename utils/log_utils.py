"""日志配置模块

提供统一的日志记录功能，包括：
1. 日志格式配置
2. 日志级别设置
3. 日志输出位置设置
4. 结构化日志工具函数
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from config.global_config import GlobalConfig

# 确保日志目录存在
os.makedirs(GlobalConfig.PATHS['log_dir'], exist_ok=True)

# 从环境变量获取日志级别，默认为 INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

# 日志格式定义
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(LOG_FORMAT)

# === 主日志 ===
main_logger = logging.getLogger("main")
main_logger.setLevel(log_level)

# 文件日志, 单份日志最大10M, 最多保留最新的5份日志
file_handler = RotatingFileHandler(
    os.path.join(GlobalConfig.PATHS['log_dir'], 'app.log'),
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
main_logger.addHandler(file_handler)

# 控制台日志
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
main_logger.addHandler(console_handler)

# === 异常日志记录器 ===
error_logger = logging.getLogger("error")
error_logger.setLevel(logging.ERROR)

error_file_handler = RotatingFileHandler(
    filename=os.path.join(GlobalConfig.PATHS['log_dir'], 'error.log'),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8'
)
error_file_handler.setFormatter(formatter)
error_logger.addHandler(error_file_handler)


# === 封装异常日志记录函数 ===
def log_exception(msg: str, exc: Exception):
    """记录异常堆栈到 error.log

    Args:
        msg: 异常说明
        exc: 异常对象
    """
    error_logger.error(msg, exc_info=exc)


# 统一导出日志封装
logger = main_logger
