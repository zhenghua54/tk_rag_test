"""文档删除请求数据模型"""
from pydantic import BaseModel, Field, validator
from src.api.response import ErrorCode
from src.utils.common.args_validator import ArgsValidator

class DocumentDeleteRequest(BaseModel):
    """文档删除请求参数
    
    Attributes:
        doc_id: 文档ID
        is_soft_delete: 是否软删除
    """
    doc_id: str = Field(
        ...,
        description="文档ID",
        min_length=1,
        max_length=64
    )
    is_soft_delete: bool = Field(
        False,
        description="是否软删除"
    )

    @validator('doc_id')
    def validate_doc_id(cls, v):
        """验证文档ID
        
        Args:
            v: 文档ID
            
        Returns:
            str: 验证后的文档ID
            
        Raises:
            ValueError: 文档ID验证失败
        """
        ArgsValidator.validity_doc_id(v)
        return v 