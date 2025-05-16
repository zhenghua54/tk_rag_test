"""MinerU 官方 API"""

import os

from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

# args: 初始化参数
pdf_file_name = "/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业/客户资料/知识问答案例/企业标准（约2300条）/规章制度及设计、采购、产品标准等（约1500条）/QSG A0303008-2024 新界泵业应届大学生培养及管理办法.pdf"  # 替换为实际的 PDF 文件路径
name_without_suff = pdf_file_name.split(".")[0]  # 获取文件名（不带后缀）

# prepare env: 准备输出目录环境
local_image_dir, local_md_dir = "output/images", "output"  # 定义本地图片和 Markdown 文件的存储路径
image_dir = str(os.path.basename(local_image_dir))  # 获取图片目录的名称

os.makedirs(local_image_dir, exist_ok=True)  # 确保图片输出目录存在

print(image_dir)
print(local_image_dir)
print(local_md_dir)
exit()

# 初始化数据写入器，用于保存图片和 Markdown 文件
image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)

# read bytes: 读取 PDF 文件内容
reader1 = FileBasedDataReader("")  # 初始化数据读取器
pdf_bytes = reader1.read(pdf_file_name)  # 读取 PDF 文件的字节内容

# proc: 创建数据集实例并进行文档分析
ds = PymuDocDataset(pdf_bytes)  # 使用读取的 PDF 字节创建数据集实例

# inference: 根据文档分类结果选择处理方式
if ds.classify() == SupportedPdfParseMethod.OCR:  # 如果文档需要 OCR 处理
    infer_result = ds.apply(doc_analyze, ocr=True)  # 应用自定义模型进行 OCR 分析
    pipe_result = infer_result.pipe_ocr_mode(image_writer)  # 进行 OCR 模式下的管道处理
else:
    infer_result = ds.apply(doc_analyze, ocr=False)  # 否则进行普通文本分析
    pipe_result = infer_result.pipe_txt_mode(image_writer)  # 进行文本模式下的管道处理

# draw model result on each page: 绘制模型结果到 PDF 页面上
infer_result.draw_model(os.path.join(local_md_dir, f"{name_without_suff}_model.pdf"))

# get model inference result: 获取模型推理结果
model_inference_result = infer_result.get_infer_res()

# draw layout result on each page: 绘制布局结果到 PDF 页面上
pipe_result.draw_layout(os.path.join(local_md_dir, f"{name_without_suff}_layout.pdf"))

# draw spans result on each page: 绘制跨度结果到 PDF 页面上
pipe_result.draw_span(os.path.join(local_md_dir, f"{name_without_suff}_spans.pdf"))

# get markdown content: 获取 Markdown 内容
md_content = pipe_result.get_markdown(image_dir)

# dump markdown: 将 Markdown 内容保存到文件中
pipe_result.dump_md(md_writer, f"{name_without_suff}.md", image_dir)

# get content list content: 获取内容列表
content_list_content = pipe_result.get_content_list(image_dir)

# dump content list: 将内容列表保存为 JSON 文件
pipe_result.dump_content_list(md_writer, f"{name_without_suff}_content_list.json", image_dir)

# get middle json: 获取中间 JSON 数据
middle_json_content = pipe_result.get_middle_json()

# dump middle json: 将中间 JSON 数据保存到文件中
pipe_result.dump_middle_json(md_writer, f'{name_without_suff}_middle.json')
