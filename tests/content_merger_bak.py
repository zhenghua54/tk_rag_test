# """处理文档内容, 包括表格、图片、文本等"""
# import json
# import os
# import tempfile
# import traceback
# import time
# from collections import defaultdict
#
# from pathlib import Path
#
# from src.api.error_codes import ErrorCode
# from src.api.response import APIException
# from src.core.doc.doc_convert import convert_office_file
# from src.core.doc.doc_parser import mineru_toolkit
# from src.database.mysql.operations import FileInfoOperation
# from src.utils.validator.content_validator import ContentValidator
# from src.utils.validator.file_validator import FileValidator
#
# from src.utils.common.logger import log_operation_success, log_operation_start, log_operation_error,logger
# from src.utils.validator.args_validator import ArgsValidator
# from src.core.llm.extract_summary import extract_table_summary
# from src.utils.table_toolkit import html_table_to_markdown
#
# def fill_title(json_doc_path: str) -> list:
#     """处理 JSON 文件中的表格和图片标题
#
#     Args:
#         json_doc_path (str): MinerU 解析后的 json 文件
#
#     Returns:
#         list: 处理后的文档内容列表
#     """
#
#     # 统计信息初始化
#     table_total, table_cap, table_cap_up, table_cap_miss = 0, 0, 0, 0
#     img_total, img_cap, img_cap_up, img_cap_miss = 0, 0, 0, 0
#
#     try:
#         # 读取json文件
#         with open(json_doc_path, "r", encoding="utf-8") as json_f:
#             json_content = json.load(json_f)
#     except Exception as e:
#         log_operation_error(operation="文件读取", error_code=ErrorCode.FILE_READ_FAILED.value, error_msg=str(e),
#                             doc_path={json_doc_path})
#         raise APIException(ErrorCode.FILE_READ_FAILED, f"读取 JSON 文件失败: {str(e)}") from e
#
#     try:
#         # 更新表格的标题信息
#         for idx, item in enumerate(json_content):
#             caption = None  # 初始化标题
#             last_item = json_content[idx - 1] if idx > 0 else None  # 指定上一个元素
#
#             # 提取表格元素
#             if item["type"] == "table":
#                 table_total += 1
#
#                 # 处理列表标题为字符串
#                 item["table_caption"] = "".join(item["table_caption"]) if isinstance(item["table_caption"], list) else \
#                     item[
#                         "table_caption"]
#
#                 # 通过 LLM 提取摘要信息（标题 + 内容摘要）
#                 markdown_table = html_table_to_markdown(item["table_body"])
#                 table_summary = extract_table_summary(markdown_table)
#
#                 # 更新内容摘要
#                 item["summary"] = table_summary["summary"]
#
#                 # 有标题
#                 if item["table_caption"].strip():
#                     table_cap += 1
#
#                 # 没有标题
#                 else:
#                     # 使用上个表格的标题
#                     if last_item and last_item["type"] == "table":
#                         caption = str(last_item.get("table_caption", "")[0]).strip()
#                     # 使用上一个文本作为标题（短文本）
#                     elif last_item and last_item["type"] == "content" and len(last_item["content"]) < 100:
#                         caption = str(last_item.get("content", "")).strip()
#                     else:
#                         # 使用 LLM 生成的标题
#                         caption = table_summary["title"].strip()
#
#                     # 如果提取到标题进行更新
#                     if caption:
#                         # 处理列表作为标题的异常情况
#                         item["table_caption"] = "".join(caption).strip() if isinstance(caption, list) else caption
#                         table_cap_up += 1
#                     else:
#                         table_cap_miss += 1
#
#             # 处理图片标题
#             if item["type"] == "image":
#                 img_total += 1
#
#                 # 处理标题为字符串
#                 item["img_caption"] = ", ".join(item["img_caption"]) if isinstance(item["img_caption"], list) else item[
#                     "img_caption"]
#
#                 # 如果图片标题存在
#                 if item["img_caption"].strip():
#                     img_cap += 1
#                 else:
#                     # 使用上一个文本作为标题（短文本）
#                     if last_item and last_item["type"] == "content" and len(last_item["content"]) < 100:
#                         caption = str(last_item.get("content", "")).strip()
#
#                     if caption:
#                         # 处理列表作为标题的异常情况
#                         item["img_caption"] = "".join(caption).strip() if isinstance(caption, list) else caption
#                         img_cap_up += 1
#                     else:
#                         img_cap_miss += 1
#
#         # 输出统计信息
#         log_operation_success("标题更新", start_time=time.time(), msg=
#         f"图片标题处理完成: {img_total} 张, 无需更新: {img_cap}, 已更新: {img_cap_up}, 缺少标题: {img_cap_miss} | "
#         f"表格标题处理完成: {table_total} 张, 已有标题: {table_cap}, 已更新: {table_cap_up}, 缺少标题: {table_cap_miss}"
#                               )
#         return json_content
#
#     except Exception as e:
#         raise APIException(ErrorCode.FILE_EXCEPTION, f"文档内容标题处理失败: {str(e)}") from e
#
#
# def merge_page_for_idx(json_doc_content: list):
#     """解析 json 内容, 根据 page_idx 合并 content 元素
#
#     Args:
#         json_doc_content (list): 处理后的 json 内容列表(MinerU -> 完善表格/图片标题)
#
#     Returns:
#         merge_page_contents (dict): 按照 page_idx 进行合并的 json 内容, 格式为 {page_idx:[content,content,content], ...}
#     """
#
#     try:
#         ContentValidator.validate_json_file(json_doc_content)
#     except json.JSONDecodeError as e:
#         raise APIException(ErrorCode.FILE_EXCEPTION, f"JSON 解析错误: {str(e)}")
#     except Exception as e:
#         log_operation_error("文件读取", error_code=ErrorCode.FILE_READ_FAILED.value, error_msg=str(e),
#                             doc_path={json_doc_content})
#         raise APIException(ErrorCode.FILE_EXCEPTION, str(e)) from e
#
#     try:
#         temp_dir = tempfile.TemporaryDirectory()  # 创建临时目录
#         page_files = defaultdict(list)  # 初始化页面存储
#         text_list = []  # 临时存储文本段
#         tmp_idx = None  # 当前页码缓存
#
#         log_operation_start("开始按页合并文档...")
#
#         for content in json_content:
#             # 获取当前页码
#             page_idx = content["page_idx"]
#
#             if tmp_idx is not None and page_idx != tmp_idx:
#                 logger.debug("翻页, 处理上一个内容页内容...")
#                 if text_list:
#                     page_files[tmp_idx].append({
#                         "type": "content",
#                         "content": "".join(text_list),
#                         "page_idx": tmp_idx
#                     })
#                     text_list = []
#                 # 保存当前页内容
#                 with open(f"{temp_dir.name}/page_{tmp_idx}.jsonl", "a", encoding="utf-8") as f:
#                     # 获取已合并完的页面内容
#                     for item in page_files[tmp_idx]:
#                         f.write(json.dumps(item, ensure_ascii=False) + "\n")
#                 # 清空已保存的页面内容
#                 page_files[tmp_idx] = []
#
#             # 更新当前页码
#             tmp_idx = page_idx
#             logger.debug(f"合并第 {tmp_idx} 页内容...")
#
#             # 处理同页内容
#             if content["type"] == "content":
#                 text_list.append(content["content"])
#             # 非文本类型，保存积累的文本后保存该元素
#             else:
#                 if text_list:
#                     page_files[page_idx].append({
#                         "type": "content",
#                         "content": "".join(text_list),
#                         "page_idx": page_idx
#                     })
#                     text_list = []
#                 page_files[page_idx].append(content)
#
#         # 处理最后一页累积的文本
#         if text_list:
#             logger.debug("处理最后一页遗留内容...")
#             page_files[tmp_idx].append({
#                 "type": "content",
#                 "content": "".join(text_list),
#                 "page_idx": tmp_idx
#             })
#         if tmp_idx is not None and page_files.get(tmp_idx):
#             with open(f"{temp_dir.name}/page_{tmp_idx}.jsonl", "a", encoding="utf-8") as f:
#                 # 获取最后一页的内容
#                 for item in page_files[tmp_idx]:
#                     f.write(json.dumps(item, ensure_ascii=False) + "\n")
#
#         # 汇总所有页
#         logger.debug("开始汇总所有页内容...")
#         result = defaultdict(list)
#         for f_name in os.listdir(temp_dir.name):
#             # 提取缓存文件的名称中的页码
#             page_idx = int(f_name.split('_')[1].split('.')[0])
#             with open(f"{temp_dir.name}/{f_name}", "r", encoding="utf-8") as f:
#                 for line in f:
#                     result[page_idx].append(json.loads(line))
#
#         logger.debug("所有页内容汇总完成, 开始保存合并后的内容...")
#         save_path = json_doc_content.parent / f"{json_content}_merged.json"
#         with open(save_path, "w", encoding="utf-8") as f:
#             json.dump(result, f, ensure_ascii=False, indent=2)
#         logger.debug(f"合并后的文档内容已保存到: {save_path}")
#
#         return save_path
#
#     except Exception as e:
#         raise APIException(ErrorCode.FILE_EXCEPTION, f"文档内容合并失败: {str(e)}") from e
#
#
# # 入口函数(后台处理)
# def process_doc_content(doc_path: str, doc_id: str = None) -> str:
#     """处理文档内容:
#     1. 非PDF文件先转换为PDF
#     2. 使用MinerU解析 PDF 文档
#     3. 填充表格和图片标题, 并按页合并内容, 写入json文件, 命名为 {json_doc_path}_merged.json
#     4. 如果提供了 doc_id，则更新数据库中的处理状态
#
#     Args:
#         doc_path (str): 源文档路径
#         doc_id (str, optional): 文档ID，如果提供则会更新数据库状态
#
#     Returns:
#         save_path (str): 处理后的文档路径
#     """
#     try:
#         if doc_id:
#             log_operation_start("处理文档",
#                                 doc_id=doc_id)
#
#         # 验证参数
#         ArgsValidator.validate_type(doc_path, str, "pdf_doc_path")  # 参数类型验证
#         FileValidator.validate_local_filepath_exist(doc_path)  # 文件路径验证
#         FileValidator.validate_file_convert_ext(doc_path)
#
#         doc_path = Path(doc_path)
#         # 非PDF文件先转换
#         pdf_path = convert_office_file(str(doc_path.resolve())) if doc_path.suffix != '.pdf' else str(doc_path)
#
#         ContentValidator.validate_pdf_content_parse(pdf_path)  # 验证 PDF 文档内容解析
#
#         # 使用MinerU 解析 PDF 文档
#         try:
#             out_info = mineru_toolkit(pdf_path)
#             if os.path.exists(out_info["json_path"]):
#                 log_operation_success("MinerU 解析完成",
#                                       start_time=time.time(),
#                                       doc_id=doc_id,
#                                       save_path=out_info["json_path"])
#                 values = {
#                     "doc_json_path": out_info["json_path"],
#                     "doc_images_path": out_info["image_path"],
#                     "doc_pdf_path": pdf_path,
#                     "process_status": "parsed"
#                 }
#                 with FileInfoOperation() as file_op:
#                     file_op.update_by_doc_id(doc_id, values)
#                 log_operation_success("数据库文件状态更新",
#                                       start_time=time.time(),
#                                       doc_id=doc_id,
#                                       status="-> parsed")
#             else:
#                 log_operation_error("MinerU 解析失败",
#                                     error_msg=traceback.format_exc(),
#                                     doc_id=doc_id)
#                 with FileInfoOperation() as file_op:
#                     values = {
#                         "process_status": "parse_failed"
#                     }
#                     file_op.update_by_doc_id(doc_id, values)
#                 log_operation_error("数据库文件状态更新",
#                                     doc_id=doc_id,
#                                     status="-> parse_failed")
#         except Exception as e:
#             log_operation_error("MinerU 解析失败",
#                                 error_msg=str(e),
#                                 doc_id=doc_id,
#                                 pdf_path=pdf_path)
#             with FileInfoOperation() as file_op:
#                 values = {
#                     "process_status": "parse_failed"
#                 }
#                 file_op.update_by_doc_id(doc_id, values)
#                 log_operation_error("数据库文件状态更新",
#                                     doc_id=doc_id,
#                                     status="-> parse_failed")
#             raise
#
#         # try:
#         #     # 填充表格和图片标题
#         #     log_operation_start("标题完善",
#         #                         start_time=time.time(),
#         #                         doc_id=doc_id,
#         #                         json_path=out_info["json_path"],
#         #                         )
#         #     json_content = fill_title(out_info["json_path"])
#         #     log_operation_success("标题完善",
#         #                           start_time=time.time())
#         # except Exception as e:
#         #     log_operation_error("填充表格和图片标题失败",
#         #                         error_msg=str(e),
#         #                         doc_id=doc_id,
#         #                         json_path=out_info["json_path"])
#         #     raise e
#
#
#         try:
#             # 合并页面内容
#             log_operation_start("合并页面内容",
#                                 start_time=time.time(),
#                                 doc_id=doc_id,
#                                 json_path=out_info["json_path"],
#                                 )
#             save_path = process_doc_by_page(out_info["json_path"])
#             log_operation_success("合并完成",
#                                   start_time=time.time(),
#                                   save_path=save_path)
#
#             # 如果提供了 doc_id，更新数据库状态
#             if doc_id:
#                 log_operation_success("文档处理完成",
#                                       start_time=time.time(),
#                                       doc_id=doc_id,
#                                       save_path=save_path)
#                 with FileInfoOperation() as file_op:
#                     values = {
#                         "doc_process_path": save_path,
#                         "process_status": "merged"
#                     }
#                     file_op.update_by_doc_id(doc_id, values)
#
#             return save_path
#         except Exception as e:
#             log_operation_error("合并页面内容失败",
#                                 error_msg=str(e),
#                                 doc_id=doc_id)
#             with FileInfoOperation() as file_op:
#                 values = {
#                     "process_status": "merge_failed"
#                 }
#                 file_op.update_by_doc_id(doc_id, values)
#                 log_operation_error("数据库文件状态更新",
#                                     doc_id=doc_id,
#                                     status="-> merge_failed")
#             raise
#
#     except Exception as e:
#         if doc_id:
#             log_operation_error("文档处理失败",
#                                 error_msg=str(e),
#                                 doc_id=doc_id)
#             # 记录详细的错误堆栈
#             log_operation_error("错误详情",
#                                 error_msg=traceback.format_exc(),
#                                 doc_id=doc_id)
#
#         raise
#
#
# if __name__ == '__main__':
#     pass
