"""LLM 响应缓存工具"""
import os
import json
import hashlib
from typing import Any, Optional
from pathlib import Path
import time

from src.utils.common.logger import logger
from config.settings import Config


class LLMCache:
    """LLM 响应缓存管理器
    
    用于缓存 LLM 的响应结果，减少 API 调用次数。
    缓存文件存储在项目根目录的 tmp 文件夹下。
    """

    def __init__(self, cache_dir: str = Config.PATHS['tmp_dir']) -> None:
        """初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录名，默认为 tmp
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _generate_cache_key(self, prompt: str) -> str:
        """生成缓存键
        
        Args:
            prompt: 提示词文本
            
        Returns:
            str: 缓存键（MD5 哈希值）
        """
        return hashlib.md5(prompt.encode()).hexdigest()

    def get(self, prompt: str) -> Optional[Any]:
        """获取缓存内容
        
        Args:
            prompt: 提示词文本
            
        Returns:
            Optional[Any]: 缓存的内容，如果不存在则返回 None
        """
        cache_key = self._generate_cache_key(prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # 检查缓存是否过期（72小时）
            if time.time() - cache_data['timestamp'] > 72 * 3600:
                self.delete(prompt)
                return None

            return cache_data['content']

        except Exception as e:
            logger.error(f"读取缓存失败: {str(e)}")
            return None

    def set(self, prompt: str, content: Any) -> None:
        """设置缓存内容
        
        Args:
            prompt: 提示词文本
            content: 要缓存的内容
        """
        cache_key = self._generate_cache_key(prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cache_data = {
                'timestamp': time.time(),
                'content': content
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"写入缓存失败: {str(e)}")

    def delete(self, prompt: str) -> None:
        """删除缓存内容
        
        Args:
            prompt: 提示词文本
        """
        cache_key = self._generate_cache_key(prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.error(f"删除缓存失败: {str(e)}")

    def clear(self) -> None:
        """清空所有缓存"""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
        except Exception as e:
            logger.error(f"清空缓存失败: {str(e)}")


# 创建全局缓存实例
llm_cache = LLMCache()
