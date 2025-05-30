import sys
import os
import json
from typing import Any
from rich import print

root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)

from config.settings import Config
from src.core.document.pdf_parser import parse_pdf_file, parse_office_file
from src.utils.common.logger import logger
from src.utils.file.file_toolkit import compute_file_hash
from src.database.mysql.operations import FileInfoOperation
from src.core.document.processor import process_json_file
from src.utils.text.text_process import merge_page_content
from src.core.llm.extract_summary import extract_table_summary


def process_document(file_path: str) -> dict[str, Any] | None:
    """处理文档主流程
    
    1. 获取文件后缀, 根据文件类型进行转换并解析，更新到数据库
    2. 清洗 json 文件信息, 对表格\图片等内容进行处理
    3. 进行分块\嵌入,分别保存到 mysql 和 milvus 中
    
    Args:
        file_path: 文件路径
        
    Returns:
        处理结果字典
    """
    # 判断文件是否存在
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return None

    # ====== 文件初始化：转换 + 解析 ======
    # 计算文件 doc_id
    doc_id = compute_file_hash(file_path)

    # 检查文件是否已存在于数据库中
    with FileInfoOperation() as f:
        select_res = f.get_file_by_doc_id(doc_id)
        if select_res['source_document_json_path']:
            logger.info(f"该文件已存在 JSON 格式，路径：{select_res['source_document_json_path']}")
            # 直接使用已存在的 JSON 文件进行清洗
            path_info = {
                "json_path": select_res['source_document_json_path'],
                "doc_name": select_res['source_document_name']
            }
        else:
            # 获取文档后缀
            file_ext = os.path.splitext(file_path)[1]

            # 根据文档类型进行转换并解析
            if file_ext == '.pdf':
                pdf_path = file_path
            elif file_ext in Config.SUPPORTED_FILE_TYPES["libreoffice"]:
                # 转换文件为 PDF 格式
                pdf_path = parse_office_file(file_path)
                if not pdf_path:
                    logger.error(f"未获取到转换后的 PDF 文件: {file_path}")
                    return None
            else:
                logger.error(f"暂不支持该格式文件,目前支持的格式为: {Config.SUPPORTED_FILE_TYPES['all']}")
                return None

            # 解析 PDF 文件
            path_info = parse_pdf_file(pdf_path)

            # 格式化参数
            values = {
                "doc_id": doc_id,  # 文档唯一标识
                "source_document_name": path_info["doc_name"],  # 文档名称
                "source_document_type": file_ext,  # 文档类型
                "source_document_path": os.path.abspath(file_path),  # 文档原始路径
                "source_document_pdf_path": pdf_path,  # PDF 文件路径
                "source_document_json_path": path_info["json_path"],  # 文档 JSON 文件路径
                "source_document_images_path": path_info["image_path"],  # 文档图片路径
            }
            # 更新 mysql-file_info 表信息
            with FileInfoOperation() as f:
                f.insert_file_info(values)

    # ====== 清洗 JSON 文件信息：处理表格\图片等内容 ======
    # 处理表格和图片标题
    content_list = process_json_file(path_info["json_path"])
    if not content_list:
        logger.error(f"处理表格和图片标题失败: {path_info['json_path']}")

    # ====== 分块\嵌入：保存到 mysql 和 milvus 中 ======
    # 先按页聚合
    content_dict = merge_page_content(content_list)
    # 保存处理后的 json 文件
    save_file_path = os.path.join(os.path.abspath(path_info["json_path"]), f"{path_info['doc_name']}.processed_content.json")
    with open(save_file_path,'w', encoding='utf-8') as f:
        json.dump(content_dict, f, ensure_ascii=False, indent=4)

    # 再按页面分块


if __name__ == "__main__":
    # 测试代码
    test_file_path = "/home/wumingxing/tk_rag/datas/raw/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225.pdf"  # 替换为实际的测试文件路径
    # test_file_path = "/home/wumingxing/tk_rag/datas/raw/1_1_竞争情况（天宽科技）.docx"  # 替换为实际的测试文件路径
    process_document(test_file_path)

    # # 使用上下文管理器
    # with FileInfoOperation() as file_op:
    #     # 查询文件
    #     file_info = file_op.get_file_by_doc_id("215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83")
    #
    #     # 更新文件
    #     file_op.update_by_doc_id("215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83",
    #                              {"source_document_type": ".pdf"})
    #
    #     # 删除文件
    #     file_op.delete_by_doc_id("f10e704816fda7c6cbf1d7f4aebc98a6ac1bfbe0602e0951af81277876adbcbc")

    # 测试摘要提取
    # table_html = "\n\n<html><body><table><tr><td>大类</td><td>类别</td><td>具体内容</td><td>责任人</td><td>周期</td><td>输出件</td></tr><tr><td rowspan=\"6\">变更监控</td><td>方案审批</td><td>审批过程中查看相关的工单类型、操作类型、风险等级是否符合实际场景，八要素是否完整、步骤 清晰</td><td>区域业务TD</td><td>按需</td><td>在线评审</td></tr><tr><td>履行确认</td><td>每天10点导出当天至第二天上午前的变更，确认是否正常履行，取消或延期提前修改时间或取消</td><td>区域网络安全专员</td><td>每天</td><td>变更监控群提醒</td></tr><tr><td>授权完整</td><td>三授权是否完整，操作时间是否在授权时间内，授权获取时间是否在授权开始时间前，二次授权获 取是否及时</td><td>区域网络安全专员</td><td>每天</td><td>质量考核记录表</td></tr><tr><td>操作知会</td><td>变更开始及完成是否在交付群发送知会</td><td>区域网络安全专员</td><td>按需</td><td>质量考核记录表</td></tr><tr><td>工单闭环</td><td>跟踪已经完成的工单，提醒工程师及时闭环</td><td>区域维护经理/质量经理</td><td>按需</td><td></td></tr><tr><td>人员资质</td><td>派单前审视人员技能等级、产品归类等，确保不出现跨产品、技能不符履行工单</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td rowspan=\"5\">WO工单</td><td>SLA</td><td>每天跟踪当天需要上门的工单，要求到达时间前1小时还未打卡，电话提醒工程师</td><td>质量经理</td><td>按需</td><td></td></tr><tr><td>合规运营</td><td>合规履行指标项审核</td><td>质量经理</td><td>每天</td><td>微信提醒，质量考核记录 表</td></tr><tr><td>单次人天</td><td>打卡日期满足配额，提前提醒工程师打卡规则</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td>单次人天</td><td>日报发送规范检查、关单附件审核 每天查看已完成未闭环的整改工单，提醒工程师尽快上传材料审核是否都已创建变更单，如无需提</td><td>质量经理</td><td>按需</td><td></td></tr><tr><td>整改</td><td>供备案凭证</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td></td><td>设备健康检查</td><td>每天查看已完成未闭环的巡检工单，提醒工程师尽快上传材料审核，验收及实际履行的条目是否- 致，未巡检的设备不要出现在验收中。</td><td>质量经理</td><td>每天</td><td></td></tr><tr><td rowspan=\"5\">驻场管理</td><td>WO工单 出入场安全检查</td><td>日报发送规范检查、关单附件、合规性审核</td><td>质量经理</td><td>每天</td><td>异常输出质量考核记录表</td></tr><tr><td>背景调查</td><td>出入场签署安全检查 入场前完成背景调查</td><td>驻场主管/质量经理 HR/驻场主管</td><td>按需 按需</td><td>员工入场安全检查表 背景调查报告</td></tr><tr><td>客户授权</td><td>入场签署长期授权，保证在驻场期间，一直有授权</td><td>驻场主管/质量经理</td><td>按需</td><td>驻场授权电子件、短信授</td></tr><tr><td>电子围栏</td><td>入场前设置电子围栏，电子围栏需要是客户局点地址，每月审视所有驻场电子围栏合理性</td><td>驻场主管</td><td>按需</td><td>权</td></tr><tr><td>入场管理</td><td>提交入场电子流</td><td>驻场主管</td><td>按需</td><td>系统提交电子流 系统提交电子流</td></tr></table></body></html>\n\n"
    # summary = extract_table_summary(table_html)
