"""测试DOCX转PDF的脚本"""
import os
import sys
import docx
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def docx_to_pdf_python(docx_path, output_path):
    """
    使用Python库将DOCX转换为PDF
    
    Args:
        docx_path: DOCX文件路径
        output_path: PDF输出目录
        
    Returns:
        生成的PDF文件路径
    """
    try:
        print(f"尝试使用Python库将DOCX转换为PDF: {docx_path}")
        # 确保输出目录存在
        os.makedirs(output_path, exist_ok=True)
        
        # 构建输出文件路径
        docx_filename = Path(docx_path).stem
        pdf_path = os.path.join(output_path, f"{docx_filename}.pdf")
        
        # 读取DOCX文件
        doc = docx.Document(docx_path)
        
        # 创建PDF文档
        pdf = SimpleDocTemplate(pdf_path, pagesize=letter)
        styles = getSampleStyleSheet()
        flowables = []
        
        # 处理文档内容
        for para in doc.paragraphs:
            if para.text:
                p = Paragraph(para.text, styles['Normal'])
                flowables.append(p)
                flowables.append(Spacer(1, 12))
        
        # 构建PDF
        pdf.build(flowables)
        
        print(f"使用Python库成功将DOCX转换为PDF: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"使用Python库转换DOCX到PDF失败: {str(e)}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_docx_convert.py <docx文件路径> [输出目录]")
        sys.exit(1)
    
    docx_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp"
    
    try:
        pdf_path = docx_to_pdf_python(docx_path, output_dir)
        print(f"转换成功，输出文件: {pdf_path}")
    except Exception as e:
        print(f"转换失败: {str(e)}")
        sys.exit(1) 