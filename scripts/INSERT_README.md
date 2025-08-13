# RAGBench文档插入工具

## 🎯 功能说明

这个工具专门为Dify平台上已存在的RAGBench知识库插入对应的文档内容。它会：

1. **自动识别** RAGBench相关的知识库
2. **跳过已有文档**的知识库（如hagrid、emanual、delucionqa）
3. **为空知识库**插入从parquet文件提取的文档
4. **创建txt文件**并上传到对应知识库

## 🚀 使用方法

### 1. 直接运行
```bash
python scripts/insert_ragbench_docs.py
```

### 2. 使用环境变量配置
```bash
# 设置自定义参数
export MAX_DOCS_PER_DATASET=100
export UPLOAD_DELAY=0.1
export RAGBENCH_PATH="custom/path/to/ragbench"

# 运行脚本
python scripts/insert_ragbench_docs.py
```

## 📋 当前配置

- **Dify服务器**: `http://192.168.31.205`
- **API密钥**: `dataset-L7pHf6iaAwImkw5601pv3N2u`
- **RAGBench路径**: `data/ragbench`
- **每个数据集最大文档数**: 50
- **上传延迟**: 0.2秒

## 📊 知识库状态分析

根据之前的查询结果：

### 🆕 需要插入文档的知识库
- **techqa**: 0个文档
- **tatqa**: 0个文档  
- **msmarco**: 0个文档
- **hotpotqa**: 0个文档
- **finqa**: 0个文档
- **expertqa**: 0个文档
- **cuad**: 0个文档
- **covidqa**: 0个文档

### ✅ 已有文档的知识库（跳过）
- **hagrid**: 6965个文档
- **emanual**: 221个文档
- **delucionqa**: 930个文档

## 🔧 脚本特性

### 智能识别
- 自动识别RAGBench相关的知识库
- 检查文档数量，跳过已有文档的知识库
- 支持不同的数据集结构（documents列或question+response列）

### 文档处理
- 从parquet文件提取文档内容
- 自动去重和清理
- 创建格式化的txt文件
- 支持中文和英文内容

### 上传控制
- 批量上传到对应知识库
- 添加延迟避免API限制
- 自动清理临时文件
- 进度显示和错误处理

## ⚙️ 配置选项

### 环境变量
- `MAX_DOCS_PER_DATASET`: 每个数据集最大文档数（默认50）
- `UPLOAD_DELAY`: 上传间隔延迟（默认0.2秒）
- `RAGBENCH_PATH`: RAGBench数据路径（默认data/ragbench）

### 数据集优先级
- **优先级1**: techqa, tatqa, msmarco, cuad, covidqa
- **优先级2**: pubmedqa, hotpotqa, finqa, expertqa  
- **优先级3**: hagrid, emanual, delucionqa（已有文档）

## 📁 输出文件

脚本会在当前目录创建 `temp_docs/` 文件夹，用于临时存储生成的txt文件。上传完成后会自动清理。

## 🐛 故障排除

### 常见问题
1. **API权限错误**: 检查API密钥是否有上传文档权限
2. **文件路径错误**: 确认RAGBench数据路径正确
3. **网络超时**: 增加上传延迟或检查网络连接
4. **内存不足**: 减少每个数据集的最大文档数

### 调试方法
1. 运行 `quick_list_kbs.py` 检查知识库状态
2. 查看脚本输出的详细日志
3. 检查临时文件是否正确生成
4. 验证API响应和错误信息

## 💡 使用建议

1. **首次运行**: 建议先用较小的文档数量测试
2. **批量处理**: 可以调整延迟参数平衡速度和稳定性
3. **监控进度**: 使用进度条监控上传状态
4. **错误恢复**: 脚本支持断点续传，失败的知识库可以重新运行

## 🔄 工作流程

```
1. 获取所有知识库列表
   ↓
2. 识别RAGBench相关知识库
   ↓
3. 检查文档数量状态
   ↓
4. 为空知识库提取文档内容
   ↓
5. 创建txt文件并上传
   ↓
6. 清理临时文件
   ↓
7. 显示最终状态
```

现在你可以运行脚本来为空的RAGBench知识库插入文档了！
