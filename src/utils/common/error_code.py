"""错误代码管理模块"""
import json
import os
from typing import Dict, Tuple, Optional


class ErrorCode:
    """错误代码定义"""
    SUCCESS = 0

    # 通用错误 1000-1999
    PARAM_ERROR = 1001
    PARAM_EXCEED_LIMIT = 1002
    DUPLICATE_OPERATION = 1003
    INTERNAL_ERROR = 1004
    UNAUTHORIZED = 1005

    # 聊天相关 2000-2999
    QUESTION_TOO_LONG = 2001
    INVALID_SESSION = 2002
    MODEL_TIMEOUT = 2003
    KB_MATCH_FAILED = 2004
    CONTEXT_TOO_LONG = 2005

    # 文件相关 3000-3999
    FILE_NOT_FOUND = 3001
    UNSUPPORTED_FORMAT = 3002
    FILE_TOO_LARGE = 3003
    INVALID_FILENAME = 3004
    FILE_PARSE_ERROR = 3005
    FILE_EXISTS = 3006
    STORAGE_FULL = 3007
    FILE_TOO_SMALL = 3008

    # 数据库相关 4000-4999
    MYSQL_INSERT_FAIL = 4001
    MYSQL_UPDATE_FAIL = 4002
    MYSQL_DELETE_FAIL = 4003
    MYSQL_QUERY_FAIL = 4004
    MYSQL_CONNECTION_FAIL = 4005

    # 权限相关 5000-5999
    PERMISSION_DENIED = 5001
    PERMISSION_EXPIRED = 5002
    PERMISSION_INVALID = 5003

    # 系统相关 6000-6999
    SYSTEM_BUSY = 6001
    SYSTEM_MAINTENANCE = 6002
    SYSTEM_OVERLOAD = 6003


class ErrorInfo:
    """错误信息管理类"""
    _instance = None
    _error_codes = None
    _categories = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ErrorInfo, cls).__new__(cls)
            cls._instance._load_error_codes()
        return cls._instance

    def _load_error_codes(self):
        """加载错误代码配置"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'error_codes.json')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self._categories = config['categories']
                self._error_codes = config['codes']
        except Exception as e:
            raise Exception(f"加载错误代码配置失败: {str(e)}")

    def get_error_info(self, code: int) -> Tuple[str, str, Optional[str]]:
        """获取错误信息
        
        Args:
            code: 错误代码
            
        Returns:
            Tuple[str, str, Optional[str]]: (错误描述, 错误分类, 建议操作)
        """
        code_str = str(code)
        if code_str not in self._error_codes:
            return ("未知错误", self._categories["COMMON"], None)
            
        error_info = self._error_codes[code_str]
        return (
            error_info['description'],
            self._categories[error_info['category']],
            error_info['suggestion']
        )

    def get_category(self, code: int) -> str:
        """获取错误分类
        
        Args:
            code: 错误代码
            
        Returns:
            str: 错误分类
        """
        code_str = str(code)
        if code_str not in self._error_codes:
            return self._categories["COMMON"]
            
        error_info = self._error_codes[code_str]
        return self._categories[error_info['category']]

    def get_description(self, code: int) -> str:
        """获取错误描述
        
        Args:
            code: 错误代码
            
        Returns:
            str: 错误描述
        """
        code_str = str(code)
        if code_str not in self._error_codes:
            return "未知错误"
            
        return self._error_codes[code_str]['description']

    def get_suggestion(self, code: int) -> Optional[str]:
        """获取建议操作
        
        Args:
            code: 错误代码
            
        Returns:
            Optional[str]: 建议操作
        """
        code_str = str(code)
        if code_str not in self._error_codes:
            return None
            
        return self._error_codes[code_str]['suggestion'] 