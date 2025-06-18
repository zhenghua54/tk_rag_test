"""文档删除请求数据模型"""
from pydantic import BaseModel, Field


class DocumentDeleteRequest(BaseModel):
    """文档删除请求参数
    
    Attributes:
        doc_id: 文档ID
        is_soft_delete: 是否软删除
    """
    doc_id: str = Field(
        ...,
        description="文档ID",
        min_length=64,
        max_length=64
    )
    is_soft_delete: bool = Field(
        False,
        description="是否软删除"
    )

    # 自定义异常捕获逻辑
    # @field_validator('doc_id')
    # def doc_id_length(cls, value: str) -> str:
    #     """验证文档ID长度"""
    #     if len(value) != 64:
    #         raise APIException(
    #             error_code=ErrorCode.PARAM_ERROR,
    #             message="文档ID长度必须为64个字符"
    #         )
    #     return value
    #
    # @field_validator('is_soft_delete')
    # def is_soft_delete_bool(cls, value: bool) -> bool:
    #     """验证是否软删除为布尔值"""
    #     if not isinstance(value, bool):
    #         raise APIException(
    #             error_code=ErrorCode.PARAM_ERROR,
    #             message="is_soft_delete必须为布尔值"
    #         )
    #     return value
    #
    # @classmethod
    # def validate_request(cls, data: dict) -> 'DocumentDeleteRequest':
    #     """验证请求数据"""
    #     try:
    #         return cls(**data)
    #     except ValidationError as e:
    #         raise APIException(
    #             error_code=ErrorCode.PARAM_ERROR,
    #             message=str(e)
    #         ) from e
