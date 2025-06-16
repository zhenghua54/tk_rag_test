"""
    语义分块 --> 效果不好, 不使用
"""

from pathlib import Path
import sys
import os
import time
from tqdm import tqdm

# 设置 PyTorch 显存分配参数
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from transformers import AutoModelForCausalLM, AutoTokenizer
from langchain.prompts import PromptTemplate
import torch

from config.settings import Config


model_path = "/data/models/Qwen/Qwen2.5-14B-DeepSeek-R1-1M"

# 加载模型
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    trust_remote_code=True,
    torch_dtype=torch.float16,  # 使用 float16 来减少显存使用
    device_map="auto"  # 自动选择最佳设备
)

# 设置提示词
instruction = """请对以下文档内容进行语义分块，要求：
1. 不得篡改原文
2. 根据自然段落和语义完整性分块
3. 每块长度控制在 300-500 字
4. 块之间通过"\n======\n"分割
5. 只输出分块后的内容

分块规则：
1. 表格内容必须完整保留，不可截断
2. 图片说明与相关段落合并
3. 连续标题序号必须保持在同一块
4. 公式和引用必须保持上下文完整
5. 每个块必须是完整的语义单位

输出格式：
- 只输出分块结果
- 不包含任何其他内容
- 不重复输出相同内容
- 不截断任何内容

文档内容:
{document_content}"""

# 初始化提示词模板
prompt_template = PromptTemplate(
    template=instruction,
    input_variables=["document_content"]
)

def process_document(document_content, window_size=1000, stride=500):
    """
    对文档进行滑动窗口处理，确保每个窗口的内容都能被模型处理
    
    Args:
        document_content (str): 原始文档内容
        window_size (int): 窗口大小
        stride (int): 滑动步长
    
    Returns:
        list: 分块后的文本列表
    """
    chunks = []
    total_windows = (len(document_content) - window_size) // stride + 1
    
    # 使用tqdm创建进度条
    with tqdm(total=total_windows, desc="文档分块进度") as pbar:
        for i in range(0, len(document_content), stride):
            chunk = document_content[i:i + window_size]
            if not chunk:  # 跳过空块
                continue
                
            # 填充提示词模板
            text = prompt_template.format(document_content=chunk)
            
            # 将提示词转换为模型输入
            model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
            
            # 生成文本
            output_ids = model.generate(
                **model_inputs,
                max_new_tokens=1024,
                do_sample=False,    # 禁用采样
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id  # 显式设置填充 token
            )
            
            # 解码输出
            output_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
            
            # 提取分块结果（只取最后一个回答部分）
            try:
                # 找到最后一个"请直接输出分块结果"之后的内容
                last_prompt = "请直接输出分块结果，不要包含任何其他内容。"
                if last_prompt in output_text:
                    output_text = output_text.split(last_prompt)[-1].strip()
                
                # 分割并清理结果
                chunk_results = output_text.split("\n======\n")
                chunks.extend([c.strip() for c in chunk_results if c.strip()])
            except Exception as e:
                print(f"处理输出时出错: {e}")
                print(f"原始输出: {output_text}")
                continue
            
            # 更新进度条
            pbar.update(1)
            pbar.set_postfix({"当前块数": len(chunks)})
    
    return chunks

# 记录开始时间
start_time = time.time()


