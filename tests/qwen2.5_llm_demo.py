import os
from openai import OpenAI
from dotenv import load_dotenv
from rich import print

# 加载环境
load_dotenv(verbose=True)


client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

completion = client.chat.completions.create(
    # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    model="qwen2.5-72b-instruct",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁？"},
    ],
    # Qwen3模型通过enable_thinking参数控制思考过程（开源版默认True，商业版默认False）
    # 使用Qwen3开源版模型时，若未启用流式输出，请将下行取消注释，否则会报错
    # extra_body={"enable_thinking": False},
)
print(completion.model_dump_json())
"""
{
    "id":"chatcmpl-3d50403c-ce6e-9166-a530-fcf681ba7160",
    "choices":[{
        "finish_reason":"stop",
        "index":0,
        "logprobs":null,
        "message":{
            "content":"我是Qwen，由阿里云开发的预训练语言模型。我被设计用来生成各种文本，如文章、故事、诗歌等，并能根据不同的场景和需求进行对话，提供信息或帮助解决问题。很高兴为你服务！",
            "refusal":null,
            "role":"assistant",
            "annotations":null,
            "audio":null,
            "function_call":null,
            "tool_calls":null
            }
        }],
    "created":1748676560,
    "model":"qwen2.5-72b-instruct",
    "object":"chat.completion",
    "service_tier":null,
    "system_fingerprint":null,
    "usage":{
        "completion_tokens":49,
        "prompt_tokens":22,
        "total_tokens":71,
        "completion_tokens_details":null,
        "prompt_tokens_details":null
        }
}
"""