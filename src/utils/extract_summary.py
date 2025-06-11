"""使用 LLM 提取摘要"""
import os
import json
import re
from typing import Dict
from openai import OpenAI

from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.utils.common.logger import logger
from src.utils.validator.args_validator import ArgsValidator




# 检查环境变量
HUNYUAN_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not HUNYUAN_API_KEY:
    raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")

# # 混元 API
# client = OpenAI(
#     api_key=HUNYUAN_API_KEY,
#     base_url="https://api.hunyuan.cloud.tencent.com/v1",
# )

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
        json_text = re.sub(r'^```json\n|\n```$', '', cleaned_text).strip()

        if not json_text:
            raise APIException(ErrorCode.FILE_EXCEPTION,"清理后的 Json 文本为空， 无法解析")

            
        # 尝试直接解析 JSON
        try:
            result = json.loads(json_text)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取 JSON 部分
            # 匹配最外层的花括号及其内容
            json_match = re.search(r'^\s*\{[^{}]*\}\s*$', json_text, re.DOTALL)
            if not json_match:
                raise APIException(ErrorCode.FILE_EXCEPTION,"无法从文本中提取 JSON 数据")
            result = json.loads(json_match.group().strip())


        # 验证结果格式
        if not isinstance(result, dict):
            raise ValueError("解析结果不是字典类型")
            
        if "title" not in result or "summary" not in result:
            raise ValueError("解析结果缺少必要字段")
            
        # 清理字段值
        result["title"] = result["title"].strip()
        result["summary"] = result["summary"].strip()
        
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
    ArgsValidator.validate_not_empty(table_html, "table_html")
    ArgsValidator.validate_type(table_html, str, "table_html")
    
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
        # 调用混元 API
        completion = client.chat.completions.create(
            model='qwen-turbo',
            stream=False,
            messages=[
                {"role": "system", "content": "你是一个专业的数据分析师，擅长从表格中提取关键信息并生成摘要。"},
                {"role": "user", "content": prompt.format(table_html=table_html)}
            ]
        )
        
        # 获取摘要
        raw_summary = completion.choices[0].message.content
        logger.debug(f"表格摘要生成成功: {raw_summary[:100]}...")
        
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
    ArgsValidator.validate_not_empty(text, "content")
    ArgsValidator.validate_type(text, str, "content")
    
    # 构建 prompt
    prompt = """你是一个专业的文本分析师，擅长从文本中提取关键信息并生成摘要。

请分析以下文本内容，并按照以下要求生成摘要：
1. 提取文本的主要内容和目的
2. 总结文本中的关键信息
3. 指出重要的发现或结论
4. 使用简洁清晰的语言描述

文本内容：
{content}

请生成摘要："""

    try:
        # 调用混元 API
        completion = client.chat.completions.create(
            model='qwen-turbo',
            stream=False,
            messages=[
                {"role": "system", "content": "你是一个专业的文本分析师，擅长从文本中提取关键信息并生成摘要。"},
                {"role": "user", "content": prompt.format(text=text)}
            ]
        )
        
        # 获取摘要
        summary = completion.choices[0].message.content
        logger.debug(f"文本摘要生成成功: {summary[:200]}...")
        return summary
        
    except Exception as e:
        logger.error(f"生成文本摘要失败: {str(e)}")
        return "抱歉，生成文本摘要时发生错误。"

if __name__ == '__main__':
    # 测试摘要提取
    table_html = "\n\n<html><body><table><tr><td>大类</td><td>类别</td><td>具体内容</td><td>责任人</td><td>周期</td><td>输出件</td></tr><tr><td rowspan=\"6\">变更监控</td><td>方案审批</td><td>审批过程中查看相关的工单类型、操作类型、风险等级是否符合实际场景，八要素是否完整、步骤 清晰</td><td>区域业务TD</td><td>按需</td><td>在线评审</td></tr><tr><td>履行确认</td><td>每天10点导出当天至第二天上午前的变更，确认是否正常履行，取消或延期提前修改时间或取消</td><td>区域网络安全专员</td><td>每天</td><td>变更监控群提醒</td></tr><tr><td>授权完整</td><td>三授权是否完整，操作时间是否在授权时间内，授权获取时间是否在授权开始时间前，二次授权获 取是否及时</td><td>区域网络安全专员</td><td>每天</td><td>质量考核记录表</td></tr><tr><td>操作知会</td><td>变更开始及完成是否在交付群发送知会</td><td>区域网络安全专员</td><td>按需</td><td>质量考核记录表</td></tr><tr><td>工单闭环</td><td>跟踪已经完成的工单，提醒工程师及时闭环</td><td>区域维护经理/质量经理</td><td>按需</td><td></td></tr><tr><td>人员资质</td><td>派单前审视人员技能等级、产品归类等，确保不出现跨产品、技能不符履行工单</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td rowspan=\"5\">WO工单</td><td>SLA</td><td>每天跟踪当天需要上门的工单，要求到达时间前1小时还未打卡，电话提醒工程师</td><td>质量经理</td><td>按需</td><td></td></tr><tr><td>合规运营</td><td>合规履行指标项审核</td><td>质量经理</td><td>每天</td><td>微信提醒，质量考核记录 表</td></tr><tr><td>单次人天</td><td>打卡日期满足配额，提前提醒工程师打卡规则</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td>单次人天</td><td>日报发送规范检查、关单附件审核 每天查看已完成未闭环的整改工单，提醒工程师尽快上传材料审核是否都已创建变更单，如无需提</td><td>质量经理</td><td>按需</td><td></td></tr><tr><td>整改</td><td>供备案凭证</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td></td><td>设备健康检查</td><td>每天查看已完成未闭环的巡检工单，提醒工程师尽快上传材料审核，验收及实际履行的条目是否- 致，未巡检的设备不要出现在验收中。</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td rowspan=\"5\">驻场管理</td><td>WO工单 出入场安全检查</td><td>日报发送规范检查、关单附件、合规性审核</td><td>质量经理</td><td>每天</td><td>异常输出质量考核记录表</td></tr><tr><td>背景调查</td><td>出入场签署安全检查 入场前完成背景调查</td><td>驻场主管/质量经理 HR/驻场主管</td><td>按需 按需</td><td>员工入场安全检查表 背景调查报告</td></tr><tr><td>客户授权</td><td>入场签署长期授权，保证在驻场期间，一直有授权</td><td>驻场主管/质量经理</td><td>按需</td><td>驻场授权电子件、短信授</td></tr><tr><td>电子围栏</td><td>入场前设置电子围栏，电子围栏需要是客户局点地址，每月审视所有驻场电子围栏合理性</td><td>驻场主管</td><td>按需</td><td>权</td></tr><tr><td>入场管理</td><td>提交入场电子流</td><td>驻场主管</td><td>按需</td><td>系统提交电子流 系统提交电子流</td></tr></table></body></html>\n\n"
    summary = extract_table_summary(table_html)