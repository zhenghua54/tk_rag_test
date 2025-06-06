"""文档上传请求数据模型"""
from pydantic import BaseModel, Field, validator
from src.utils.common.args_validator import ArgsValidator
from src.utils.file.file_validator import FileValidator
from src.api.response import ErrorCode


class DocumentUploadRequest(BaseModel):
    """文档上传请求参数
    
    Attributes:
        document_path: 文档路径
        department_id: 部门ID
    """
    document_path: str = Field(
        ...,
        description="文档路径",
        min_length=1,
        max_length=500
    )
    department_id: str = Field(
        ...,
        description="部门ID",
        min_length=1,
        max_length=50
    )

    @validator('document_path')
    def validate_document_path(cls, v):
        """验证文档路径
        
        Args:
            v: 文档路径
            
        Returns:
            str: 验证后的路径
            
        Raises:
            ValueError: 路径验证失败
        """
        try:
            # 1. 基础参数校验
            ArgsValidator.validity_not_empty(v, "document_path")
            ArgsValidator.validity_type(v, str, "document_path")
            
            # 2. 文件校验
            FileValidator.validity_file_exist(v)  # 文件存在性校验
            FileValidator.validity_file_ext(v)  # 文件格式校验
            FileValidator.validity_file_name(v)  # 文件名格式校验
            FileValidator.validity_file_size(v)  # 文件大小校验
            FileValidator.validity_file_normal(v)  # 文件可读性校验
            
            # 3. PDF特殊校验
            if v.lower().endswith('.pdf'):
                FileValidator.validity_pdf_parse(v)
                
            return v
        except ValueError as e:
            # 如果是FileValidator抛出的错误，直接重新抛出
            if len(e.args) == 2 and isinstance(e.args[0], ErrorCode):
                raise
            # 如果是其他错误，包装成标准错误格式
            raise ValueError(ErrorCode.PARAM_ERROR, str(e))

    @validator('department_id')
    def validate_department_id(cls, v):
        """验证部门ID
        
        Args:
            v: 部门ID
            
        Returns:
            str: 验证后的部门ID
            
        Raises:
            ValueError: 部门ID验证失败
        """
        try:
            ArgsValidator.validity_department_id(v)
            return v
        except ValueError as e:
            # 如果是ArgsValidator抛出的错误，直接重新抛出
            if len(e.args) == 2 and isinstance(e.args[0], ErrorCode):
                raise
            # 如果是其他错误，包装成标准错误格式
            raise ValueError(ErrorCode.PARAM_ERROR, str(e)) 