from typing import Union
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求模型

    Attributes:
        query: 用户问题
        permission_ids: 权限ID，JSON格式字符串，可选
        session_id: 会话ID(可选)
    """
    query: str = Field(
        ...,  # 必填
        description="问题内容",
        min_length=1,
        max_length=2000,
    )
    permission_ids: Union[str, list[str]] = Field(
        None,
        description="权限ID列表，多个ID用逗号分隔",
    )
    session_id: str = Field(
        ...,
        description="会话 ID，可保持上下文",
    )
    timeout: int = Field(
        30,
        description="超时等待时间",
    )

    # @field_validator("query")
    # def validate_query(cls, v):
    #     if len(v.strip()) == 0:
    #         raise ValueError("问题不能为空")
    #     return v.strip()
