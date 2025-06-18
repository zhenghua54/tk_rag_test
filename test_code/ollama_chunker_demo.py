import re
import psutil
import time
import torch
import requests
from utils.log_utils import logger


def print_memory_usage():
    """打印当前内存和 GPU 显存的使用情况"""
    # CPU 内存使用
    process = psutil.Process()
    cpu_memory = process.memory_info().rss / (1024 ** 2)  # 转换为 MB
    logging.info(f"当前 CPU 内存使用量：{cpu_memory:.2f} MB")

    # GPU 显存使用(若可用)
    if torch.cuda.is_available():
        logging.info("正在获取 GPU 显存使用量...")
        gpu_memory_allocated = torch.cuda.memory_allocated() / (1024 ** 2)  # 转换为 MB
        gpu_memory_reserved = torch.cuda.memory_reserved() / (1024 ** 2)
        logging.info(f"当前 GPU 显存使用量：{gpu_memory_allocated:.2f} MB, 已预留: {gpu_memory_reserved:.2f} MB")

    # MPS 内存使用
    elif hasattr(torch.mps, 'current_allocated_memory'):
        # 获取当前分配的 MPS 内存(以字节为单位)
        mps_allocated = torch.mps.current_allocated_memory() / (1024 ** 2)  # 转换为 MB
        logging.info(f"当前 MPS 内存使用量：{mps_allocated:.2f} MB")

    else:
        logging.warning("当前设备不支持 GPU 显存使用量查询")


def validate_chunks(original_text: str, chunks: list) -> bool:
    """验证分块内容是否都来自原文"""
    # 预处理文本，移除空白字符但保留换行符
    clean_original = original_text.replace('\r\n', '\n').replace('\r', '\n')
    
    for chunk in chunks:
        # 移除可能存在的空白字符后再检查
        clean_chunk = chunk.replace('\r\n', '\n').replace('\r', '\n')
        
        # 检查是否是原文的子串
        if clean_chunk not in clean_original:
            # 尝试更宽松的匹配：检查是否包含原文的主要部分
            chunk_lines = [line.strip() for line in clean_chunk.split('\n') if line.strip()]
            original_lines = [line.strip() for line in clean_original.split('\n') if line.strip()]
            
            # 计算匹配行数
            matched_lines = 0
            for chunk_line in chunk_lines:
                # 对于标题行，要求完全匹配
                if chunk_line.startswith('#') or chunk_line.startswith('*') or chunk_line.startswith('1.') or chunk_line.startswith('2.'):
                    if any(chunk_line == orig_line for orig_line in original_lines):
                        matched_lines += 1
                # 对于表格行，要求完全匹配
                elif '|' in chunk_line:
                    if any(chunk_line == orig_line for orig_line in original_lines):
                        matched_lines += 1
                # 对于普通行，允许部分匹配
                else:
                    if any(chunk_line in orig_line for orig_line in original_lines):
                        matched_lines += 1
            
            # 如果匹配行数低于阈值，则认为验证失败
            if matched_lines / len(chunk_lines) < 0.85:  # 85% 的匹配度阈值
                logging.warning(f'发现不匹配的分块内容: {chunk[:100]}...')
                return False
    return True


def segment_text(context: str, model_name, api_base, validate=True):
    """使用 Ollama API 进行文本分块
    
    Args:
        context (str): 需要分块的文本
        model_name (str): Ollama 模型名称
        api_base (str): Ollama API 地址
        validate (bool): 是否进行分块验证，默认为 True
    """
    logging.info('=== 初始状态 ===')
    print_memory_usage()

    # 提示词
    instruction = """
    请将以下文档内容按照以下规则进行分块：

    规则：
    1. 每块以'[chunk_start]'标记开头
    2. 每块长度控制在300-500字之间
    3. 按照文档的自然章节和段落进行分块
    4. 保持原文格式，不要修改任何内容

    示例：
    [chunk_start]第一章 概述
    这是第一章的内容...

    [chunk_start]第二章 详细说明
    这是第二章的内容...

    需要分块的内容：
    {content}
    """

    prompt = instruction.format(content=context)
    logging.info(f'提示词长度: {len(prompt)}')
    logging.info(f'内容长度: {len(context)}')

    # API 调用
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,  # 保持分块稳定
            "top_p": 0.1,  # 降低随机性
            "repetition_penalty": 1.0,
            "max_tokens": 8000,
            "stop": None
        }
    }

    start_time = time.time()

    logging.info('开始 API 调用...')
    try:
        response = requests.post(
            f"{api_base}/api/generate",
            json=payload,
            timeout=600,  # 设置超时时间为600秒（10分钟）
            headers={"Content-Type": "application/json"})

        response.raise_for_status()

        result = response.json()
        text = result.get('response', '')
        logging.info(f'模型响应长度: {len(text)}')
        logging.info(f'模型响应前100个字符: {text[:100]}')

        # 提取分块
        chunks = re.findall(r'\[chunk_start\](.*?)(?=\[chunk_start\]|$)', text, re.DOTALL)
        if not chunks:
            logging.warning('分块为空，尝试使用原文作为单个分块')
            chunks = [context]

        end_time = time.time()
        logging.info(f'处理时间: {end_time - start_time:.2f}秒')

        logging.info('=== 处理完成 ===')
        print_memory_usage()

        if chunks:
            total_length = sum(len(chunk) for chunk in chunks)
            avg_length = total_length / len(chunks) if chunks else 0
            logging.info(f'总块数：{len(chunks)}, 总字符数：{total_length}, 平均每块：{avg_length:.1f} 字')

            chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
            if validate and not validate_chunks(context, chunks):
                logging.warning('分块验证失败，返回原文')
                return [context]

            return chunks
        else:
            logging.warning('未获得有效分块，返回原文')
            return [context]

    except requests.exceptions.RequestException as e:
        logger.error(f"API 调用失败: {e}")
        return [context]


if __name__ == '__main__':
    from codes.config import Config

    config = Config()

    # 记录起始状态
    logging.info('=== 程序启动 ===')
    print_memory_usage()

    md_input_file = '/Users/jason/Library/Mobile Documents/com~apple~CloudDocs/PycharmProjects/tk_rag_demo/datas/output_data/公司能力交流口径-2025:02定稿版/公司能力交流口径-2025:02定稿版.md'
    # 读取markdown文档内容
    with open(md_input_file, 'r', encoding='utf-8') as f:
        md_text = f.read()

    try:
        summarys = segment_text(md_text, model_name=config.ollama_model, api_base=config.ollama_url)
        print('总分块数：', len(summarys))
        for summary in summarys:
            print('Chunk---->')
            print(f'chunk_len: {len(summary)}')
            print(summary)

    except Exception as e:
        logger.error(f"处理过程出现错误: {e}")
        raise

    finally:
        logging.info('=== 程序结束 ===')
        print_memory_usage()
