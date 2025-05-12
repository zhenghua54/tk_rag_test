import os
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model='hunyuan-turbos-latest',
    openai_api_key=os.getenv("HUNYUAN_API_KEY"),
    openai_api_base="https://api.hunyuan.cloud.tencent.com/v1",
    extra_body={
        "enable_enhancement": True,
    }
)

# 测试简单对话
response = llm.invoke("你好")
print(response)