"""文件工具方法"""
import os

import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re

import fitz
import requests
import hashlib
import shutil
import subprocess
import tempfile

from pathlib import Path
from typing import Dict, Tuple, Optional, List, Union
# mineru 解析使用
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

from config.global_config import GlobalConfig
from error_codes import ErrorCode
from api.response import APIException
from utils.log_utils import logger, log_exception
from utils.llm_utils import llm_manager, render_prompt


# === 输出路径获取 ===
def get_doc_output_path(doc_path: str) -> dict:
    """
    获取文档的输出目录

    Args:
        doc_path (str): 源文档的路径

    Returns:
        dict: 包含以下字段的字典：
            - output_path (str): 该文档的输出根目录
            - output_image_path (str): markdown 的图片文件目录
    """
    doc_path = Path(doc_path)
    # 项目文件处理输出目录
    output_data_dir = Path(GlobalConfig.PATHS["processed_data"])

    # 根据文件名称,在输出目录下构建自己的输出子目录
    output_path = output_data_dir / doc_path.stem
    output_image_path = output_path / "images"

    return {
        "output_path": str(output_path),
        "output_image_path": str(output_image_path),
        "doc_name": doc_path.stem,
    }


# === 文档 ID 生成 ===
def generate_doc_id(doc_path: str, add_title: bool = True, algo: str = "sha256") -> str:
    """计算文件内容的哈希值

    Args:
        doc_path (str): 文件路径
        add_title (bool): 是否添加标题哈希值, 默认为 True（前期避免重复处理）
        algo (str): 哈希算法，默认为 "sha256"

    Returns:
        str: 文件的 SHA256 哈希值
    """
    hasher = hashlib.new(algo)
    with open(doc_path, "rb") as f:
        # 逐块读取文件内容（8K）以避免内存问题
        while chunk := f.read(8192):
            hasher.update(chunk)

    # 如果需要添加文件名到哈希计算中
    if add_title:
        doc_path = Path(doc_path)
        # 将文件名转换为字节并添加到哈希计算中
        hasher.update(str(doc_path.name).encode('utf-8'))

    return hasher.hexdigest()


# === 分块 ID 生成 ===
def generate_seg_id(content: str) -> str:
    """生成片段ID

    Args:
        content (str): 片段内容

    Returns:
        str: 片段ID（SHA256哈希值）
    """
    return hashlib.sha256(content.encode()).hexdigest()


# === 文本处理 ===
def truncate_text(text: str, max_length: int = None) -> str:
    """截断摘要文本，确保不超过最大长度

    Args:
        text: 原始文本
        max_length: 最大长度限制

    Returns:
        截断后的文本
    """
    if not text.strip():
        return ""
    if not max_length:
        max_length = GlobalConfig.SEGMENT_CONFIG.get("max_text_length")

    if len(text.strip()) <= max_length:
        return text
    # 在最大长度处截断，并添加省略号
    return text.strip()[:max_length - 3] + "..."


# === 文档删除 ===
def delete_local_file(file_path_list: List[str]) -> Optional[bool]:
    """删除本地文档和文件夹服务

    Args:
        file_path_list: 要删除的文档路径列表

    Returns:
        bool: 删除结果
    """
    total_num: int = len(file_path_list)

    if total_num == 0:
        logger.error(f"没有需要删除的文件/目录")
        return True

    try:
        logger.info(f"[文件删除] 开始, 文件数量={len(file_path_list)}")
        logger.debug(f"[文件删除] 文件清单: {file_path_list}")
        for file_path in file_path_list:
            logger.info(f"开始删除文件: {file_path}")
            if not file_path:
                logger.info(f"跳过删除, 路径不存在")
                total_num -= 1
                continue
            try:
                if not file_path or not isinstance(file_path, str):
                    logger.error(f"跳过删除, 路径格式非法, 需为字符串格式, 当前格式: {type(file_path)}")
                    total_num -= 1
                    continue
                path = Path(file_path)
                if not path.exists():
                    logger.warning(f"文件不存在")
                    total_num -= 1
                    continue
                if path.is_file():
                    path.unlink()
                    logger.info(f"文件删除成功")
                elif path.is_dir():
                    shutil.rmtree(path)
                    logger.info(f"文件删除成功")
            except OSError as e:
                log_exception("系统IO错误", e)
                raise ValueError(str(e)) from e
            except Exception as e:
                logger.error(f"文件删除失败, 失败原因: {str(e)}")
                raise ValueError(f"文件删除失败, 失败原因: {str(e)}") from e
        logger.info(f"本地文件删除完成, 删除数量: {total_num}")
        return True

    except Exception as e:
        logger.error(f"文档删除失败, 错误原因: {str(e)}")
        raise ValueError(f"文档删除失败, 错误原因: {str(e)}") from e


# === 下载 http 文档 ===
async def download_file_step_by_step(url: str, local_path: str = None, chunk_size: int = 8192):
    """逐步下载网络文档并保存为本地文件

    Args:
        url (str): 网络文档的 URL
        local_path (str): 本地保存路径
        chunk_size (int): 每次下载的字节数，默认 8KB

    Returns:
        local_path (str): 本地保存的文件路径
    """

    try:
        # 从 URL 中获取文件名
        file_name = url.split('/')[-1]
        if not file_name:
            raise APIException(ErrorCode.HTTP_FILE_NOT_FOUND, "无法从URL中获取文件名")

        # 设置本地保存路径
        if local_path is None:
            local_path = str(Path(GlobalConfig.PATHS["origin_data"]) / file_name)
        else:
            local_path = str(Path(local_path) / file_name)

        # 确保目录存在
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"开始下载文件: {url}")
        logger.debug(f"保存到本地路径: {local_path}")

        with requests.get(url, stream=True, timeout=10) as response:
            response.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:  # 过滤掉 keep-alive 块
                        f.write(chunk)
        logger.debug(f"文件下载完成，保存到: {local_path}")
        return local_path
    except Exception as e:
        raise APIException(ErrorCode.HTTP_FILE_NOT_FOUND, str(e)) from e


# === 文档名称非法字符处理 ===
def sanitize_doc_name(doc_name: str) -> str:
    """将文档名中不支持的字符替换为下划线"""
    chars = "".join(re.escape(ch) for ch in GlobalConfig.UNSUPPORTED_FILENAME_CHARS)
    pattern = f"[{chars}]"  # 构造类似于 [\\/:*?"<>|]
    return re.sub(pattern, "_", doc_name)


# === 表格内容解析 ===
def _clean_json_block(text: str) -> str:
    """去除 markdown 中的代码块标记，返回纯 JSON 字符串"""
    text = text.strip()
    text = re.sub(r'^```(json)?\n?', '', text)
    text = re.sub(r'\n?```$', '', text)
    return text


def _validate_summary_dict(data: Dict[str, str]) -> Dict[str, str]:
    """验证并清洗 JSON 对象的字段"""
    title = data.get("title", "").strip()
    summary = data.get("summary", "").strip()

    if not title or not summary:
        raise ValueError(f"缺失 title 或 summary 字段: {data}")
    return {"title": title, "summary": summary}


def parse_table_summary(value: str) -> Dict[str, str]:
    """解析并验证表格摘要内容
    Args:
        value: 模型输出的原始摘要文本
    Returns:
        Dict[str, str]: 包含 title 和 summary 的字典
    Raises:
        ValueError: 当摘要格式不正确时抛出
    """
    try:
        # 清理输入文本
        json_str = _clean_json_block(value)
        start = json_str.index('{')
        end = json_str.rindex('}')
        json_part = json_str[start:end + 1]
        parsed = json.loads(json_part)
        return _validate_summary_dict(parsed)
    except Exception as e:
        raise ValueError(f"[表格摘要解析失败] 输入内容: {value[:100]}..., 错误: {str(e)}")


# === 摘要生成 ===
def extract_table_summary(html: str) -> Dict[str, str]:
    """提取表格摘要， 调用LLM接口并解析输出
    Args:
        html: HTML 格式的表格
    Returns:
        Dict[str, str]: 包含 title 和 summary 的字典
    """
    # 获取提示词
    prompt, config = render_prompt("table_summary", {"table_html": html})
    system_prompt = "你是一个专业的数据分析师，擅长从表格中提取关键信息并生成摘要。"
    raw = llm_manager.invoke(prompt=prompt, temperature=config['temperature'], system_prompt=system_prompt,
                             max_tokens=config['max_tokens'], invoke_type="表格摘要生成")
    logger.debug(f"表格摘要生成成功: {raw[:100]}...")
    return parse_table_summary(raw)


def extract_text_summary(text: str) -> str:
    """提取文本摘要

    Args:
        text: 文本内容

    Returns:
        str: 文本摘要
    """
    # 加载提示词
    prompt, config = render_prompt("text_summary", {"content": text})
    system_prompt = "你是一个专业的文本分析师，擅长从文本中提取关键信息并生成摘要。请直接输出摘要内容，不要包含任何其他说明文字。"
    summary = llm_manager.invoke(prompt=prompt, temperature=config['temperature'], system_prompt=system_prompt,
                                 max_tokens=config['max_tokens'], invoke_type="文本摘要生成")
    logger.info(f"[文本摘要] 生成成功, 摘要长度={len(summary)}, {summary[:100]}...")
    return summary.strip()


# === 文档转换 ===
def _check_system_requirements() -> Tuple[bool, str]:
    """
    检查系统环境要求

    Returns:
        Tuple[bool, str]: (是否满足要求, 错误信息)
    """

    # 检查 LibreOffice 是否安装
    if not os.path.exists(GlobalConfig.PATHS["libreoffice_path"]):
        return False, f"LibreOffice 未安装或路径不正确: {GlobalConfig.PATHS['libreoffice_path']}"
    else:
        logger.debug(f"LibreOffice 已安装: {GlobalConfig.PATHS['libreoffice_path']}")

    # 检查中文字体
    try:
        # 检查高质量中文字体，优先使用思源系列字体
        chinese_fonts = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Noto Sans CJK
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",  # Noto Serif CJK
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # 备选路径
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",  # 备选路径
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # 文泉驿微米黑
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",  # 文泉驿正黑
        ]

        font_found = False
        found_font = None
        for font in chinese_fonts:
            if os.path.exists(font):
                font_found = True
                found_font = font
                break

        if not font_found:
            # 尝试使用 fc-list 命令检查字体
            try:
                result = subprocess.run(
                    ["fc-list", ":", "lang=zh"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    font_found = True
                    found_font = "通过 fc-list 检测到中文字体"
            except FileNotFoundError:
                pass

        if not font_found:
            return False, "未检测到中文字体，建议安装：\n" + \
                          "Ubuntu/Debian: sudo apt install fonts-noto-cjk\n" + \
                          "CentOS/RHEL: sudo yum install google-noto-cjk-fonts"
        else:
            logger.debug(f"已检测到中文字体: {found_font}")
        return True, ""

    except Exception as e:
        return False, f"检查系统环境时发生错误: {str(e)}"


def libreoffice_convert_toolkit(doc_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    使用 LibreOffice 将文件转换为 PDF 格式

    Args:
        doc_path (str): 输入文件的完整路径
        output_dir (str, optional): 输出目录路径。如果不指定，则使用输入文件所在目录

    Returns:
        str: 转换后的 PDF 文件路径，如果转换失败则返回 None

    Raises:
        FileNotFoundError: 当输入文件不存在时
        ValueError: 当输入文件格式不支持时
    """
    try:
        # 检查系统环境
        is_ready, error_msg = _check_system_requirements()
        if not is_ready:
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    except Exception as e:
        logger.error(f"Libreoffice 系统环境时发生错误: {str(e)}")
        raise ValueError(f"检查系统环境时发生错误: {str(e)}")

    try:
        office_doc_path = Path(doc_path)
        # 如果未指定输出目录，使用输入文件所在目录
        output_dir = output_dir or office_doc_path.parent
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 检查文件名非法字符并替换，避免libreoffice转换失败
        save_name = sanitize_doc_name(office_doc_path.stem)

        # 构建输出文件路径
        output_file = os.path.join(output_dir, f"{save_name}.pdf")
        logger.debug(f"输出文件路径: {output_file}")
    except Exception as e:
        logger.error(f"Libreoffice 转换路径构建失败: {str(e)}")
        raise ValueError(f"Libreoffice 转换路径构建失败: {str(e)}")

    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 复制文件到临时目录，使用英文文件名
            temp_input = os.path.join(temp_dir, f"input{office_doc_path.suffix}")
            shutil.copy2(office_doc_path, temp_input)
            logger.debug(f"创建临时文件: {temp_input}")

            # 构建 LibreOffice 命令
            cmd = [
                GlobalConfig.PATHS["libreoffice_path"],
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', temp_dir,
                temp_input
            ]
            logger.debug(f"执行命令: {' '.join(cmd)}")

            # 执行转换命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(os.environ, LANG='zh_CN.UTF-8')  # 设置环境变量确保中文支持
            )

            # 获取转换输出
            stdout, stderr = process.communicate()
            logger.debug(f"命令输出: {stdout.decode() if stdout else '无'}")
            if stderr:
                logger.error(f"命令错误输出: {stderr.decode()}")

            # 检查转换是否成功
            if process.returncode == 0:
                # 检查临时目录中的 PDF 文件
                temp_pdf = os.path.join(temp_dir, f"input.pdf")
                if os.path.exists(temp_pdf):
                    # 移动 PDF 文件到目标目录
                    shutil.move(temp_pdf, output_file)
                    logger.debug(f"文件 {os.path.basename(office_doc_path)} 转换成功，保存至: {output_file}")
                    return output_file
                else:
                    error_msg = f"转换命令成功但临时 PDF 文件不存在: {temp_pdf}"
                    logger.error(f"[转换失败]  error_code={ErrorCode.CONVERT_FAILED},error_msg={error_msg}")
                    raise APIException(ErrorCode.CONVERT_FAILED, error_msg)
            else:
                logger.error(
                    f"[转换失败] doc_path={str(office_doc_path.resolve())}, error_code={ErrorCode.CONVERT_FAILED}, error_msg={stderr.decode()}")
                raise APIException(ErrorCode.CONVERT_FAILED, stderr.decode())

    except Exception as e:
        logger.error(f"[转换失败] error_code={ErrorCode.CONVERT_FAILED},error_msg={str(e)}")
        raise APIException(ErrorCode.CONVERT_FAILED, str(e))


# === PDF 文档解析 ===
def mineru_toolkit(pdf_doc_path: str, output_dir: str, output_image_path: str, doc_name: str) -> Union[Dict, None]:
    """解析 PDF 文件, 返回 json 文件信息

    Args:
        pdf_doc_path: PDF 文件路径
        output_dir: 输出目录
        output_image_path: 图片保存目录
        doc_name: 文档名称

    Returns:
        dict:
            json_path (str): json 文件的保存路径
            spans_path (str): spans 文件保存路径
            layout_path (str): layout 文件保存路径
    """

    try:

        # 初始化数据写入器，用于保存图片和 Markdown 文件
        image_writer, md_writer = FileBasedDataWriter(output_image_path), FileBasedDataWriter(output_dir)

        # 读取 PDF 文件内容
        reader1 = FileBasedDataReader("")  # 初始化数据读取器
        pdf_bytes = reader1.read(pdf_doc_path)  # 读取 PDF 文件的字节内容

        # 创建数据集实例并进行文档分析
        ds = PymuDocDataset(pdf_bytes)  # 使用读取的 PDF 字节创建数据集实例

        # 根据文档分类结果选择处理方式
        if ds.classify() == SupportedPdfParseMethod.OCR:  # 如果文档需要 OCR 处理
            logger.info(f"文档需要 OCR 处理")
            infer_result = ds.apply(doc_analyze, ocr=True)  # 应用自定义模型进行 OCR 分析
            pipe_result = infer_result.pipe_ocr_mode(image_writer)  # 进行 OCR 模式下的管道处理
        else:
            logger.info(f"文档不需要 OCR 处理")
            infer_result = ds.apply(doc_analyze, ocr=False)  # 否则进行普通文本分析
            pipe_result = infer_result.pipe_txt_mode(image_writer)  # 进行文本模式下的管道处理

        #  绘制布局结果到 PDF 页面上
        layout_path = os.path.join(output_dir, f"{doc_name}_layout.pdf")
        pipe_result.draw_layout(layout_path)

        # 绘制跨度结果到 PDF 页面上（方便质检，排查文本丢失、行间公式未识别等问题）
        spans_path = os.path.join(output_dir, f"{doc_name}_spans.pdf")
        pipe_result.draw_span(spans_path)

        # 将内容列表保存为 JSON 文件
        json_path = os.path.join(output_dir, f"{doc_name}_mineru.json")
        pipe_result.dump_content_list(md_writer, json_path, output_image_path)

        logger.info(f"MinerU 解析完成, JSON 文件已保存至: {json_path}")
        results = {
            "json_path": json_path,
            "spans_path": spans_path,
            "layout_path": layout_path,
        }
        return results
    except Exception as e:
        logger.error(f"Mineru 解析文档失败, 错误原因: {str(e)}")
        raise ValueError(f"Mineru 解析文档失败, 错误原因: {str(e)}") from e


# === 文档分页切割 ===
def split_pdf_to_pages(input_path, output_dir) -> Optional[dict[str, str]]:
    """按页切割文档,返回保存的页面地址列表"""
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(input_path)
    result: dict[str, str] = {}
    try:
        logger.info(f"文档共 {len(doc)} 页, 切割为 PNG 图片中...")
        for page_num in range(len(doc)):
            # 保存为PDF
            # new_doc = fitz.open()
            # new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            # save_path: str = f"{output_dir}/page_{page_num + 1}.pdf"
            # new_doc.save(save_path)
            # result[str(page_num + 1)] = save_path

            # 保存为 PNG 图片
            # 获取页面
            page = doc.load_page(page_num)
            # 设置图片缩放比例（DPI），提高图片质量
            mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放，相当于 300 DPI

            # 将页面渲染为图片
            pix = page.get_pixmap(matrix=mat)

            # 保存图片为 PNG 格式
            save_path: str = f"{output_dir}/page_{page_num + 1}.png"
            pix.save(save_path)
            
            result[str(page_num + 1)] = save_path

            # 清理内存
            pix = None

        logger.info(f"文档切割完成, 共生成 {len(result)} 张PNG图片")
        return result
    except Exception as e:
        logger.error(f"文档切割失败, 失败原因: {str(e)}")
        raise ValueError(f"文档切割失败, 失败原因: {str(e)}") from e
    finally:
        # 确保文档关闭
        if doc:
            doc.close()


# === 文档删除 ===


if __name__ == '__main__':
    text = """
1. 复杂问题下只做RAG优化精度提升有限，是否引入微调？（包含您的问题1/2/4）

首先，我们天宽是有模型微调能力的，在PPT里确实没有过多强调，其实是包含在了RAG优化的不同阶段那张图里，如Embedding模型/Rerank模型/生成模型的微调。
其次，我们其实是会针对客户的具体情况去考虑是否一定需要做微调。因为微调需要一定的数据收集/时间及算力成本，我们会根据客户的预算情况、需求精度来多方面考虑是否只做RAG还是加入微调。在客户有预算，并且精度要求比较高的话，我们是可以做微调的，效果也肯定会比纯RAG要好。
---------------------------

2. 是否可以引入多模态检索，适配工业场景？（包含您的问题3）

可以的。我们之前其实有使用一些VL模型来处理复杂文档里的图像/表格解析，但确实比较专注于文本类检索的方向，没有过多地做视觉/图像/声音/多模态。像工业图纸、巡检影像这类的识别，我理解可能涉及到专业小模型的训练，这个我们之前确实接触不多。如果在这块能加入梁博您的专业能力，相信我们能在工业场景一起打造更好的方案。
---------------------------

3. 销售标准化ppt很难看到真实的业务场景。UX交付方式我们是否可以展开更深的讨论？

这个没问题的，给您发的这个ppt确实是一份标准的产品介绍ppt，没有过多地深入介绍场景如何结合以及具体交付的UX。这个我们可以先做用户调研，然后结合具体场景一起深入讨论，才能打造最适合的UX方式。
    """
    table_html = """
    <html><body><table><tr><td colspan="5">版本演进及版本与版本批次关系</td></tr><tr><td>大版本</td><td>版本/次</td><td>小版本</td><td>版本/次</td><td></td></tr><tr><td>V1. 0</td><td>A/1</td><td>V1. 1</td><td>A/2</td><td>：</td></tr><tr><td>V2. 0</td><td>B/1</td><td>V2. 1</td><td>B/2</td><td>：</td></tr><tr><td>V3. 0</td><td>C/1</td><td>V3. 1</td><td>C/2</td><td>：</td></tr><tr><td></td><td>：</td><td>…</td><td>：</td><td>：</td></tr></table></body></html>
    """

    # print("=== 测试文本摘要 ===")
    # text_summary = extract_text_summary(text)
    # print(f"文本摘要结果：\n{text_summary}\n")

    # print("=== 测试表格摘要 ===")
    # table_summary = extract_table_summary(table_html)
    # print(f"表格摘要结果：\n{json.dumps(table_summary, ensure_ascii=False, indent=2)}\n")
    # print(type(table_summary))
    # print(table_summary['title'])
    # print(table_summary['summary'])

    # input_path = "/home/wumingxing/tk_rag/datas/raw/天宽服务质量体系_第1部分_1-22.pdf"
    # output_path = "./output"
    #
    # split_pdf_to_pages(input_path,output_path)

    # === 测试路径获取 ===
    from rich import print

    doc_path = "/home/wumingxing/tk_rag/datas/raw/2025年公司规范管理守则.docx"
    output_path = get_doc_output_path(doc_path)
    print(output_path)
