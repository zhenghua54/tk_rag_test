# 环境配置说明

## 环境变量配置

### 基础环境配置
- `ENV`: 环境标识，可选值：`dev`(开发环境)、`prod`(生产环境)

### 数据库配置

#### MySQL配置
- `DB_NAME`: 数据库名称
  - 开发环境：`tk_rag_dev`
  - 生产环境：`tk_rag_prod`
- `MYSQL_HOST`: MySQL服务器地址
  - 开发环境：`192.168.5.199`
  - 生产环境：`localhost`
- `MYSQL_USER`: MySQL用户名
- `MYSQL_PASSWORD`: MySQL密码
- `MYSQL_PORT`: MySQL端口号（默认：3306）

#### Milvus配置
- `MILVUS_HOST`: Milvus服务器地址
  - 开发环境：`192.168.5.199`
  - 生产环境：`localhost`
- `MILVUS_PORT`: Milvus端口号（默认：19530）
- `MILVUS_URI`: Milvus连接URI
- `MILVUS_TOKEN`: Milvus访问令牌

#### Elasticsearch配置
- `ES_HOST`: Elasticsearch服务器地址
  - 开发环境：`http://192.168.5.199:9200`
  - 生产环境：`http://localhost:9200`
- `ES_USER`: Elasticsearch用户名
- `ES_PASSWORD`: Elasticsearch密码
- `ES_TIMEOUT`: 请求超时时间（默认：30秒）

### 状态同步配置
- `STATUS_SYNC_ENABLED`: 是否启用状态同步（默认：true）
- `STATUS_SYNC_BASE_URL`: 状态同步接口基础URL
- `STATUS_SYNC_TIMEOUT`: 请求超时时间（默认：10秒）
- `STATUS_SYNC_RETRY_ATTEMPTS`: 重试次数（默认：3次）
- `STATUS_SYNC_RETRY_DELAY`: 重试延迟（默认：1.0秒）

### 大模型配置
- `LLM_NAME`: 大模型名称（默认：qwen）
- `DASHSCOPE_API_KEY`: 通义千问API密钥

## 配置示例

### 开发环境配置 (.env)
```bash
ENV=dev
DB_NAME=tk_rag_dev
MYSQL_HOST=192.168.5.199
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MILVUS_HOST=192.168.5.199
ES_HOST=http://192.168.5.199:9200
STATUS_SYNC_ENABLED=true
#STATUS_SYNC_BASE_URL=http://192.168.6.99:18101
```

### 生产环境配置 (.env)
```bash
ENV=prod
DB_NAME=tk_rag_prod
MYSQL_HOST=localhost
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MILVUS_HOST=localhost
ES_HOST=http://localhost:9200
STATUS_SYNC_ENABLED=true
#STATUS_SYNC_BASE_URL=http://192.168.6.99:18101
```

## 使用说明

1. 复制 `.env.example` 为 `.env`
2. 根据实际环境修改配置值
3. 确保数据库服务已启动并可访问
4. 启动应用前检查配置是否正确

## 注意事项

1. 开发环境和生产环境使用不同的数据库名称，避免数据冲突
2. 模型路径保持本地路径不变，不受环境影响
3. 大模型API调用配置保持不变
4. 状态同步接口地址根据实际部署情况调整