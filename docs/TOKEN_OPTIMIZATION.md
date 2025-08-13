# Token使用优化指南

## 概述

本文档提供了关于如何优化dashscope API token使用的建议，以减少成本和提高响应速度。

## Token消耗分析

### 主要消耗场景

1. **RAG生成阶段**（使用dashscope API）
   - 查询重写：每次用户查询都会调用LLM进行查询重写
   - 生成答案：基于检索到的文档和用户查询生成最终答案

2. **RAGAS评估阶段**（使用其他API）
   - 四个评估指标：faithfulness, answer_relevancy, context_precision, context_recall
   - 每个样本会调用4次LLM进行评估

### Token消耗估算

#### RAG生成阶段
- **知识库上下文**：最多10,000 tokens
- **历史对话**：最多10,000 tokens
- **系统提示词**：500-2,000 tokens
- **用户查询**：50-500 tokens
- **总计**：约15,000-25,000 tokens/请求

#### 批量评估场景
- **10个样本**：约150,000-250,000 tokens
- **100个样本**：约1,500,000-2,500,000 tokens

## 优化建议

### 1. 减少知识库上下文长度

```python
# 在core/rag/llm_generator.py中调整
context_max_len: int = 5000  # 从10000减少到5000
```

### 2. 限制历史对话长度

```python
# 在core/rag/llm_generator.py中调整
history_max_len: int = 5000  # 从10000减少到5000
```

### 3. 优化文档检索策略

```python
# 减少检索的文档数量
top_k=3  # 从5减少到3
limit=20  # 从50减少到20
```

### 4. 启用token使用监控

代码中已添加token使用监控功能：

```python
# 查看token使用统计
rag_generator = RAGGenerator()
stats = rag_generator.get_token_usage_stats()
print(f"总请求数: {stats['total_requests']}")
print(f"总token数: {stats['total_tokens']}")
print(f"平均token数/请求: {stats['avg_tokens_per_request']:.1f}")
```

### 5. 批量处理优化

```python
# 在评估脚本中启用批处理
BATCH_SIZE = 10  # 减少批次大小
BATCH_DELAY = 2.0  # 增加批次间延迟
```

### 6. 缓存机制

- 对相同查询的结果进行缓存
- 避免重复的LLM调用

### 7. 文档预处理优化

- 在文档处理阶段就控制文档长度
- 使用更智能的文档切分策略

## 监控和告警

### Token使用监控

代码中已添加以下监控功能：

1. **实时监控**：每次LLM调用都会记录token使用情况
2. **警告阈值**：
   - 知识库上下文 > 8,000 tokens时发出警告
   - 总token数 > 15,000时发出警告
3. **统计报告**：提供详细的token使用统计

### 日志示例

```
[Token统计] 请求#1: 输入12000, 输出500, 总计12500, 平均12500.0
[Token使用警告] 知识库上下文token数(8500)较高，建议优化文档长度或减少检索数量
[Token使用警告] 总token数(15000)较高，可能影响响应速度和成本
```

## 成本控制策略

### 1. 设置预算限制

```python
# 在配置中添加预算限制
MAX_TOKENS_PER_DAY = 1000000  # 每日最大token数
MAX_TOKENS_PER_REQUEST = 20000  # 单次请求最大token数
```

### 2. 智能限流

```python
# 基于token消耗的限流策略
if total_tokens > MAX_TOKENS_PER_REQUEST:
    # 触发限流逻辑
    pass
```

### 3. 优先级管理

- 重要请求优先处理
- 非关键请求可以延迟或跳过

## 最佳实践

1. **定期监控**：定期检查token使用统计
2. **优化文档**：确保文档内容简洁有效
3. **合理配置**：根据实际需求调整参数
4. **缓存策略**：对重复查询进行缓存
5. **批量处理**：合理使用批处理减少API调用次数

## 故障排除

### 常见问题

1. **Token消耗过快**
   - 检查文档长度是否过长
   - 确认历史对话是否累积过多
   - 验证检索策略是否合理

2. **响应速度慢**
   - 减少token数量
   - 优化网络连接
   - 使用缓存机制

3. **成本过高**
   - 实施预算限制
   - 优化文档内容
   - 使用更高效的检索策略

## 联系支持

如果遇到token使用相关的问题，请联系技术支持团队。


