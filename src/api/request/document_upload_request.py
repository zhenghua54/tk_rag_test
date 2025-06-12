"""文档上传请求数据模型"""
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.api.response import APIException
from src.api.error_codes import ErrorCode


class DocumentUploadRequest(BaseModel):
    """文档上传请求参数

    Attributes:
        document_http_url: 文档的 http 访问路径
        permission_ids: 部门ID
    """
    document_http_url: str = Field(
        ...,
        description="文档的存储路径，必须是一个可访问的 HTTP 路径",
        min_length=1,
        max_length=1000
    )
    permission_ids: str = Field(
        ...,
        description="部门ID，必须是一个有效的部门标识符",
        min_length=1,
        max_length=32,
    )

    # 自定义异常捕获逻辑
    # @field_validator('document_path')
    # def document_path_length(cls, value: str) -> str:
    #     """验证文档路径长度"""
    #     if len(value) > 1000:
    #         raise APIException(
    #             error_code=ErrorCode.PARAM_ERROR,
    #             message="document_path长度不能超过1000个字符"
    #         )
    #     return value
    #
    # @field_validator('permission_ids')
    # def department_id_length(cls, value: str) -> str:
    #     """验证部门ID长度"""
    #     if len(value) != 32:
    #         raise APIException(
    #             error_code=ErrorCode.PARAM_ERROR,
    #             message="部门ID必须是32个字符的字符串"
    #         )
    #     return value
    #
    # @classmethod
    # def validate_request(cls, data: dict) -> 'DocumentUploadRequest':
    #     """验证请求数据"""
    #     try:
    #         return cls(**data)
    #     except ValidationError as e:
    #         raise APIException(
    #             error_code=ErrorCode.PARAM_ERROR,
    #             message=str(e)
    #         ) from e