# """日志配置模块
#
# 提供统一的日志记录功能，包括：
# 1. 日志格式配置
# 2. 日志级别设置
# 3. 日志输出位置设置
# 4. 结构化日志工具函数
# """
#
# import os
# import logging
# import time
# from logging.handlers import RotatingFileHandler
# from typing import Optional
# from config.global_config import GlobalConfig
#
# # 创建日志目录
# os.makedirs(GlobalConfig.PATHS['log_dir'], exist_ok=True)
#
# # 配置日志格式
# # LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d - %(funcName)s()] - %(message)s'
# # LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(threadName)s] [%(filename)s:%(lineno)d - %(funcName)s()] - %(message)s'
# formatter = logging.Formatter(LOG_FORMAT)
#
# # 普通日志处理器
# file_handler = RotatingFileHandler(
#     os.path.join(GlobalConfig.PATHS['log_dir'], 'app.log'),
#     maxBytes=10 * 1024 * 1024,  # 10MB
#     backupCount=5,
#     encoding='utf-8'
# )
# file_handler.setFormatter(formatter)
#
# console_handler = logging.StreamHandler()
# console_handler.setFormatter(formatter)
#
# # 普通日志记录器
# logger = logging.getLogger('tk_rag')
# logger.setLevel(logging.INFO)
# logger.addHandler(file_handler)
# logger.addHandler(console_handler)
#
# # --- 新增异常日志记录器 ---
# error_file_handler = RotatingFileHandler(
#     os.path.join(GlobalConfig.PATHS['log_dir'], 'error.log'),
#     maxBytes=10 * 1024 * 1024,
#     backupCount=5,
#     encoding='utf-8'
# )
# error_file_handler.setFormatter(formatter)
#
# error_logger = logging.getLogger('tk_rag_error')
# error_logger.setLevel(logging.ERROR)
# error_logger.addHandler(error_file_handler)
#
#
# def log_exception(msg: str, exc: Exception):
#     """
#     记录异常链到 error.log
#     :param msg: 错误描述
#     :param exc: 异常对象
#     """
#     error_logger.error(msg, exc_info=exc)
#
#
# # --- 结构化日志工具函数 ---
#
# def mask_sensitive_info(text: str, max_length: int = 200) -> str:
#     """脱敏处理敏感信息"""
#     if not text:
#         return ""
#     if len(text) > max_length:
#         return text[:max_length] + "..."
#     return text
#
#
# def format_log_params(**kwargs) -> str:
#     """格式化日志参数为 key=value 格式"""
#     return ", ".join([f"{k}={v}" for k, v in kwargs.items() if v is not None])
#
#
# def log_operation_start(operation: str, **context) -> float:
#     """记录操作开始"""
#     start_time = time.time()
#     params = format_log_params(operation=operation, **context)
#     logger.info(f"[{operation}] 开始, {params}")
#     return start_time
#
#
# def log_operation_success(operation: str, start_time: float, **context) -> None:
#     """记录操作成功"""
#     duration = int((time.time() - start_time) * 1000)  # 转换为毫秒
#     params = format_log_params(operation=operation, duration=f"{duration}ms", **context)
#     logger.info(f"[{operation}] 成功, {params}")
#
#
# def log_operation_error(operation: str, error_code: Optional[str] = None,
#                         error_msg: Optional[str] = None, **context) -> None:
#     """记录操作错误"""
#     context_params = format_log_params(**context)
#     error_params = format_log_params(error_code=error_code, error_msg=mask_sensitive_info(str(error_msg)))
#
#     all_params = ", ".join(filter(None, [context_params, error_params]))
#     logger.error(f"[{operation}失败] {all_params}")
#
#
# def log_business_info(category: str, **context) -> None:
#     """记录业务信息日志"""
#     params = format_log_params(**context)
#     logger.info(f"[{category}] {params}")
#
#
# def log_performance_metric(operation: str, duration_ms: int, **metrics) -> None:
#     """记录性能指标"""
#     all_metrics = format_log_params(operation=operation, duration=f"{duration_ms}ms", **metrics)
#     logger.info(f"[性能指标] {all_metrics}")
#
#
# def log_batch_progress(operation: str, processed: int, total: int, **context) -> None:
#     """记录批处理进度"""
#     progress = (processed / total * 100) if total > 0 else 0
#     params = format_log_params(
#         operation=operation,
#         processed=processed,
#         total=total,
#         progress=f"{progress:.1f}%",
#         **context
#     )
#     logger.info(f"[批处理进度] {params}")
#
#
# # 使用示例和文档
# """
# 使用示例：
#
# # 1. 操作流程日志
# start_time = log_operation_start("文档上传", doc_id="123", filename="test.pdf")
# try:
#     # 业务逻辑...
#     log_operation_success("文档上传", start_time, doc_id="123", size="1.2MB")
# except Exception as e:
#     log_operation_error("文档上传", error_code="UPLOAD_FAILED", error_msg=str(e), doc_id="123")
#
# # 2. 业务信息日志
# log_business_info("用户查询", query=mask_sensitive_info(query), user_id="user123")
#
# # 3. 性能监控日志
# log_performance_metric("向量检索", 150, result_count=10, memory_usage="256MB")
#
# # 4. 批处理进度日志
# log_batch_progress("文档分块", 50, 100, doc_id="123")
#
# # 5. 异常日志
# try:
#     # 业务逻辑...
#     pass
# except Exception as e:
#     log_exception("文档处理异常", e)
# """


"""日志配置模块

提供统一的日志记录功能，包括：
1. 日志格式配置
2. 日志级别设置
3. 日志输出位置设置
4. 结构化日志工具函数
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from config.global_config import GlobalConfig

# 确保日志目录存在
os.makedirs(GlobalConfig.PATHS['log_dir'], exist_ok=True)

# 日志格式定义
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(LOG_FORMAT)

# === 主日志 ===
main_logger = logging.getLogger("main")
main_logger.setLevel(logging.INFO)

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
