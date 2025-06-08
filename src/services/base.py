"""服务接口基类

定义服务接口的基本结构，便于切换 mock/真实 实现
"""
import importlib
from abc import ABC
from config.settings import Config


class BaseService(ABC):
    """服务接口基类
    
    所有服务类都应该继承此类，并实现相应的抽象方法
    """

    @classmethod
    def get_instance(cls):
        """根据配置返回 mock 或真实服务实例"""
        if Config.USE_MOCK:
            mock_class_name = f"Mock{cls.__name__}"  # 例：MockDocumentService
            module_name = cls.__module__  # 获取子类定义的模块名
            try:
                module = importlib.import_module(module_name)
                mock_cls = getattr(module, mock_class_name, None)
                if mock_cls:
                    return mock_cls()
                else:
                    raise NotImplementedError(f"未定义 Mock 类: {mock_class_name} in {module_name}")
            except ImportError as e:
                raise ImportError(f"导入模块失败: {module_name}, 原因: {str(e)}")
        return cls()
