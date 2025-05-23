"""
MinerU 官方 API 修改, 调整输出可选项和路径(备份)
"""
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze


from src.utils.common.logger import logger
from src.utils.pdf_valid import is_pdf_valid
from src.utils.document_path import get_doc_output_path


# args: 初始化参数
pdf_file_name = "/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业/客户资料/知识问答案例/企业标准（约2300条）/规章制度及设计、采购、产品标准等（约1500条）/QSG A0303008-2024 新界泵业应届大学生培养及管理办法.pdf"  # 替换为实际的 PDF 文件路径


valid_res, valid_content = is_pdf_valid(pdf_file_name)

if not valid_res:
    logger.error(f"文件 {pdf_file_name} 结构不合法, {valid_content}")
    exit()

output_path = get_doc_output_path(pdf_file_name)
output_path, output_image_path, doc_name = output_path["output_path"], output_path["output_image_path"], output_path["doc_name"]


# 初始化数据写入器，用于保存图片和 Markdown 文件
image_writer, md_writer = FileBasedDataWriter(output_image_path), FileBasedDataWriter(output_path)

# read bytes: 读取 PDF 文件内容
reader1 = FileBasedDataReader("")  # 初始化数据读取器
pdf_bytes = reader1.read(pdf_file_name)  # 读取 PDF 文件的字节内容

# proc: 创建数据集实例并进行文档分析
ds = PymuDocDataset(pdf_bytes)  # 使用读取的 PDF 字节创建数据集实例

# inference: 根据文档分类结果选择处理方式
if ds.classify() == SupportedPdfParseMethod.OCR:  # 如果文档需要 OCR 处理
    logger.info(f"文档需要 OCR 处理")
    infer_result = ds.apply(doc_analyze, ocr=True)  # 应用自定义模型进行 OCR 分析
    pipe_result = infer_result.pipe_ocr_mode(image_writer)  # 进行 OCR 模式下的管道处理
else:
    logger.info(f"文档不需要 OCR 处理")
    infer_result = ds.apply(doc_analyze, ocr=False)  # 否则进行普通文本分析
    pipe_result = infer_result.pipe_txt_mode(image_writer)  # 进行文本模式下的管道处理



# # draw model result on each page: 绘制模型结果到 PDF 页面上
# infer_result.draw_model(os.path.join(output_path, f"{doc_name}_model.pdf"))

# # get model inference result: 获取模型推理结果
# model_inference_result = infer_result.get_infer_res()

# # draw layout result on each page: 绘制布局结果到 PDF 页面上
# pipe_result.draw_layout(os.path.join(output_path, f"{doc_name}_layout.pdf"))

# # draw spans result on each page: 绘制跨度结果到 PDF 页面上
# pipe_result.draw_span(os.path.join(output_path, f"{doc_name}_spans.pdf"))

# get markdown content: 获取 Markdown 内容
md_content = pipe_result.get_markdown(output_image_path)

# dump markdown: 将 Markdown 内容保存到文件中
pipe_result.dump_md(md_writer, f"{doc_name}.md", output_image_path)

# get content list content: 获取内容列表
content_list_content = pipe_result.get_content_list(output_image_path)

# dump content list: 将内容列表保存为 JSON 文件
pipe_result.dump_content_list(md_writer, f"{doc_name}_content_list.json", output_image_path)

# # get middle json: 获取中间 JSON 数据
# middle_json_content = pipe_result.get_middle_json()

# # dump middle json: 将中间 JSON 数据保存到文件中
# pipe_result.dump_middle_json(md_writer, f'{doc_name}_middle.json')
