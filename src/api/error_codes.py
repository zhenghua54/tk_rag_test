"""错误编码, 根据在线接口文档维护,如有修改,保持同步"""
from enum import Enum

from config.settings import Config


class ErrorCode(Enum):
    # 系统成功响应
    SUCCESS = 0
    INTERNAL_ERROR = 1
    PARAM_ERROR = 2
    DUPLICATE_OPERATION = 3
    CALLBACK_ERROR = 4

    # 数据库相关错误
    MYSQL_CONNECTION_FAIL = 1000
    MYSQL_INSERT_FAIL = 1001
    MYSQL_UPDATE_FAIL = 1002
    MYSQL_DELETE_FAIL = 1003
    MYSQL_QUERY_FAIL = 1004

    # 权限相关错误
    UNAUTHORIZED = 2000
    PERMISSION_INVALID = 2001

    # 系统相关错误
    STORAGE_FULL = 3000
    SYSTEM_BUSY = 3001
    SYSTEM_MAINTENANCE = 3002
    INTERNAL_ERROR_2 = 3003
    ENVIRONMENT_DEFICIT = 3004

    # 文件相关错误
    FILE_NOT_FOUND = 4000
    UNSUPPORTED_FORMAT = 4001
    FILE_TOO_LARGE = 4002
    FILE_EMPTY = 4003
    FILENAME_TOOLONG = 4004
    INVALID_FILENAME = 4005
    PDF_PARSE_ERROR = 4006
    FILE_EXISTS_PROCESSED = 4007
    FILEPATH_TOOLONG = 4008
    FILE_EXCEPTION = 4009
    FILE_VALIDATION_ERROR = 4010
    FILE_HARD_DELETE_ERROR = 4011
    FILE_SOFT_DELETE_ERROR = 4012
    FILE_READ_FAILED = 4013
    HTTP_FILE_NOT_FOUND = 4014
    FILE_SAVE_FAILED = 4015
    DOC_PROCESS_ERROR = 4016
    FILE_EXISTS_PENDING = 4017
    FILE_HASH_FAIL= 4018

    # 会话相关错误
    QUESTION_TOO_LONG = 5000
    INVALID_SESSION = 5001
    KB_MATCH_FAILED = 5002
    CONTEXT_TOO_LONG = 5003
    MODEL_TIMEOUT = 5004
    CHAT_EXCEPTION = 5005

    # 服务相关错误
    CONVERT_FAILED = 6000


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
    ErrorCode.DUPLICATE_OPERATION: "重复操作, 请勿重复提交请求",
    ErrorCode.CALLBACK_ERROR: "回调通知失败",


    ErrorCode.MYSQL_CONNECTION_FAIL: "数据库连接失败，请检查数据库连接配置",
    ErrorCode.MYSQL_INSERT_FAIL: "数据新增失败，请检查插入数据是否符合要求",
    ErrorCode.MYSQL_UPDATE_FAIL: "数据更新失败，请检查更新数据是否符合要求",
    ErrorCode.MYSQL_DELETE_FAIL: "数据删除失败",
    ErrorCode.MYSQL_QUERY_FAIL: "数据查询失败",


    ErrorCode.UNAUTHORIZED: "未授权操作, 请重新登录",
    ErrorCode.PERMISSION_INVALID: "权限无效, 请重新登录",

    ErrorCode.STORAGE_FULL: "存储空间不足, 为确保后续文件处理正常进行， 请检查RAG服务器剩余存储空间",
    ErrorCode.SYSTEM_BUSY: "系统繁忙，请稍后重试",
    ErrorCode.SYSTEM_MAINTENANCE: "系统维护中，请等待维护完成",
    ErrorCode.INTERNAL_ERROR_2: "系统内部错误，请联系系统管理员",
    ErrorCode.ENVIRONMENT_DEFICIT: "环境缺失",

    ErrorCode.FILE_NOT_FOUND: "文件不存在, 请检查文件路径是否正确",
    ErrorCode.UNSUPPORTED_FORMAT: f"文件格式不支持, 仅支持: {','.join(Config.SUPPORTED_FILE_TYPES.get('all')).replace('.', '')}",
    ErrorCode.FILE_TOO_LARGE: "文件过大, 最大支持 50MB 文件",
    ErrorCode.FILE_EMPTY: "文件内容为空, 无法读取文件内容",
    ErrorCode.FILENAME_TOOLONG: "文件名称超长, 长度应不超过 200字",
    ErrorCode.INVALID_FILENAME: f"文件名无效, 仅支持: {Config.UNSUPPORTED_FILENAME_CHARS}",
    ErrorCode.PDF_PARSE_ERROR: "PDF解析失败",
    ErrorCode.FILE_EXISTS_PROCESSED: "文件已存在, 请检查是否重复上传",
    ErrorCode.FILEPATH_TOOLONG: "文件路径超长, 长度应不超过 1000 字",
    ErrorCode.FILE_EXCEPTION: "",  # 不同异常单独返回
    ErrorCode.FILE_VALIDATION_ERROR: "文件验证失败",
    ErrorCode.FILE_HARD_DELETE_ERROR: "文件软删除失败",
    ErrorCode.FILE_SOFT_DELETE_ERROR: "文件物理删除失败",
    ErrorCode.FILE_READ_FAILED: "文件读取失败, 请检查文件是否存在或格式是否正确",
    ErrorCode.HTTP_FILE_NOT_FOUND: "HTTP文件未找到, 请检查文件URL是否正确",
    ErrorCode.FILE_SAVE_FAILED: "文件保存失败",
    ErrorCode.DOC_PROCESS_ERROR: "文档处理失败",
    ErrorCode.FILE_EXISTS_PENDING: "文件已上传，等待后续处理",
    ErrorCode.FILE_HASH_FAIL: "哈希值计算失败",

    ErrorCode.QUESTION_TOO_LONG: "问题超长, 长度应不超过 2000 字",
    ErrorCode.INVALID_SESSION: "会话ID无效, 检查session_id是否正确或重新开始会话",
    ErrorCode.KB_MATCH_FAILED: "未检索到数据, 请尝试调整问题描述或确认是否启用了权限管理",
    ErrorCode.CONTEXT_TOO_LONG: "上下文长度超限, 建议开启新的会话",
    ErrorCode.MODEL_TIMEOUT: "模型响应超时, 请稍后重试或降低问题复杂度",
    ErrorCode.CHAT_EXCEPTION:"聊天异常",

    ErrorCode.CONVERT_FAILED: "转换PDF失败",
}

if __name__ == '__main__':
    # 示例：在 API 响应中返回错误码和错误消息
    def handle_error(error_code):
        error_message = ErrorCode.get_message(error_code)
        return {
            "error_code": error_code,
            "error_message": error_message
        }


    # 错误处理示例
    response = handle_error(ErrorCode.MYSQL_INSERT_FAIL)
    print(response)  # 输出：{'error_code': 1001, 'error_message': '数据新增失败，请检查插入数据是否符合要求'}

    response_with_extra = handle_error(ErrorCode.UNSUPPORTED_FORMAT)
    print(response_with_extra)  # 输出：{'error_code': 4004, 'error_message': '不支持的文件格式，请使用支持的文件格式，jpg'}

    response_with_extra = handle_error(ErrorCode.UNSUPPORTED_FORMAT)
    print(response_with_extra)  # 输出：{'error_code': 4004, 'error_message': '不支持的文件格式，请使用支持的文件格式 $placeholder'}
