# 文档状态同步设计文档

## 设计原则

### 1. 关键里程碑策略

- 只同步对前端有意义的节点状态
- 包含成功和失败的关键状态点
- 确保前端不会一直处于等待状态

### 2. 状态映射机制

- 内部状态与外部状态分离
- 支持灵活的状态映射配置
- 便于后续扩展和维护

### 3. 简洁实用原则

- 去除冗余函数，只保留实际使用的接口
- 自动判断是否需要同步，减少调用复杂度
- 统一的错误处理和日志记录

## 状态同步节点

### 1. 布局就绪状态 (layout_ready)

- **触发时机**: MinerU解析完成，状态变为 `parsed`
- **前端意义**: 可以获取解析后的layout版面PDF进行展示
- **内部状态**: `parsed`
- **外部状态**: `layout_ready`

### 2. 完全处理状态 (fully_processed)

- **触发时机**: 文档所有处理步骤完成，状态变为 `splited`
- **前端意义**: 可以获取该文档的所有信息（分块、分页等）
- **内部状态**: `splited`
- **外部状态**: `fully_processed`

### 3. 处理失败状态 (processing_failed)

- **触发时机**: 任何处理步骤失败
- **前端意义**: 告知前端处理失败，可以重新上传或显示错误信息
- **内部状态**: `parse_failed`, `merge_failed`, `chunk_failed`, `split_failed`
- **外部状态**: `processing_failed`

## 配置说明

### 状态映射配置

```python
EXTERNAL_STATUS_MAPPING = {
    "parsed": "layout_ready",  # 内部状态 -> 外部状态
    "splited": "fully_processed",  # 内部状态 -> 外部状态
    # 失败状态映射
    "parse_failed": "processing_failed",  # 解析失败
    "merge_failed": "processing_failed",  # 合并失败
    "chunk_failed": "processing_failed",  # 切块失败
    "split_failed": "processing_failed",  # 切页失败
}
```

### 失败状态集合

```python
FAILURE_STATUSES = {
    "parse_failed", "merge_failed", "chunk_failed", "split_failed"
}
```

### 环境变量配置

```bash
# 状态同步配置
STATUS_SYNC_ENABLED=true
#STATUS_SYNC_BASE_URL=http://192.168.6.99:18101 # 已改为动态传入
STATUS_SYNC_TIMEOUT=10
STATUS_SYNC_RETRY_ATTEMPTS=3
STATUS_SYNC_RETRY_DELAY=1.0
```

## 核心接口

### 主要接口函数

```python
def sync_status_safely(doc_id: str, status: str, request_id: str = None, callback_url: str = None) -> None:
    """安全同步文档状态(不抛出异常)
    
    这是唯一的外部调用接口，内部自动处理：
    - 状态过滤（只同步关键状态）
    - 状态映射（内部状态转外部状态）
    - 错误处理和重试
    - 日志记录
    """
```

### 内部类方法

```python
class StatusSyncClient:
    def should_sync_status(self, internal_status: str) -> bool:
        """判断是否需要同步该状态"""

    def get_external_status(self, internal_status: str) -> Optional[str]:
        """获取对应的外部状态"""

    def is_failure_status(self, internal_status: str) -> bool:
        """判断是否为失败状态"""

    def sync_document_status(self, doc_id: str, status: str, request_id: str = None) -> bool:
        """执行实际的同步操作"""

    def sync_status_safely(self, doc_id: str, status: str, request_id: str = None) -> None:
        """安全同步（不抛出异常）"""
```

## 实现特性

### 1. 智能状态过滤

- 自动判断是否需要同步当前状态
- 避免无效的网络请求
- 提高系统效率

### 2. 失败状态处理

- 所有失败状态都会同步到外部系统
- 确保前端不会一直处于等待状态
- 提供清晰的错误反馈

### 3. 容错机制

- 支持重试机制
- 网络异常不影响主流程
- 完整的错误日志记录
- 失败状态同步失败时的特殊处理

### 4. 配置灵活性

- 支持环境变量配置
- 可动态启用/禁用功能
- 便于不同环境部署

### 5. 代码简洁性

- 去除冗余函数，只保留实际使用的接口
- 单例模式确保全局唯一客户端实例
- 统一的错误处理和日志格式

## 使用示例

### 1. 基本使用（推荐）

```python
from utils.status_sync import sync_status_safely

# 同步成功状态
sync_status_safely(doc_id="your_doc_id", status="parsed", request_id="your_request_id", callback_url="your_callback_url")

# 同步失败状态
sync_status_safely(doc_id="your_doc_id", status="parse_failed", request_id="your_request_id", callback_url="your_callback_url")
```

### 2. 在文档处理流程中的使用

```python
# 文档解析成功
try:
    # ... 解析逻辑 ...
    sync_status_safely(doc_id, "parsed", request_id, callback_url)
except Exception as e:
    # 解析失败
    sync_status_safely(doc_id, "parse_failed", request_id, callback_url)

# 文档处理完成
try:
    # ... 处理逻辑 ...
    sync_status_safely(doc_id, "splited", request_id, callback_url)
except Exception as e:
    # 处理失败
    sync_status_safely(doc_id, "split_failed", request_id, callback_url)
```

## 监控和调试

### 1. 日志级别

- `INFO`: 正常同步操作和状态过滤
- `DEBUG`: 详细的同步过程信息
- `WARNING`: 业务错误和HTTP错误
- `ERROR`: 系统异常和同步失败

### 2. 关键日志信息

- 状态过滤结果（是否需要同步）
- 内部状态和外部状态映射
- 成功/失败状态同步结果
- 重试次数和错误详情
- 失败状态同步失败的特殊警告

### 3. 日志格式

[StatusSyncClient] 状态无需同步: request_id=xxx, doc_id=xxx, status=xxx
[StatusSyncClient] 开始同步成功状态: request_id=xxx, doc_id=xxx, internal_status=xxx, external_status=xxx
[StatusSyncClient] 成功状态同步成功: request_id=xxx, doc_id=xxx, internal_status=xxx, external_status=xxx
[StatusSyncClient] 失败状态同步失败: request_id=xxx, doc_id=xxx, status=xxx

## 扩展性

### 1. 新增状态节点

- 在 `EXTERNAL_STATUS_MAPPING` 中添加映射
- 在相应处理流程中调用 `sync_status_safely`
- 无需修改核心逻辑

### 2. 自定义状态映射

- 支持不同项目使用不同的状态映射
- 通过环境变量或配置文件控制
- 保持向后兼容性

### 3. 配置扩展

- 支持自定义重试策略
- 支持自定义超时时间
- 支持自定义日志格式

## 用户体验保障

### 1. 避免无限等待

- 所有失败状态都会及时同步
- 前端可以立即显示错误状态
- 用户可以重新上传或查看错误详情

### 2. 状态一致性

- 内部状态与外部状态保持同步
- 避免前端显示错误的状态信息
- 提供准确的处理进度反馈

### 3. 系统稳定性

- 网络异常不影响主流程
- 自动重试机制提高成功率
- 完整的错误处理和日志记录