# 检查环境变量
import os

from openai import OpenAI
from src.utils.common.logger import logger


# 检查环境变量
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")

# 初始化千问客户端
llm_client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",

)


def create_completion(prompt: str, model: str = "qwen-turbo-1101", temperature: float = 0.2,system_prompt: str = None):
    """模型调用
    
    Args:
        prompt: 提示词
        model: 模型
        temperature: 温度
        system_prompt: 系统提示词
        
    Returns:
        response: 响应
    """
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        completion = llm_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=False
        )
        
        return completion.choices[0].message.content
    
    except Exception as e:
        logger.error(f"模型调用失败: {str(e)}")
        raise e