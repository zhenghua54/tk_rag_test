"""
优化后的 HTML 表格线性化模块：
- 通过 html_table_extractor 将表格展平为 2 维数组的数字键内容矩阵
- 将数字键内容矩阵解析为字段名结构的 JSON 内容
- 分析前 3 列,进行按行分组, 并统计分组信息
- 构建分组文本, 并统计
- 解析失败的则由大模型兜底
"""

# 全局补丁:修改 bs4 中 Python3.10 版本后不支持的 collections.Callable 为 collections.abc.Callable
# - 也可以去 bs4 源码中修改替换
import collections.abc
import json
import re
from html import escape, unescape

if not hasattr(collections, "Callable") and hasattr(collections.abc, "Callable"):
    collections.Callable = collections.abc.Callable

from bs4 import BeautifulSoup
from html_table_extractor.extractor import Extractor
from typing import List, Dict, Optional, Any
from rich import print

from utils.log_utils import logger
from utils.llm_utils import render_prompt, llm_manager


def html_to_extractor_result(html: str) -> List[List[str]]:
    """
    HTML 表格转换为 html_table_extractor 解析结果
    
    Args:
        html: HTML 表格字符串
        
    Returns:
        List[List[str]: html_table_extractor 解析后的数字键内容矩阵
    """
    try:
        # 初始化html提取器
        soup = BeautifulSoup(html, 'html.parser')
        # 提取table部分
        table_html = soup.find("table")
        # 未提取到表格内容
        if table_html is None:
            raise ValueError("未找到 table 元素")

        # 提取数字键内容矩阵
        extractor = Extractor(str(table_html))
        extractor.parse()

        return extractor.return_list()

    except Exception as e:
        logger.error(f"[Table Linearize] HTML 表格解析失败: {str(e)}")
        raise ValueError(f"HTML 表格解析失败: {str(e)}")


def matrix_to_field_json(matrix: List[List[str]]) -> List[Dict[str, str]]:
    """
    将数字键矩阵转换为字段名结构的 JSON 内容

    Args:
        matrix: html_table_extractor 解析后的数字键矩阵

    Return:
        List[Dict[str,str]]: 字段名结构的 JSON 内容
    """

    if not matrix:
        return []

    # 抽取第一行做标题判断
    header_row = matrix[0] if matrix else []

    # 简单的表头行检测: 不为空,且所有字段均不为空
    if header_row and all(cell and cell.strip() for cell in header_row):
        field_names = [i.strip() for i in header_row]
        data_rows = matrix[1:]  # 跳过表头行
    else:
        field_names = [f"字段{i}" for i in range(len(header_row))]
        data_rows = matrix  # 没有表头,全部作为数据

    # 转换为字段名结构
    result = []
    for row in data_rows:
        if not row:
            # 跳过空行
            continue

        # 确保行长度与字段名一致, 使用空字符串补齐
        if len(row) > len(field_names):
            normalize_row = row[:len(field_names)]
        else:
            normalize_row = row + [""] * (len(field_names) - len(row))

        # 构建字段名字典
        row_dict = {}
        for i, field_name in enumerate(field_names):
            if i < len(normalize_row):
                cell_value = normalize_row[i]
                if cell_value is None:
                    cell_value = ""
                row_dict[field_name] = normalize_row[i].strip()

        result.append(row_dict)

    return result


def _build_groups(json_data: List[Dict[str, str]], group_fields: List[str]) -> Dict[str, List[Dict[str, str]]]:
    """
    统一的分组构建函数

    Args:
        json_data: 字段名结构的 JSON 内容
        group_fields: 分组字段列表，按优先级排序

    Returns:
        Dict[str, List[Dict[str, str]]]: 分组后的内容
    """
    if not json_data or not group_fields:
        return {"未分组": json_data}

    groups = {}

    for row in json_data:
        if not row:
            continue

        # 构建分组键
        group_key_parts = []
        for field in group_fields:
            if field in row:
                value = row[field].strip()
                if value:
                    group_key_parts.append(value)

        # 生成分组键
        if group_key_parts:
            group_key = " - ".join(group_key_parts)
        else:
            group_key = "未分类"

        # 添加到分组
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(row)

    return groups


def _determine_group_fields(json_data: List[Dict[str, str]]) -> List[str]:
    """
    根据数据特征决定使用哪些字段进行分组

    Args:
        json_data: 字段名结构的 JSON 内容

    Returns:
        List[str]: 分组字段列表，按优先级排序
    """
    if not json_data:
        return []

    field_names = list(json_data[0].keys()) if json_data[0] else []
    if len(field_names) < 2:
        return field_names[:1]  # 只有一列时使用第一列

    first_field = field_names[0]
    second_field = field_names[1]

    # 分析第一列数据
    first_col_values = [row.get(first_field, "").strip() for row in json_data if row]
    unique_first = len(set([v for v in first_col_values if v]))

    # 分析第二列数据
    second_col_values = [row.get(second_field, "").strip() for row in json_data if row]
    unique_second = len(set([v for v in second_col_values if v]))

    # 决策逻辑
    if unique_first == 0:
        # 第一列全为空，使用第二列
        if unique_second == 0:
            # 第二列也为空,最多使用第三列
            return field_names[:3]
        else:
            # 使用第二列
            return [second_field]
    elif unique_first == 1:
        # 第一列只有一个值，使用两列组合
        if unique_second == 0:
            # 第二列全为空, 只使用第一列
            return [first_field]
        elif unique_second == 1:
            # 第二列也只有一列,那就使用第三列
            return field_names[:3]
        else:
            # 使用两列组合
            return [first_field, second_field]
    else:
        # 第一列有多个值，只使用第一列
        return [first_field]


def group_by_smart_strategy(json_data: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """
    智能分组：组合使用分组字段确定和分组构建

    Args:
        json_data: 字段名结构的 JSON 内容

    Returns:
        Dict[str, List[Dict[str, str]]]: 分组后的内容
    """
    # 确定分组字段
    group_fields = _determine_group_fields(json_data)

    # 构建分组
    return _build_groups(json_data, group_fields)


def linearize_grouped_data(grouped_data: Dict[str, List[Dict[str, str]]]) -> Dict[str, Any]:
    """
    将分组后的内容转换为线性化文本

    Args:
        grouped_data: 分组后的内容

    Returns:
         Dict[str,Any]: 线性文本和相关统计信息
    """
    if not grouped_data:
        return {
            "groups": [],
            "total_chars": 0,
            "group_stats": []
        }

    groups = []
    group_stats = []
    total_chars = 0

    for group_name, group_items in grouped_data.items():
        if not group_items:
            continue
        # 构建分组文本
        lines = list()

        # 添加分组标题
        lines.append(f"{group_name}: ")

        # 处理分组内的每个条目
        for item in group_items:
            # 构建条目描述
            item_parts = []
            for field_name, field_value in item.items():
                # 清理换行符, 处理超长文本自动转换的问题
                cleaned_value = field_value.replace('\n', '').replace('\r', '')
                item_parts.append(f"{field_name}: {cleaned_value}")

            if item_parts:
                # 使用 - 分割不同行, 使用 ; 拼接同一行的多个列
                lines.append(f"- {'; '.join(item_parts)}")

        # 换行符拼接各分组的文本, 并计算字符数
        group_text = '\n'.join(lines).strip()
        group_chars = len(group_text)

        # 追加该分组的文本
        groups.append(group_text)

        group_stats.append({
            "group_name": group_name,  # 分组名称
            "item_count": len(group_items),  # 分组数量
            "char_count": group_chars  # 分组字符数
        })
        total_chars += group_chars

    return {
        "groups": groups,
        "total_chars": total_chars,
        "group_stats": group_stats
    }


def html_to_structured_linear(html: str, caption: Optional[str] = None) -> Dict[str, Any]:
    """
    HTML 表格转换为结构化文本

    Args:
        html: HTML 表格字符串
        caption: 表格标题

    Returns:
        Dict[str, Any]: 包含各种格式的转换结果, 转换失败时:
            - 优先对模型提取的结构化内容尝试线性化流程
            - 兜底则直接返回模型输出的结果
    """
    try:
        # 步骤1：HTML → html_table_extractor结果
        matrix: List[List[str]] = html_to_extractor_result(html)

        if not matrix or not matrix[0]:
            raise ValueError("html_table_extractor结果 提取为空表或结构异常")

        # 步骤2：数字键矩阵 → 字段名结构JSON
        json_data: List[Dict[str, str]] = matrix_to_field_json(matrix)

        # 步骤3：字段名JSON → 分组内容
        grouped_data: Dict[str, List[Dict[str, str]]] = group_by_smart_strategy(json_data)

        # 步骤四: 分组内容 → 分组线性化文本列表()
        linearize_result: Dict[str, Any] = linearize_grouped_data(grouped_data)

        # 添加标题
        if caption:
            result = {f"表格标题: {caption}": linearize_result["groups"]}
        else:
            result = {"表格无标题": linearize_result['groups']}

        return {
            "source": "parser-linear",
            "content": result,
            "meta": {
                "rows": len(matrix),
                "cols": len(matrix[0]) if matrix else 0,
                "groups": len(grouped_data),
                "total_chars": linearize_result['total_chars'],
                "group_stats": linearize_result['group_stats']
            }
        }


    except Exception as e:
        logger.error(f'[Table Linearize] 表格线性化失败: {str(e)}')
        logger.debug(f'[Table Linearize] 使用模型提取方法...')

        # 降级处理: 使用大模型进行提取
        llm_output = extract_table_summary(html)
        logger.debug(f"[Table Linearize] 模型输出清洗后: \n {llm_output:500}")

        try:
            # 尝试对大模型提取的表格结构进行分组
            logger.debug(f"[Table Linearize] 分组模型提取结果")
            grouped_data: Dict[str, List[Dict[str, str]]] = group_by_smart_strategy(llm_output)

            # 步骤四: 分组内容 → 分组线性化文本列表()
            logger.debug(f"[Table Linearize] 线性化分组后的表格内容")
            linearize_result: Dict[str, Any] = linearize_grouped_data(grouped_data)

            # 添加标题
            if caption:
                result = {f"表格标题: {caption}": linearize_result["groups"]}
            else:
                result = {"表格无标题": linearize_result['groups']}

            return {
                "source": "llm-linear",
                "content": result,
                "meta": {
                    "groups": len(grouped_data),
                    "total_chars": linearize_result['total_chars'],
                    "group_stats": linearize_result['group_stats']
                }
            }

        except Exception as fallback_error:
            logger.error(f"[Table Linearize] 对模型提取结果进行分组: {str(fallback_error)}")
            logger.debug(f"[Table Linearize] 分组/线性化模型提取结果失败, 使用模型输出结果")
            return {
                "source": "llm_fallback",
                "content": llm_output,
                "meta": {
                    "total_chars": len(str(llm_output)),
                }
            }


# === 摘要生成 ===
def _extract_json_array(text: str) -> List[Dict[str, str]]:
    """
    从模型输出中提取JSON数组

    Args:
        text: 模型输出的文本

    Returns:
        List[Dict[str, str]]: 提取的JSON数组
    """
    try:
        # 匹配 ```json 和 ``` 之间的内容
        pattern = r'```json\s*(.*?)\s*```'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            json_content = match.group(1).strip()
            logger.debug(f"模型生成的表格摘要:\n {json_content}")
            return json.loads(json_content)
        else:
            raise ValueError("未找到JSON代码块")

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {str(e)}")
        raise ValueError(f"JSON解析失败: {str(e)}")
    except Exception as e:
        logger.error(f"JSON提取失败: {str(e)}")
        raise ValueError(f"JSON提取失败: {str(e)}")


def extract_table_summary(html: str) -> List[Dict[str, str]]:
    """提取表格摘要， 调用LLM接口并解析输出
    Args:
        html: HTML 格式的表格
    Returns:
        List[Dict[str, str]]: 从 LLM 生成的 json 内容中提取出的解析结果
    """
    # 获取提示词
    prompt, config = render_prompt("table_summary_v2", {"table_html": html})

    raw = llm_manager.invoke(
        temperature=config['temperature'],
        system_prompt=prompt,
        max_tokens=config['max_tokens'],
        invoke_type="表格结构化提取"
    )
    logger.debug(f"表格结构化提取成功: {raw[:200]}...")
    return _extract_json_array(raw)


# === html 格式表格编码(MySQL 存储使用) ===
def escape_html_table(html: str) -> str:
    """
    将html格式的表格通过 escape 进行编码,避免特殊字符存储报错

    Args:
        html: html 格式内容

    Returns:
        str: escape 编码后的 html 内容, 编码失败返回空字符串
    """
    try:
        if not html or not html.strip():
            return ""

        # 直接对 HTML 字符串进行 escape 编码
        escaped_html: str = escape(html)

        return escaped_html
    except Exception as e:
        logger.error(f"[Table Linearize] HTML 编码失败: {str(e)}")
        return ""


def unescape_html_table(escaped_html: str) -> str:
    """
    将 escape 编码后的表格 HTML 反向编码还原

    Args:
        escaped_html: escape 编码后的表格 HTML 字符串

    Returns:
        str: unescape 反编码后还原的表格 html 字符串
    """
    try:
        if not escaped_html or not escaped_html.strip():
            return ""

        # 直接对 HTML 字符串进行 escape 编码
        unescaped_html: str = unescape(escaped_html)

        return unescaped_html
    except Exception as e:
        logger.error(f"[Table Linearize] HTML 反编码失败: {str(e)}")
        return ""


if __name__ == '__main__':
    # html_table = "<table><tr><td>大类</td><td>分类</td><td>类别</td><td>具体内容</td><td>责任人</td><td>周期</td><td>输出件</td></tr><tr><td rowspan=\"24\">日常管理</td><td rowspan=\"7\">变更监控</td><td>方案审批</td><td>审批过程中查看相关的工单类型、操作类型、风险等级是否符合实际场景，方案是否符合九要素。</td><td>安全员</td><td>按需</td><td rowspan=\"7\">变更监控表（NetCare 系统表为主）</td></tr><tr><td>履行确认</td><td>每天 9 点导出当天至第二天上午前的变更，确认是否正常履行，取消或延期提前修改时间或取消。</td><td>安全员</td><td>每天</td></tr><tr><td>变更积分</td><td>确认工程师变更积分是否符合要求，不符合更换人员。</td><td>安全员</td><td>每天</td></tr><tr><td>操作时间</td><td>确认操作时间，不允许在业务高峰期操作，客户特殊要求需要客户书面证明。</td><td>安全员</td><td>每天</td></tr><tr><td>授权完整/微信知会</td><td>三授权是否完整，操作时间是否在授权时间内，开始完成知会是否发送。</td><td>安全员</td><td>每天</td></tr><tr><td>内部打卡通报</td><td>打卡开始先进行内部通报，确认符合规定后打卡开始、打卡结束。</td><td>安全员</td><td>每天</td></tr><tr><td>工单闭环</td><td>每天跟踪已经完成的工单，提醒工程师及时闭环。</td><td>安全员</td><td>每天</td></tr><tr><td rowspan=\"5\">维护管理</td><td>人员资质</td><td>派单前审视人员技能等级、产品线归类，确保不出现跨产品、技能不符履行工单。</td><td>维护经理</td><td>每天</td><td></td></tr><tr><td>SLA</td><td>跟踪当天需要上门的工单，电话提醒工程师。</td><td>维护经理</td><td>每天</td><td></td></tr><tr><td>合规运营</td><td>接单、派单、预约、授权、关单等合规项的跟踪、提醒。</td><td>维护经理</td><td>每天</td><td></td></tr><tr><td>单次例外值守</td><td>打卡日期满足配额，提前提醒工程师打卡规则</td><td>维护经理</td><td>每天</td><td></td></tr><tr><td>整改</td><td>整改进度及整改工单执行情况跟踪</td><td>维护经理</td><td>每天</td><td></td></tr><tr><td rowspan=\"6\">驻场管理</td><td>背景调查</td><td>入场前完成背景调查。</td><td>驻场管理</td><td>按需</td><td>背景调查表</td></tr><tr><td>客户授权</td><td>入场签署长期授权，核实授权主体，保证在驻场期间，一直有授权。</td><td>驻场管理</td><td>按需</td><td>驻场授权文件</td></tr><tr><td>入场手续</td><td>入场手续办理，核实电子围栏打卡地址手否合规</td><td>驻场管理</td><td>按需</td><td rowspan=\"4\">邮件</td></tr><tr><td>离场交接</td><td>人员离场邮件知会，提醒客户修改帐号密码。</td><td>驻场管理</td><td>按需</td></tr><tr><td>周月报</td><td>每周检查周报是否上传及时，周报规范是否合规，每月检查月报上传及时性，月报规范是否合规。</td><td>驻场管理</td><td>每周</td></tr><tr><td>考勤</td><td>每周统计驻场考勤打卡数据，针对缺卡、迟到、早退的进行申述。</td><td>驻场管理</td><td>每周</td></tr><tr><td rowspan=\"4\">入离职管理</td><td>入职学习</td><td>人员入职，发送网络安全、流程规范等相关学习材料。</td><td>文员行政</td><td>按需</td><td>无</td></tr><tr><td>资源录入帐号申请</td><td>代表处定级面评后，录入资源，申请工作帐号、权限、邮箱、工卡。</td><td>文员行政</td><td>按需</td><td>邮件</td></tr><tr><td>离职 checklist</td><td>确认工作是否完成交接、资源是否移交。个人电脑是否删除公司及客户数据。</td><td>文员行政</td><td>按需</td><td>离职交接记录表（OA 系统）</td></tr><tr><td>帐号注销</td><td>离职后发起工卡、邮箱、帐号、权限的注销（华为侧及公司侧）。</td><td>文员行政</td><td>按需</td><td>邮件</td></tr><tr><td rowspan=\"2\">资源管理</td><td>资源清除</td><td>人员当月离职，在当月资源考核数据发出后删除离职人员 iResouces 资源。</td><td>质量经理</td><td>按需</td><td>通讯录</td></tr><tr><td>资源到期/证书到期</td><td>每月定期查看有效资源中是否存在证书到期、资源到期、提醒对应主管进行续认证或续面试申请。</td><td>质量经理</td><td>每月</td><td>iResouces</td></tr></table>"
    # html_table = "<table><tr><td>大类</td><td>分类</td><td>类别</td><td>具体内容</td><td>责任人</td><td>周期</td><td>输出件</td></tr><tr><td rowspan=\"5\"></td><td rowspan=\"2\">承诺书/双\n证管理</td><td>入职</td><td>入职人员要求在去项目学习前，完成承诺书手抄及上岗证考试。</td><td>文员/行政</td><td>按需</td><td>考试截图/承诺书扫描件</td></tr><tr><td>双证管理</td><td>上岗证、服务规范考试考试成绩截图及有证书有效期管理</td><td>文员/行政</td><td>每年</td><td>考试截图/承诺书扫描件</td></tr><tr><td rowspan=\"3\">涉A备件管理</td><td>涉A备件管理</td><td>统计归还的特定消耗备件，报备记录，销毁记录等。</td><td>质量经理</td><td>每周</td><td>涉A备件管理表</td></tr><tr><td>整改单备件管理</td><td>整改单备件申请、跟踪归还情况。</td><td>质量经理</td><td>每周</td><td>涉A备件管理表</td></tr><tr><td>无工单备件管理</td><td>查看无工单备件申请情况，跟踪归还情况。</td><td>质量经理</td><td>每周</td><td>涉A备件管理表</td></tr><tr><td rowspan=\"7\">培训</td><td rowspan=\"7\">流程学习材料</td><td>维护流程</td><td>维护流程指导材料</td><td>质量经理</td><td>季度</td><td>指导材料</td></tr><tr><td>设备健康检查</td><td>巡检流程指导材料</td><td>质量经理</td><td>季度</td><td>指导材料</td></tr><tr><td>变更流程</td><td>变更流程指导材料</td><td>安全员</td><td>季度</td><td>指导材料</td></tr><tr><td>新员工培训</td><td>新员工学习培训材料</td><td>行政/质量经理</td><td>季度</td><td>指导材料</td></tr><tr><td>部门培训</td><td>部门培训中需包含网络安全隐私保护、EHS等固定会议内容宣贯</td><td>产品线主管</td><td>月度</td><td>会议纪要</td></tr><tr><td>产品线技能培训</td><td>月度组织产品线人员进行技能培训，不限方式</td><td>产品线主管</td><td>月度</td><td>会议纪要</td></tr><tr><td>网络安全</td><td>网络安全培训、学习材料</td><td>区域主任/质量经理</td><td>季度</td><td>指导材料</td></tr><tr><td rowspan=\"7\">项目管理</td><td rowspan=\"7\">项目验收管理</td><td>验收报告真实性</td><td>完工证明、产品安装报告、高级服务交付报告、驻场交付报告等所有涉及客户签字的报告，质量自检报告，客户签字是否真实，有无PS等情况，不允许提前签署报告。</td><td>项目经理/质量经理</td><td>每天</td><td>验收真实性合规性检查</td></tr><tr><td>报告规范性</td><td>对所有报告的合规性、规范性进行检查</td><td>项目经理/质量经理</td><td>每天</td><td>验收真实性合规性检查</td></tr><tr><td>帐号密码移交</td><td>由最终客户签署的报告，需要单独和最终客户移交下帐号密码。</td><td>项目经理/质量经理</td><td>每天</td><td>验收真实性合规性检查</td></tr><tr><td>项目质量检查</td><td>现场抽查项目质量。</td><td>项目经理/质量经理</td><td>双周</td><td>质量检查报告</td></tr><tr><td>开工会议纪要</td><td>确认项目开工会议纪要是否发送及知会相关责任人</td><td>项目经理/质量经理</td><td>按需</td><td>开工会议纪要</td></tr><tr><td>项目验收项目访谈</td><td>项目完工前进行项目预回访</td><td>项目经理/质量经理</td><td>按需</td><td>回访记录表</td></tr><tr><td>项目转维</td><td>跟踪完工的项目，进行资料移交（邮件）</td><td>项目经理/质量经理</td><td>双周</td><td>移交证明</td></tr><tr><td rowspan=\"7\">质量管理</td><td rowspan=\"3\">现场抽查</td><td rowspan=\"3\">现场检查</td><td>现场检查网络安全</td><td>质量经理</td><td>月度</td><td>现场检查报告</td></tr><tr><td>现场检查变更流程规范</td><td>质量经理</td><td>月度</td><td>现场检查报告</td></tr><tr><td>现场检查维护流程规范</td><td>质量经理</td><td>月度</td><td>现场检查报告</td></tr><tr><td rowspan=\"2\">电话抽查</td><td rowspan=\"2\">电话抽查</td><td>电话抽查流程规范掌握情况</td><td>质量经理</td><td>月度</td><td>电话抽查检查表</td></tr><tr><td>远程参加培训人员抽查培训内容掌握。</td><td>质量经理</td><td>月度</td><td>电话抽查检查表</td></tr><tr><td rowspan=\"2\">固定动作</td><td>质量月报</td><td>质量月报输出</td><td>质量经理</td><td>月度</td><td>质量月报</td></tr><tr><td>能力提升月报</td><td>能力提升月报输出</td><td>质量经理</td><td>月度</td><td>能力提升月报</td></tr></table>"
    # 提取为数字键矩阵
    # matrix_res = html_to_extractor_result(html_table)
    # print(matrix_res)

    # 转换为字段名结构的 JSON
    # field_json = matrix_to_field_json(matrix_res)
    # print(field_json)
    # print("-" * 20)

    # 按照第一列分组
    # first_col_group = group_by_first_field(field_json)
    # print("分组数量 -->", len(first_col_group))
    # print(first_col_group)
    # print("-" * 20)

    # 根据分组构建线性化文本
    # linearize_group_text = linearize_grouped_data(first_col_group)
    # print("分组数量 -->", len(linearize_group_text))
    # print(linearize_group_text[0])
    # print(len(linearize_group_text[0]))
    # print("-" * 20)

    # 综合测试
    # results = html_to_structured_linear(html_table)
    # print(results)

    # result = html_to_all_outputs(html_table, caption="服务质量体系手册目录")
    # print(result)
    # print("-" * 20)
    # print(result['by_row'])
    # print("-" * 20)
    # print(result['by_section'])
    # print("-" * 20)

    # raw = extract_table_summary(html_table)
    # print(f"LLM 生成结果长度:{len(raw)}")
    # print("LLM 生成结果如下:")
    # print(raw)
    #
    # print("-" * 20)
    # cleaned_raw = _extract_json_array(raw)
    # print("清洗后的内容:")
    # print(type(cleaned_raw))
    # print(len(cleaned_raw))
    # print(type(cleaned_raw[0]))
    # print(cleaned_raw)

    escape_html = "&lt;html&gt;&lt;body&gt;&lt;table&gt;&lt;tr&gt;&lt;td&gt;序 号&lt;/td&gt;&lt;td&gt;关键事项&lt;/td&gt;&lt;td&gt;动作&lt;/td&gt;&lt;td&gt;描述&lt;/td&gt;&lt;td&gt;周期&lt;/td&gt;&lt;td&gt;责任人/ 部门&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;1&lt;/td&gt;&lt;td&gt;刷新ASP服 务规范要求&lt;/td&gt;&lt;td&gt;更新服务质量手册；变更要点 及时邮件通知和组织培训&lt;/td&gt;&lt;td&gt;公司服务质量手册版本刷新&lt;/td&gt;&lt;td&gt;年度&lt;/td&gt;&lt;td&gt;质量部&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;2&lt;/td&gt;&lt;td&gt;客户现场服 务质量检查&lt;/td&gt;&lt;td&gt;交付、维护、驻场场景进行质 量检查&lt;/td&gt;&lt;td&gt;现场检查工程师的工作纪 律，抽查服务意识，检查操作 是否规范，是否有网络安全 意识，了解客户的声音。&lt;/td&gt;&lt;td&gt;月度&lt;/td&gt;&lt;td&gt;质量经理&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;3&lt;/td&gt;&lt;td&gt;高危操作监 控&lt;/td&gt;&lt;td&gt;输出高危操作统计表，合规运 营周报&lt;/td&gt;&lt;td&gt;重点关注变更计划，流程规 范性和操作规范性&lt;/td&gt;&lt;td&gt;每工作日 /每周&lt;/td&gt;&lt;td&gt;质量经理&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;4&lt;/td&gt;&lt;td&gt;维护工单接 收与 SLA&lt;/td&gt;&lt;td&gt;NetCare 系统查看工单 SLA,及 备件申请情况&lt;/td&gt;&lt;td&gt;工单及时响应，派发后提醒 备件申请，每工作日提醒打 卡规范性&lt;/td&gt;&lt;td&gt;每工作日&lt;/td&gt;&lt;td&gt;维护经理&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;5&lt;/td&gt;&lt;td&gt;巡检工单统 计表&lt;/td&gt;&lt;td&gt;输出巡检进展表&lt;/td&gt;&lt;td&gt;监控巡检工单问题、过程及 完成计划&lt;/td&gt;&lt;td&gt;每双周&lt;/td&gt;&lt;td&gt;维护经理&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;6&lt;/td&gt;&lt;td&gt;客户满意度 评价管理&lt;/td&gt;&lt;td&gt;跟踪满意度评价&lt;/td&gt;&lt;td&gt;每周一对未评价的工单要求 工程师要请客户评价。&lt;/td&gt;&lt;td&gt;每周&lt;/td&gt;&lt;td&gt;文员&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;7&lt;/td&gt;&lt;td&gt;备件管理&lt;/td&gt;&lt;td&gt;输出备件统计表&lt;/td&gt;&lt;td&gt;1.监控备件归还，及时通知 相关工程师 2.特定备件收集与销毁;&lt;/td&gt;&lt;td&gt;每周&lt;/td&gt;&lt;td&gt;质量经理 工程文员&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;8&lt;/td&gt;&lt;td&gt;文档规范性 检查&lt;/td&gt;&lt;td&gt;检查文档规范性并对问题进 行通报&lt;/td&gt;&lt;td&gt;项目文档-工程文员检查 维护文档-维护经理检查 文档规范性-质量经理抽检&lt;/td&gt;&lt;td&gt;每周&lt;/td&gt;&lt;td&gt;（项目） 维护经理 （维护） 质量经理 （抽检）&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;9&lt;/td&gt;&lt;td&gt;驻场周报检 查&lt;/td&gt;&lt;td&gt;NetCare 系统检查周报&lt;/td&gt;&lt;td&gt;每周一中午检查驻场周报上 载情况 考勤打卡情况统计;&lt;/td&gt;&lt;td&gt;每周&lt;/td&gt;&lt;td&gt;驻场管理/ 质量经理&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;10&lt;/td&gt;&lt;td&gt;驻场考勤检 查&lt;/td&gt;&lt;td&gt;NetCare 考勤打卡检查 1.项目开工前期，现场督导&lt;/td&gt;&lt;td&gt;异常考勤跟踪处理 抽检交付质量，对不合格项&lt;/td&gt;&lt;td&gt;每周&lt;/td&gt;&lt;td&gt;驻场管理/ 质量经理&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;11&lt;/td&gt;&lt;td&gt;项目交付质 量抽检&lt;/td&gt;&lt;td&gt;2.完工项目抽检，通报抽检结 果&lt;/td&gt;&lt;td&gt;目进行整改(30%抽查率)，输 出质量检查报告&lt;/td&gt;&lt;td&gt;每月&lt;/td&gt;&lt;td&gt;质量经理/ 项目经理&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;&lt;/body&gt;&lt;/html&gt;"

    # 测试反向编码表格
    unescape_html = unescape_html_table(escape_html)
    print('unescape 反编码后的表格内容:')
    print(unescape_html)
