"""服务接口基类

定义服务接口的基本结构，便于切换 mock/真实 实现
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from config.settings import Config

class BaseService(ABC):
    """服务接口基类
    
    所有服务类都应该继承此类，并实现相应的抽象方法
    """
    
    @classmethod
    def get_instance(cls):
        """获取服务实例
        
        根据配置返回 mock 或真实服务实例
        
        Returns:
            BaseService: 服务实例
        """
        # 导入放在这里避免循环引用
        from src.server.chat import MockChatService
        
        if Config.USE_MOCK:
            if cls.__name__ == "ChatService":
                return MockChatService()
        return cls() 