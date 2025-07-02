"""文档删除请求数据模型"""
from typing import Union

from pydantic import BaseModel, Field


class DocumentDeleteRequest(BaseModel):
    """文档删除请求参数
    
    Attributes:
        doc_id: 文档ID
        is_soft_delete: 是否只删除记录,不删除本地文件
    """
    doc_id: str = Field(
        ...,
        description="文档ID",
        min_length=64,
        max_length=64
    )
    is_soft_delete: bool = Field(
        False,
        description="是否只删除记录,不删除本地文件"
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


class DocumentStatusRequest(BaseModel):
    """文档状态监测请求参数

    Attributes:
        doc_id: 要查询的文档 ID
    """
    doc_id: str = Field(
        ...,
        description="文档ID",
        min_length=64,
        max_length=64
    )


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
    # department_id: str = Field(
    #     None,
    #     description="部门ID，必须是一个有效的部门标识符",
    #     min_length=1,
    #     max_length=32,
    # )
    permission_ids: Union[str, list[str], list[None]] = Field(
        None,
        description="部门ID列表，单个 ID 接收字符串格式, 多个 ID 接收列表格式, 公开文档使用空字符串或空数组",
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
