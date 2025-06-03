"""使用 LLM 提取摘要"""
import os
import json
from typing import Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from src.utils.common.logger import logger
from src.utils.common.args_validator import Validator

# 检查环境变量
load_dotenv(verbose=True)
HUNYUAN_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not HUNYUAN_API_KEY:
    raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")

# # 混元 API
# client = OpenAI(
#     api_key=HUNYUAN_API_KEY,
#     base_url="https://api.hunyuan.cloud.tencent.com/v1",
# # )

# 阿里云百炼 API
client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


def parse_table_summary(summary: str) -> Dict[str, str]:
    """解析和清洗表格摘要
    
    Args:
        summary: 模型输出的原始摘要文本
        
    Returns:
        Dict[str, str]: 包含 title 和 summary 的字典
        
    Raises:
        ValueError: 当摘要格式不正确时抛出
    """
    try:
        # 清理输入文本
        cleaned_text = summary.strip()

        # 尝试多种方式解析 JSON
        result = None

        # 1. 尝试直接解析
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError:
            pass

        # 2. 尝试提取 JSON 部分
        if not result:
            import re
            # 匹配最外层的花括号及其内容，支持嵌套
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_text)
            if json_match:
                try:
                    result = json.loads(json_match.group().strip())
                except json.JSONDecodeError:
                    pass

        # 3. 尝试修复常见格式问题
        if not result:
            # 处理可能的格式问题
            fixed_text = cleaned_text
            # 移除可能的 markdown 代码块标记
            fixed_text = re.sub(r'```json\s*|\s*```', '', fixed_text)
            # 修复可能的引号问题
            fixed_text = re.sub(r'[\'"]', '"', fixed_text)
            # 修复可能的换行问题
            fixed_text = re.sub(r'\n\s*', ' ', fixed_text)
            try:
                result = json.loads(fixed_text)
            except json.JSONDecodeError:
                pass

        # 4. 如果仍然无法解析，尝试手动构建
        if not result:
            # 尝试提取 title 和 summary
            title_match = re.search(r'"title"\s*:\s*"([^"]*)"', cleaned_text)
            summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', cleaned_text)

            if title_match and summary_match:
                result = {
                    "title": title_match.group(1),
                    "summary": summary_match.group(1)
                }
            else:
                raise ValueError("无法从文本中提取 JSON 数据")

        # 验证结果格式
        if not isinstance(result, dict):
            raise ValueError("解析结果不是字典类型")

        if "title" not in result or "summary" not in result:
            raise ValueError("解析结果缺少必要字段")

        # 清理字段值
        result["title"] = str(result["title"]).strip()
        result["summary"] = str(result["summary"]).strip()

        # 验证字段值非空
        if not result["title"] or not result["summary"]:
            raise ValueError("标题或摘要为空")

        return result

    except Exception as e:
        logger.error(f"解析表格摘要失败: {str(e)}")
        raise ValueError(f"解析表格摘要失败: {str(e)}")


def extract_table_summary(table_html: str) -> Dict[str, str]:
    """提取表格摘要
    
    Args:
        table_html: HTML 格式的表格
        
    Returns:
        Dict[str, str]: 包含 title 和 summary 的字典
    """
    # 参数验证
    Validator.validate_not_empty(table_html, "table_html")
    Validator.validate_type(table_html, str, "table_html")

    # 构建 prompt
    prompt = """你是一个表格摘要生成助手，负责从 HTML 表格中提取表格的核心主题，并输出结构化的摘要结果，用于标题生成和内容嵌入。

你的任务：
1. 提取表格反映的**主要分类主题**，生成一个**概括性标题**
2. 分析表格每类任务的执行要素（如执行方、频率、任务内容），输出**简洁摘要**
3. 以 JSON 格式返回结果，字段为 `title` 和 `summary`，不得包含额外说明文字

输出格式如下：
{{
  "title": "表格主题（如：变更管理流程）",
  "summary": "总览表格所包含的核心任务分类与执行特征，分段描述，150字内。"
}}

处理建议：
- 不同任务类别用分号 ; 分隔描述
- 若存在任务责任人、执行频率、输出文档等字段，提取其关键特征；如字段缺失则略过
- 若无明显大类字段，可从表格第一行（表头）推测任务结构
- 摘要必须覆盖所有主要任务类别，但内容应保持精炼

请你从以下 HTML 表格中提取结构化摘要：
<BEGIN_HTML>
{table_html}
<END_HTML>
"""

    try:
        completion = client.chat.completions.create(
            model="qwen-turbo",  # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
            messages=[{"role": "system", "content": "你是一个专业的数据分析师，擅长从表格中提取关键信息并生成摘要。"},
                      {"role": "user", "content": prompt.format(table_html=table_html)}
                      ]
        )

        # 获取摘要
        raw_summary = completion.choices[0].message.content

        logger.info(f"表格摘要生成成功: {raw_summary[:200]}...")

        # 解析和清洗摘要
        return parse_table_summary(raw_summary)

    except Exception as e:
        logger.error(f"生成表格摘要失败: {str(e)}")
        raise ValueError(f"生成表格摘要失败: {str(e)}")


def extract_text_summary(text: str) -> str:
    """提取文本摘要
    
    Args:
        text: 文本内容
        
    Returns:
        str: 文本摘要
    """
    # 参数验证
    Validator.validate_not_empty(text, "text")
    Validator.validate_type(text, str, "text")

    # 构建 prompt
    prompt = """你是一个专业的文本分析师，擅长从文本中提取关键信息并生成摘要。

请分析以下文本内容，并按照以下要求生成摘要：
1. 提取文本的主要内容和目的
2. 总结文本中的关键信息
3. 指出重要的发现或结论
4. 使用简洁清晰的语言描述

文本内容：
{text}

请生成摘要："""

    try:
        # 调用在线 API
        completion = client.chat.completions.create(
            model='qwen-turbo',
            stream=False,
            messages=[
                {"role": "system", "content": "你是一个专业的数据分析师，擅长从表格中提取关键信息并生成摘要。"},
                {"role": "user", "content": prompt.format(text=text)}
            ]
        )

        # 获取摘要
        raw_summary = completion.choices[0].message.content

        logger.info(f"文本摘要生成成功: {raw_summary[:200]}...")

        return raw_summary

    except Exception as e:
        logger.error(f"生成文本摘要失败: {str(e)}")
        return "抱歉，生成文本摘要时发生错误。"
