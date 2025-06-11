from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """聊天请求模型

    Attributes:
        query: 用户问题
        department_id: 部门ID
        session_id: 会话ID(可选)
    """
    query: str = Field(
        ...,    # 必填
        description="问题内容",
        min_length=1,
        max_length=2000,
    )
    department_id: str = Field(
        ...,
        description="用户所属部门 ID",
        min_length=1,
        max_length=32,
    )
    session_id: Optional[str] = Field(
        None,
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
