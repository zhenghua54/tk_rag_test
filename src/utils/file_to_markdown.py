import logging
import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# 导入其他模块
from codes.utils.office_to_markdown_langchain import process_file_to_md
from codes.utils.pdf_to_markdown import process_pdf
from codes.config import Config, get_doc_output_dir

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_file(config, file_path: str, doc_type: str = "auto") -> bool | str:
    """
    处理文档文件
    
    Args:
        file_path (str): 文件路径
        doc_type (str): 文档类型，可选值：auto, pdf, office
        
    Returns:
        bool: 处理是否成功
        :param config:
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    # 获取输出md文件路径和图片文件路径
    output_paths = get_doc_output_dir(config, file_path)

    # 获取文件扩展名
    file_ext = os.path.splitext(file_path)[1].lower()

    # 自动检测文件类型
    if doc_type == "auto":
        if file_ext in config.supported_file_types["pdf"]:
            doc_type = "pdf"
        elif file_ext in config.supported_file_types["office"]:
            doc_type = "office"
        else:
            logger.error(f"不支持的文件类型: {file_ext}")
            return False

    # 根据文件类型处理
    if doc_type == "pdf":
        logging.info(f"文件为 PDF-->")
        return process_pdf(config, file_path)
    elif doc_type == "office":
        logging.info(f"文件为 word/ppt-->")
        return process_file_to_md(file_path, output_paths['output_markdown_path'])
    else:
        logger.error(f"不支持的文档类型: {doc_type}")
        return False


if __name__ == "__main__":
    config = Config()

    # 示例：处理一个文件
    file_path = '/Users/jason/Library/Mobile Documents/com~apple~CloudDocs/PycharmProjects/tk_rag_demo/datas/origin_data/组织过程资产平台需求规格说明书.docx'
    success = process_file(config, file_path)

    if not success:
        logger.error("文件处理失败")
