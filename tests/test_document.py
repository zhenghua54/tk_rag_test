import pytest
import os
from src.api.base import ErrorCode

def test_upload_success(client, test_file, test_department_id):
    """测试文件上传 - 成功场景"""
    response = client.post(
        "/api/v1/documents",
        json={
            "document_path": test_file,
            "department_id": test_department_id
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "request_id" in data
    assert "doc_id" in data["data"]
    assert "file_name" in data["data"]
    assert "status" in data["data"]
    assert data["data"]["status"] == "completed"

def test_upload_file_not_found(client, test_department_id):
    """测试文件上传 - 文件不存在"""
    response = client.post(
        "/api/v1/documents",
        json={
            "document_path": "/path/to/non_existent_file.pdf",
            "department_id": test_department_id
        }
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == ErrorCode.FILE_NOT_FOUND

def test_upload_invalid_file_type(client, test_department_id, tmp_path):
    """测试文件上传 - 无效的文件类型"""
    # 创建一个临时的.jpg文件
    invalid_file = tmp_path / "test.jpg"
    invalid_file.write_text("test content")
    
    response = client.post(
        "/api/v1/documents",
        json={
            "document_path": str(invalid_file),
            "department_id": test_department_id
        }
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == ErrorCode.INVALID_FILE_TYPE
    assert "supported_types" in data["data"]

def test_upload_invalid_filename(client, test_department_id, tmp_path):
    """测试文件上传 - 无效的文件名"""
    # 创建一个带有特殊字符的文件名
    invalid_file = tmp_path / "test@#$%.pdf"
    invalid_file.write_text("test content")
    
    response = client.post(
        "/api/v1/documents",
        json={
            "document_path": str(invalid_file),
            "department_id": test_department_id
        }
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == ErrorCode.INVALID_FILENAME

def test_delete_success(client, test_doc_id):
    """测试文件删除 - 成功场景"""
    response = client.delete(f"/api/v1/documents/{test_doc_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "request_id" in data
    assert data["data"]["doc_id"] == test_doc_id
    assert data["data"]["status"] == "deleted"

def test_delete_with_soft_delete(client, test_doc_id):
    """测试文件删除 - 软删除"""
    response = client.delete(
        f"/api/v1/documents/{test_doc_id}",
        params={"is_soft_delete": True}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "deleted"

def test_delete_non_existent(client):
    """测试文件删除 - 文件不存在"""
    response = client.delete("/api/v1/documents/non_existent_id")
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == ErrorCode.FILE_NOT_FOUND 