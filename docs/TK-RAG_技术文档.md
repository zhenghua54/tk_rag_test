# TK-RAG 智能问答系统技术文档

## 一、系统概述

TK-RAG 是基于 LangGraph + LangChain 构建的 RAG+Agent 混合问答系统，支持多格式文档解析、智能检索与生成式问答。系统采用微服务架构，具备高可扩展性、可复用性和强大的日志监控能力。

---

## 二、技术架构

### 1. 框架与基础设施

- **LangGraph + LangChain**：核心智能体与工作流编排，支持多 Agent 协作、状态管理与人机中断（interrupt）等高级特性。
- **FastAPI**：高性能异步 Web 框架，提供 RESTful API 服务。
- **OneAPI**：统一管理本地与在线大模型 API 调用，支持动态路由与健康检查。
- **vLLM**：本地大模型推理优化，提升推理效率与吞吐量。
- **Celery**：分布式任务队列，异步处理文档解析、向量化等耗时任务。
- **多线程与线程锁**：确保任务隔离与并发安全。
- **统一日志服务**：支持 info、debug、warning、exception 等多级别日志，便于监控与追溯。

### 2. 大模型与智能体

- **Embedding & Rerank**：采用 BGE 系列模型（如 bge-m3-v2）进行文本向量化与检索结果重排序。
- **生成模型**：支持通义千问（qwen）、DeepSeek 等多种兼容 OpenAI 接口的模型，支持在线+本地混合调用与对话中动态切换。
- **模型管理**：通过 OneAPI/vLLM 实现统一模型注册、路由、健康检查与资源回收。

### 3. 文档处理

- **MinerU2.x**：PDF 文档结构化解析，支持表格、图片、文本等多类型内容抽取。
- **LibreOffice**：多格式文档（doc/docx/ppt/pptx）转 PDF，作为 MinerU 的输入。
- **分块与向量化**：文档内容按页/段落智能分块，生成稠密/稀疏向量，便于后续检索。

### 4. 数据存储与索引

- **Milvus**：向量数据库，支持稠密向量检索与 BM25 稀疏向量检索（混合检索），并承担全文检索功能。未来将完全替代 Elasticsearch，统一检索与索引能力。
- **MySQL**：存储文档元数据、分块信息、会话历史等。
- ~~**Elasticsearch**：全文检索与 BM25 检索，提升召回率。~~（后续将去除，相关功能由 Milvus 实现）
- **Redis**：缓存服务，提升会话历史、检索结果等高频数据的访问效率。

### 5. 其他特性

- **可复用性**：各模块高度解耦，便于独立扩展与复用。
- **多线程支持**：文档处理、检索、生成等核心流程均支持多线程并发。
- **生命周期管理**：应用启动/关闭自动初始化与清理资源，防止内存泄漏。

---

## 三、核心模块说明

### 1. RAG 检索与生成

- **混合检索**：结合 Milvus 向量检索与 ES BM25 检索，提升召回率与相关性。
- **重排序**：BGE-reranker 对检索结果进行相关性打分与排序。
- **上下文构建**：根据历史对话、检索文档智能构建 RAG 上下文，提升生成质量。
- **查询重写**：基于历史对话与当前问题，自动重写检索用 query。

### 2. Agent 工作流（LangGraph）

- **状态定义**：采用 TypedDict/Annotated 等类型安全方式定义 Agent 状态。
- **节点与边**：每个功能（如检索、生成、工具调用）为一个节点，节点间通过 add_edge/add_conditional_edges 灵活编排。
- **中断与人机协作**：支持 interrupt，允许人工审核/编辑/审批关键节点结果。
- **工具集成**：通过 ToolNode/自定义工具节点，支持外部 API、数据库、搜索等工具调用。

### 3. 文档处理

- **格式转换**：非 PDF 文档通过 LibreOffice 转换为 PDF。
- **结构解析**：PDF 由 MinerU 解析为结构化 JSON，支持表格、图片、文本等多类型内容。
- **内容分块**：按页/段落分块，生成向量，存入 Milvus/ES。
- **缓存与清理**：处理过程中的中间文件、缓存目录自动清理，防止磁盘占用。

### 4. 模型与 API 管理

- **OneAPI**：统一注册、路由、调用所有模型（本地/在线），支持健康检查与动态切换。
- **vLLM**：本地推理优化，支持大模型高效推理与多实例部署。
- **Celery**：异步任务调度，支持任务优先级、重试、进度追踪与监控。

---

## 四、典型开发与集成示例

### 1. LangGraph 基本用法

```python
from typing import Annotated
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]

graph_builder = StateGraph(State)
llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages")]]}

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()
```

### 2. 工具调用与条件分支

```python
from langgraph.prebuilt import ToolNode

def get_weather(location: str):
    if location.lower() in ["sf", "san francisco"]:
        return "It's 60 degrees and foggy."
    else:
        return "It's 90 degrees and sunny."

tool_node = ToolNode([get_weather])
graph_builder.add_node("tools", tool_node)
# 通过 add_conditional_edges 实现工具调用分支
```

### 3. 人机中断与审批

```python
from langgraph.types import interrupt, Command

def human_approval(state):
    is_approved = interrupt({
        "question": "是否通过当前输出？",
        "llm_output": state["llm_output"]
    })
    if is_approved:
        return Command(goto="approved_path")
    else:
        return Command(goto="rejected_path")
```

---

## 五、部署与运维建议

- **容器化部署**：推荐使用 Docker Compose 管理 FastAPI、Redis、MySQL、Milvus、Elasticsearch 等服务。
- **资源监控**：建议接入 Prometheus + Grafana 监控各服务状态与性能。
- **日志采集**：统一日志格式，便于 ELK/Graylog 等日志平台采集与分析。
- **安全加固**：API 鉴权、数据库权限、Redis 访问控制等需严格配置。

---

## 六、版本迭代建议

1. **第一阶段**：补全 Redis 缓存、OneAPI 统一管理、vLLM 本地推理、Celery 任务队列等基础设施。
2. **第二阶段**：集成 LangGraph，完善 Agent 工作流与工具调用。
3. **第三阶段**：优化检索与生成链路，提升性能与可维护性。
4. **第四阶段**：完善监控、日志、测试与文档，保障系统稳定运行。

---

如需具体模块代码示例、API 设计或集成细节，可随时补充。此文档可作为团队开发、架构设计与后续迭代的权威参考。

## 七、优化与问题解决

### 1. 召回不稳定（检索结果不一致）
- **原因分析**：
  - 检索参数（如 top_k、score_threshold）未固定，或向量化/分词存在随机性。
  - 检索后未做去重/排序，导致结果波动。
- **优化方案**：
  - 固定检索参数，明确 top_k、score 阈值。
  - 检索后统一排序（如按分数降序），并对结果做去重。
  - 向量化模型和分词器版本固定，避免模型热更新导致的向量漂移。
  - 检索流程增加日志，便于追踪异常。

### 2. 模型回答不受控（突破约束条件）
- **原因分析**：
  - Prompt 设计不严谨，未对输出范围做硬性限制。
  - 检索结果为空时，模型自由发挥。
- **优化方案**：
  - 优化系统 prompt，增加"仅基于检索内容回答""无相关信息时回复固定模板"等约束。
  - 检索为空时，直接返回"知识库无相关信息"，不调用生成模型。
  - 对输出内容做正则/关键词过滤，防止越界。
  - 增加模型输出后处理，二次校验。

### 3. 前端显示问题（不相关内容被返回）
- **原因分析**：
  - 检索召回/重排序阈值过低，低相关内容未过滤。
  - 前端未对内容做二次筛选。
- **优化方案**：
  - 提高重排序分数阈值（如只展示分数大于某值的内容）。
  - 后端接口返回时增加相关性过滤。
  - 前端根据 metadata 标记，仅展示高相关内容。
  - 支持用户反馈，标记无关内容，反向优化召回。

### 4. 重排序分数异常（2-3分内容被判为不相关）
- **原因分析**：
  - Rerank 模型分数分布不均，阈值设置不合理。
  - 训练数据 domain gap，导致分数解释偏差。
- **优化方案**：
  - 统计分数分布，动态调整相关性阈值。
  - 结合业务实际，人工标注一批样本，微调 rerank 阈值。
  - 多模型融合 rerank，提升鲁棒性。
  - 分数归一化处理，便于前端理解。

### 5. 对话历史污染（错误回答影响后续对话）
- **原因分析**：
  - 错误/无关内容被写入历史，影响后续上下文。
  - 历史对话未做有效过滤。
- **优化方案**：
  - 对每轮对话结果做质量评估，低质量内容不写入历史。
  - 支持用户撤回/删除历史消息。
  - 对历史内容做相关性筛选，仅保留高相关对话。
  - 增加对话 session 质量监控，发现异常及时告警。

--- 