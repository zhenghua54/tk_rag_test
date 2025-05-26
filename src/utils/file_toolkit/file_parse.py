"""
文档解析模块,目前使用 MinerU 工具进行解析
1. 根据 mysql 数据库的文件路径提取文件
2. 将所有文件使用 libreoffice 转换为 PDF 格式
3. 调用 MinerU 工具进行解析
4. 保存解析后的文件
5. 更新解析后的文件路径到 mysql 记录
"""

from src.api.mineru_parse import parse_pdf
from src.utils.common.logger import logger
from src.utils.database.file_db import update_parse_paths
from src.utils.common.pdf_validator import is_pdf_valid


def parse_pdf_file(pdf_paths: list[dict]) -> list[dict]:
    """使用 MinerU 解析 PDF 文件, 返回 markdown 和 json 文件的保存路径

    Args:
        pdf_paths (list[dict], optional): 文件的 PDF 地址列表。如果为 None, 则从数据库获取。

    Returns:
        list: 解析后的文件路径信息列表，每个元素包含 doc_id 和输出路径信息
    """

    output_paths = []

    if not pdf_paths:
        logger.info("没有需要解析的 PDF 文件")
        return output_paths

    # 先检查所有文件的合法性
    valid_pdf_paths = []
    for pdf_path in pdf_paths:
        try:
            is_valid, reason = is_pdf_valid(pdf_path['source_document_pdf_path'])
            
            if not is_valid:
                logger.error(f"文件 {pdf_path['source_document_name']} 不合法: {reason}")
                continue
                
            valid_pdf_paths.append(pdf_path)
            
        except Exception as e:
            logger.error(
                f"检查文件 {pdf_path.get('source_document_name', 'unknown')} 失败: {str(e)}"
            )
            continue
            
    logger.info(f"文件合法性检查完成: 通过 {len(valid_pdf_paths)} 个, 失败 {len(pdf_paths) - len(valid_pdf_paths)} 个")
    
    # 更新待解析文件列表
    pdf_paths = valid_pdf_paths

    logger.info(f"开始解析 {len(pdf_paths)} 个 PDF 文件")

    for pdf_path in pdf_paths:
        try:
            logger.info(f"正在解析文件: {pdf_path['source_document_name']}")
            
            output_path = parse_pdf(pdf_path['source_document_pdf_path'])
            if output_path:
                # 添加 doc_id 到输出路径信息中
                output_path['doc_id'] = pdf_path['doc_id']
                output_paths.append(output_path)
                logger.info(f"文件 {pdf_path['source_document_name']} 解析成功")
            else:
                logger.error(
                    f"文件 {pdf_path['source_document_name']} 解析失败: 未返回输出路径"
                )
        except Exception as e:
            logger.error(
                f"解析文件 {pdf_path.get('source_document_name', 'unknown')} 失败: {str(e)}"
            )
            continue

    logger.info(
        f"PDF 文件解析完成: 成功 {len(output_paths)} 个, 失败 {len(pdf_paths) - len(output_paths)} 个"
    )
    return output_paths


def update_parse_file_records_in_db(output_paths: list[dict] = None) -> None:
    """将解析后的文件路径信息保存至 Mysql 中

    Args:
        output_paths (list[dict], optional): 解析后的文件路径信息列表。如果为 None, 则先进行解析。
    """
    # 如果没有提供输出路径列表, 则先进行解析
    if output_paths is None:
        output_paths = parse_file_from_db()

    # 更新数据库
    success_count, fail_count = update_parse_paths(output_paths)

    if success_count > 0 or fail_count > 0:
        logger.info(f"文件路径更新完成: 成功 {success_count} 条, 失败 {fail_count} 条")


if __name__ == "__main__":
    update_parse_file_records_in_db()
