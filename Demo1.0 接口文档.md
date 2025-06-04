# **Demo 1.0 接口文档**
版本：1.0

更新时间：2025-06-04

说明：本接口文档适用于 Demo 1.0，包含 **RAG 聊天**、**上传文件**、**删除文件** 等接口。采用 RESTful 风格，统一使用 application/json 作为请求与返回数据格式。

## **通用说明**

### 1. 接口规范
- 基础路径：`/api/v1`
- 请求格式：application/json
- 字符编码：UTF-8


### 2. 通用响应格式
```json
{
    "code": 0,            // 响应码：0-成功，非0-失败
    "message": "success", // 响应信息
    "data": {            // 实际数据
        // 具体内容
    }
}
```

### 3. 错误码说明
| 错误码范围 | 说明 |
|------------|------|
| 1000-1999  | 通用错误 |
| 2000-2999  | 聊天相关 |
| 3000-3999  | 文件相关 |

#### 通用错误码 (1000-1999)
| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| 1001 | 参数缺失或格式错误 | 检查请求参数是否完整且格式正确 |
| 1002 | 请求参数超出限制 | 检查参数长度或大小是否符合要求 |
| 1003 | 重复操作 | 检查是否重复提交请求 |

#### 聊天相关错误码 (2000-2999)
| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| 2001 | 问题长度超出限制 | 问题长度应在2000字符以内 |
| 2002 | 会话ID无效 | 检查session_id是否正确或重新开始会话 |
| 2003 | 模型响应超时 | 请稍后重试或减少问题复杂度 |
| 2004 | 知识库匹配失败 | 尝试调整问题描述或确认部门ID是否正确 |
| 2005 | 上下文长度超限 | 建议开启新的会话 |

#### 文件相关错误码 (3000-3999)
| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| 3001 | 文件不存在 | 检查文件路径是否正确 |
| 3002 | 文件格式不支持 | 仅支持PDF、DOCX、TXT格式 |
| 3003 | 文件大小超限 | 文件大小应小于50MB |
| 3004 | 文件名格式错误 | 文件名应仅包含字母、数字、下划线，长度不超过100字符 |
| 3005 | 文件解析失败 | 检查文件是否损坏或格式是否正确 |
| 3006 | 文件已存在 | 检查是否重复上传 |
| 3007 | 存储空间不足 | 请联系管理员处理 |



---

## **接口列表**

### 1. 健康检查：`GET /api/v1/health`
用于检查服务状态

#### 响应示例
```json
{
    "code": 0,
    "message": "success",
    "data": {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": "2025-06-04T10:00:00Z"
    }
}
```

### 2. RAG聊天：`POST /api/v1/rag_chat`
根据用户问题和指定部门ID，过滤数据并返回模型回答及其对应来源文档信息。

#### 请求参数
| 参数名 | 类型 | 必填 | 示例值 | 说明 |
|--------|------|------|---------|------|
| query | string | 是 | "请介绍服务质量流程" | 用户输入问题(最大长度2000字符) |
| department_id | string | 是 | "7e96498e-..." | 部门UUID |
| session_id | string | 否 | "sess_123..." | 会话ID(保持上下文) |
| timeout | integer | 否 | 30 | 超时时间(秒),默认30秒 |

#### 响应参数
```json
{
    "code": 0,
    "message": "success",
    "data": {
        "answer": "根据最新标准，服务质量指标包括...",
        "source": [
            {
                "doc_id": "abcdef1234567890...",
                "file_name": "服务质量手册.pdf",
                "segment_id": "seg_00042",
                "page_idx":"1",
                "confidence": 0.95
            },
            {
                "doc_id": "abcdef1234567890...",
                "file_name": "服务质量手册.pdf",
                "segment_id": "seg_00042",
                "page_idx":"2",
                "confidence": 0.95
            },
        ],
        "tokens_used": 123,
        "processing_time": 0.5
    }
}
```

### 3. 上传文件：`POST /api/v1/documents`
将服务器本地指定路径的PDF文件解析、切块并入库。

#### 请求参数
| 参数名 | 类型 | 必填 | 示例值 | 说明 |
|--------|------|------|---------|------|
| document_path | string | 是 | "/home/user/..." | 文件路径 |
| department_id | string | 是 | "7e96498e-..." | 所属部门ID |

#### 文件限制
- 支持格式：PDF、DOCX、TXT
- 单文件大小：最大50MB
- 文件名要求：仅支持字母、数字、下划线，长度不超过100字符，不区分大小写

#### 响应参数
```json
{
    "code": 0,
    "message": "success",
    "data": {
        "doc_id": "doc_789xyz",
        "file_name": "服务质量手册.pdf",
        "status": "completed",
        "department_id": "7e96498e-..."
    }
}
```

### 4. 删除文件：`DELETE /api/v1/documents/{doc_id}`
删除指定doc_id所对应的文档及其所有切块内容。

#### 请求参数
| 参数名 | 类型 | 必填 | 示例值 | 说明 |
|--------|------|------|---------|------|
| doc_id | string | 是 | "doc_789xyz" | 文档ID |
| is_soft_delete | boolean | 否 | false | 是否软删除,默认false |

#### 响应参数
```json
{
    "code": 0,
    "message": "success",
    "data": {
        "doc_id": "doc_789xyz",
        "delete_time": "2025-06-04T10:30:00Z",
        "status": "deleted"
    }
}
```

## 错误响应示例

1. 参数错误示例
```json
{
    "code": 1001,
    "message": "参数缺失或格式错误",
    "data": {
        "field": "query",
        "reason": "问题长度超过2000字符限制",
        "current_length": 2500,
        "max_length": 2000
    }
}
```

2. 文件上传错误示例
```json
{
    "code": 3002,
    "message": "文件格式不支持",
    "data": {
        "file_name": "test.jpg",
        "current_type": "jpg",
        "supported_types": [".doc", ".docx", ".ppt", ".pptx", ".pdf", ".txt"]
    }
}
```

3. 聊天错误示例
```json
{
    "code": 2003,
    "message": "模型响应超时",
    "data": {
        "timeout": 30,
        "session_id": "sess_abc123",
        "suggestion": "请简化问题或分多次询问"
    }
}
```

4. 文件解析错误示例
```json
{
    "code": 3005,
    "message": "文件解析失败",
    "data": {
        "file_name": "report.pdf",
        "error_page": 5,
        "reason": "PDF文件已加密，无法解析",
        "suggestion": "请解除文件加密后重新上传"
    }
}
```


