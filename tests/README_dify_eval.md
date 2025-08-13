# Dify平台RAG系统性能评估脚本

这个脚本用于评估Dify平台RAG系统在RagBench数据集上的性能，使用RAGAS评估框架。

## 功能特点

- 支持RagBench数据集的12个子任务
- 使用Dify平台API进行RAG问答
- 集成RAGAS评估框架，提供4个核心指标
- 智能限流管理，避免API调用超限
- 详细的结果导出（JSON + Excel格式）
- 异步处理，提高评估效率

## 安装依赖

```bash
pip install -r requirements_dify_eval.txt
```

## 使用方法

### 1. 基本运行

```bash
cd tests
python evaluate_dify_rag_with_ragas.py
```

### 2. 交互式选择

脚本运行后会提示你选择：
- 数据集（covidqa, cuad, delucionqa等12个选项）
- 数据集分割（train, validation, test）
- 评估样本数量（默认10个）

### 3. 评估流程

脚本会自动执行以下步骤：
1. 加载本地ragbench子任务数据
2. 使用Dify平台API生成答案
3. 运行RAGAS评估
4. 保存结果到JSON文件
5. 导出详细结果到Excel文件

## 配置说明

### Dify API配置

脚本中已配置了Dify API：
- API Key: `app-eCw9INTLaMi6O2foeSVibfy2`
- 基础URL: `https://api.dify.ai/v1`
- 端点: `/chat-messages`

### 系统提示词

脚本使用了附件中的系统提示词，确保RAG系统按照特定格式生成答案。

### 限流配置

- RPM限制: 1000次/分钟
- TPM限制: 20000 tokens/分钟
- 批次大小: 20个样本
- 批次延迟: 1.2秒

## 输出结果

### 1. 控制台输出

- 评估进度信息
- RAGAS指标得分
- 整体评估摘要

### 2. 文件输出

- **JSON结果**: `evaluation_results/dify_ragbench_ragas_evaluation_{task_name}_{timestamp}.json`
- **Excel详细结果**: `evaluation_results/dify_ragbench_detailed_results_{task_name}_{timestamp}.xlsx`

### 3. RAGAS评估指标

- **Faithfulness**: 答案忠实度
- **Answer Relevancy**: 答案相关性
- **Context Precision**: 上下文精确度
- **Context Recall**: 上下文召回率

## 注意事项

1. **数据路径**: 确保`data/ragbench/`目录下有相应的数据集文件
2. **网络连接**: 需要稳定的网络连接访问Dify API
3. **API限制**: 注意Dify平台的API调用限制
4. **模型配置**: 如果使用本地embedding模型，确保模型文件存在

## 故障排除

### 常见问题

1. **API调用失败**: 检查网络连接和API密钥
2. **数据集加载失败**: 确认数据文件路径和格式
3. **RAGAS评估失败**: 检查依赖安装和模型配置

### 调试模式

可以通过修改日志级别来获取更详细的信息：
```python
logging.basicConfig(level=logging.DEBUG)
```

## 扩展功能

脚本设计为模块化结构，可以轻松扩展：
- 添加新的评估指标
- 支持其他RAG平台
- 自定义数据处理逻辑
- 集成其他评估框架

## 技术支持

如果遇到问题，请检查：
1. 依赖包版本兼容性
2. 网络连接状态
3. API密钥有效性
4. 数据文件完整性
