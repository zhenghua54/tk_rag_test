"""系统信息检查"""
import os
import shutil

from src.api.response import ErrorCode
from src.utils.common.unit_convert import convert_bytes


class SystemValidator:
    @staticmethod
    def validate_storage_space(file_path: str):
        """检查存储空间是否足够"""
        file_size = os.path.getsize(file_path)
        # 获取项目根目录所在磁盘的可用空间
        total, used, free = shutil.disk_usage(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        if free <= file_size * 2:  # 预留2倍空间作为缓冲
            file_size = convert_bytes(file_size)
            free = convert_bytes(free - file_size)

            raise ValueError(ErrorCode.STORAGE_FULL,f"存储空间不足，文件大小：{file_size}, 系统剩余 {free}")
