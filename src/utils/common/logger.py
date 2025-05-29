"""日志配置模块

提供统一的日志记录功能，包括：
1. 日志格式配置
2. 日志级别设置
3. 日志输出位置设置
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from src.config.settings import Config

# 创建日志目录
os.makedirs(Config.PATHS['log_dir'], exist_ok=True)

# 配置日志格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 创建日志处理器
file_handler = RotatingFileHandler(
    os.path.join(Config.PATHS['log_dir'], 'app.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 创建日志记录器
logger = logging.getLogger('tk_rag')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
