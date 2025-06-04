import pytest
from src.api.base import ErrorCode

def test_chat_success(client, test_department_id, test_session_id):
    """测试聊天接口 - 成功场景"""
    response = client.post(
        "/api/v1/rag_chat",
        json={
            "query": "这是一个测试问题",
            "department_id": test_department_id,
            "session_id": test_session_id,
            "timeout": 30
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "request_id" in data
    assert "answer" in data["data"]
    assert "source" in data["data"]
    assert "tokens_used" in data["data"]
    assert "processing_time" in data["data"]

def test_chat_question_too_long(client, test_department_id):
    """测试聊天接口 - 问题过长"""
    response = client.post(
        "/api/v1/rag_chat",
        json={
            "query": "测试" * 1000,  # 2000字符以上
            "department_id": test_department_id
        }
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == ErrorCode.QUESTION_TOO_LONG
    assert "current_length" in data["data"]
    assert "max_length" in data["data"]

def test_chat_missing_params(client):
    """测试聊天接口 - 缺少必要参数"""
    response = client.post(
        "/api/v1/rag_chat",
        json={
            "query": "这是一个测试问题"
            # 缺少 department_id
        }
    )
    
    assert response.status_code == 422  # FastAPI的参数验证错误

def test_chat_invalid_department(client):
    """测试聊天接口 - 无效的部门ID"""
    response = client.post(
        "/api/v1/rag_chat",
        json={
            "query": "这是一个测试问题",
            "department_id": "invalid_id"
        }
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == ErrorCode.KNOWLEDGE_MATCH_FAILED

@pytest.mark.parametrize("timeout", [0, -1, 3600])
def test_chat_invalid_timeout(client, test_department_id, timeout):
    """测试聊天接口 - 无效的超时时间"""
    response = client.post(
        "/api/v1/rag_chat",
        json={
            "query": "这是一个测试问题",
            "department_id": test_department_id,
            "timeout": timeout
        }
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == ErrorCode.PARAM_ERROR 