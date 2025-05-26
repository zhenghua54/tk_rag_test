<html><body><table><tr><td>模块编号</td><td>模块名称</td></tr><tr><td>M1</td><td>大模型推理服务</td></tr><tr><td>M2</td><td>Embedding 服务</td></tr><tr><td>M3</td><td>Rerank服务</td></tr><tr><td>M4</td><td>向量数据库（Milvus）</td></tr><tr><td>M5</td><td>文档解析服务</td></tr><tr><td>M6</td><td>业务接口服务</td></tr><tr><td>M7</td><td>负载均衡与网关</td></tr><tr><td>M8</td><td>日志与监控</td></tr><tr><td>M9</td><td>对象存储</td></tr><tr><td>M10</td><td>带宽与安全</td></tr></table></body></html>  

<html><body><table><tr><td>用途说明</td></tr><tr><td>部署Deepseek-32B等大语言模型，用于回答生成 批量生成文本向量，使用BGE-M3模型</td></tr><tr><td>BGE-Rerank-M3模型排序</td></tr><tr><td>向量存储与相似度检索</td></tr><tr><td>OCR/MinerU文档结构化</td></tr><tr><td>API接入、用户管理</td></tr><tr><td>请求调度、安全控制</td></tr><tr><td>系统日志、运行指标 文档与向量文件存储</td></tr></table></body></html>  

<html><body><table><tr><td>推荐云服务类型</td></tr><tr><td>GPU云主机（高性能） GPU云主机（中等）</td></tr><tr><td>GPU云主机（中等）</td></tr><tr><td>高性能存储优化型主机 计算型主机（可加速）</td></tr><tr><td>计算型云主机 SLB+API网关 计算型主机 对象存储服务（OBS/OSS）</td></tr></table></body></html>  

# 推荐配置  

GPU：8 × A100 80G；CPU：64 vCPU；内存：512 GB；存储：2 TB NVMe SSD  
GPU：2 × A100 40G；CPU：32 vCPU；内存：128 GB；存储：1 TB SSD  
同上  
CPU：32 vCPU；内存：256 GB；存储：4 TB SSD  
CPU：32 vCPU；内存：128 GB；可选 GPU：T4/3090  
CPU：8 vCPU；内存：32 GB  
云服务资源  
CPU：8 vCPU；内存：32 GB；存储：2 TB HDD  
$\scriptstyle \geq 4$ TB 存储； ${ \ge } 5 0 \mathsf { M B / s }$ 吞吐  
$\scriptstyle 2 2 0 0$ Mbps 出口  

<html><body><table><tr><td>数量</td><td>说明备注</td></tr><tr><td>1独立部署优化吞吐</td><td>1满足>50并发问答，支持多线程推理</td></tr><tr><td>1可与M2合并</td><td></td></tr><tr><td></td><td>1支持高并发ANN查询</td></tr><tr><td></td><td>1按需运行，不常驻</td></tr><tr><td></td><td>2主备部署</td></tr><tr><td></td><td>1支持HTTPS、安全防护</td></tr><tr><td></td><td>1搭配Prometheus/ELK使用</td></tr><tr><td></td><td></td></tr><tr><td></td><td>支持冷热分层</td></tr><tr><td></td><td>满足50+并发需求</td></tr></table></body></html>  

<html><body><table><tr><td>弹性扩容建议</td></tr><tr><td>可按需增加实例，或使用vLLM动态分配线程 可弹性增加至4卡或多实例并发处理 如响应压力大可拆分独立部署 可配置分片与副本，或横向扩容节点集群</td></tr></table></body></html>  