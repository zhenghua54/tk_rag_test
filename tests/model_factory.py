import os
from typing import Optional, Literal
from openai import OpenAI

class ModelFactory:
    """模型工厂类，用于创建和管理不同类型的NLP模型"""
    
    def __init__(self):
        # 支持的模型类型
        self.supported_models = {
            "hunyuan": {
                "api_key_env": "HUNYUAN_API_KEY",
                "base_url": "https://api.hunyuan.cloud.tencent.com/v1"
            },
            "openai": {
                "api_key_env": "OPENAI_API_KEY",
                "base_url": "https://api.openai.com/v1"
            },
            "local": {
                "api_key_env": None,
                "base_url": "http://localhost:8000/v1"  # 假设本地模型服务运行在8000端口
            }
        }
    
    def get_model(self, model_type: Literal["hunyuan", "openai", "local"]) -> OpenAI:
        """
        获取指定类型的模型客户端
        
        Args:
            model_type: 模型类型，支持 "hunyuan"、"openai" 和 "local"
            
        Returns:
            OpenAI: 配置好的OpenAI客户端实例
            
        Raises:
            ValueError: 当模型类型不支持或API密钥未设置时
        """
        if model_type not in self.supported_models:
            raise ValueError(f"不支持的模型类型: {model_type}")
            
        model_config = self.supported_models[model_type]
        
        # 对于本地模型，不需要API密钥
        if model_type == "local":
            return OpenAI(base_url=model_config["base_url"])
            
        # 获取API密钥
        api_key = os.getenv(model_config["api_key_env"])
        if not api_key:
            raise ValueError(f"请设置 {model_config['api_key_env']} 环境变量")
            
        return OpenAI(
            api_key=api_key,
            base_url=model_config["base_url"]
        ) 
    
if __name__ == "__main__":
    # 创建工厂实例
    factory = ModelFactory()

    # 获取混元模型
    hunyuan_client = factory.get_model("hunyuan")

    # 获取OpenAI模型
    openai_client = factory.get_model("openai")

    # 获取本地模型
    local_client = factory.get_model("local")