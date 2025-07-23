"""文档删除请求数据模型"""

from pydantic import BaseModel, Field


class DocumentStatusRequest(BaseModel):
    """文档状态监测请求参数

    Attributes:
        doc_id: 要查询的文档 ID
    """

    doc_id: str = Field(..., description="文档ID", min_length=64, max_length=64)


class DocumentDeleteRequest(BaseModel):
    """文档删除请求参数

    Attributes:
        doc_id: 文档ID
        is_soft_delete: 是否只删除记录,不删除本地文件
    """

    doc_id: str = Field(..., description="文档ID", min_length=64, max_length=64)
    is_soft_delete: bool = Field(False, description="是否只删除记录,不删除本地文件")

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


class DocumentUploadRequest(BaseModel):
    """文档上传请求参数

    Attributes:
        document_http_url: 文档的 http 访问路径
        permission_ids: 部门ID列表, 单个 ID 接收字符串格式, 多个 ID 接收列表格式, 公开文档使用空数组
        callback_url: 回调 URL
    """

    document_http_url: str = Field(
        ..., description="文档的存储路径，必须是一个可访问的 HTTP 路径", min_length=1, max_length=1000
    )

    permission_ids: str | list[str] | None = Field(
        None, description="部门ID列表, 单个 ID 接收字符串格式, 多个 ID 接收列表格式, 公开文档使用空数组"
    )
    callback_url: str = Field(..., description="回调 URL", min_length=1, max_length=1000)


class DocumentPermissionUpdateRequest(BaseModel):
    """文档权限更新请求参数

    Attributes:
        doc_id: 文档ID
        permission_ids: 部门ID列表, 单个 ID 接收字符串格式, 多个 ID 接收列表格式, 公开文档使用空数组
    """

    doc_id: str = Field(..., description="文档ID", min_length=64, max_length=64)
    permission_ids: str | list[str] | None = Field(
        None, description="部门ID列表, 单个 ID 接收字符串格式, 多个 ID 接收列表格式, 公开文档使用空数组"
    )
