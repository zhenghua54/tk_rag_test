"""日志配置模块

提供统一的日志记录功能，包括：
1. 日志格式配置
2. 日志级别设置
3. 日志输出位置设置
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from config.settings import Config

# 创建日志目录
os.makedirs(Config.PATHS['log_dir'], exist_ok=True)

# 配置日志格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 普通日志处理器
file_handler = RotatingFileHandler(
    os.path.join(Config.PATHS['log_dir'], 'app.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 普通日志记录器
logger = logging.getLogger('tk_rag')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# --- 新增异常日志记录器 ---
error_file_handler = RotatingFileHandler(
    os.path.join(Config.PATHS['log_dir'], 'error.log'),
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
error_file_handler.setFormatter(formatter)

error_logger = logging.getLogger('tk_rag_error')
error_logger.setLevel(logging.ERROR)
error_logger.addHandler(error_file_handler)

def log_exception(msg: str, exc: Exception):
    """
    记录异常链到 error.log
    :param msg: 错误描述
    :param exc: 异常对象
    """
    error_logger.error(msg, exc_info=exc)