"""错误编码, 根据在线接口文档维护,如有修改,保持同步"""

from enum import Enum


class ErrorCode(Enum):
    # 系统成功响应
    SUCCESS = 0
    INTERNAL_ERROR = 1
    PARAM_ERROR = 2

    # 文件相关错误
    FILE_STATUS_CHECK_FAIL = 4019

    # 会话相关错误
    CHAT_EXCEPTION = 5005

    # 模型相关错误
    MODEL_TIMEOUT = 7000

    @staticmethod
    def get_message(error_code) -> str:
        """获取错误码对应的提示信息

        Args:
            :param error_code: 错误码
        Return:
            message (str): 错误提示信息
        """
        if isinstance(error_code, int):
            try:
                error_code = ErrorCode(error_code)
            except ValueError:
                return f"转换error_code失败, 请检查错误码是否正确,error_code={error_code}"

        message = ERROR_MESSAGES.get(error_code, "未知错误")
        return message


# 错误信息对应的描述
ERROR_MESSAGES = {
    ErrorCode.SUCCESS: "success",
    ErrorCode.INTERNAL_ERROR: "系统内部错误",
    ErrorCode.PARAM_ERROR: "参数错误, 请检查请求参数是否完整且格式正确",
    ErrorCode.FILE_STATUS_CHECK_FAIL: "文档状态检查失败",
    ErrorCode.CHAT_EXCEPTION: "聊天异常",
    ErrorCode.MODEL_TIMEOUT: "模型响应超时, 请稍后重试或降低问题复杂度",
}

if __name__ == "__main__":
    # 示例：在 API 响应中返回错误码和错误消息
    def handle_error(error_code):
        error_message = ErrorCode.get_message(error_code)
        return {"error_code": error_code, "error_message": error_message}

    # 错误处理示例
    response = handle_error(ErrorCode.MYSQL_INSERT_FAIL)
    print(response)  # 输出：{'error_code': 1001, 'error_message': '数据新增失败，请检查插入数据是否符合要求'}

    response_with_extra = handle_error(ErrorCode.UNSUPPORTED_FORMAT)
    print(
        response_with_extra
    )  # 输出：{'error_code': 4004, 'error_message': '不支持的文件格式，请使用支持的文件格式，jpg'}

    response_with_extra = handle_error(ErrorCode.UNSUPPORTED_FORMAT)
    print(
        response_with_extra
    )  # 输出：{'error_code': 4004, 'error_message': '不支持的文件格式，请使用支持的文件格式 $placeholder'}
