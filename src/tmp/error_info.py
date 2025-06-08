"""错误信息构建(未启用)"""
from enum import Enum
from typing import Union

from src.api.error_codes import ErrorCode


def build_error_info(error_code: Union[int, Enum],
                     error_msg: str = None,
                     exception: Union[Exception, str, None] = None
                     ) -> dict:
    """构建错误信息字典

    Args:
        error_code (int,enum): 错误代码
        error_msg (str): 错误信息
        exception (Exception,str): 异常对象或异常信息

    Return:
        dict: 包含错误代码和错误信息的字典
    """
    code = error_code.value if isinstance(error_code, Enum) else error_code
    # 优先级: error_msg > exception > ErrorCode表 > 默认
    if error_msg:
        msg = error_msg
    elif exception:
        msg = str(exception)
    elif hasattr(ErrorCode, "get_message"):
        msg = ErrorCode.get_message(code)
    else:
        msg = "未登记错误代码"
    return {
        "error_code": code,
        "error_message": msg
    }
