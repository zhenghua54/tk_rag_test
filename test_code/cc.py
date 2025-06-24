# data_list = [
#     {"id": 1, "name": "Alice", "age": 25},
#     {"id": 2, "name": "Bob", "age": 30},
#     {"id": 3, "name": "Charlie", "age": 22}
# ]
#
# print(data_list[0].keys())

# a_path = "./cc.py"
# abs_path = "/home/jason/tk_rag/tests_code/cc.py"
# abs_dir = "/home/jason/tk_rag/utils"
# from pathlib import Path
# a_path = Path(a_path)
# abs_path = Path(abs_path)
# abs_dir = Path(abs_dir)
# # print("a_path.stem-->",a_path.stem) # cc
# # print("a_path.stem.type-->",type(a_path.stem)) # <class 'str'>
# # print("a_path.suffix -->",a_path.suffix)    # .py
# # print("a_path.suffix.type -->",type(a_path.suffix))    # <class 'str'>
# # print("a_path.stat() --> ", a_path.stat())  # os.stat_result(st_mode=33188, st_ino=139179, st_dev=2080, st_nlink=1, st_uid=1000, st_gid=1000, st_size=611, st_atime=1749389037, st_mtime=1749389037, st_ctime=1749389037)
# # print("a_path.stat().st_size --> ", a_path.stat().st_size)  # 611
# # print("a_path.stat().st_size.type --> ", type(a_path.stat().st_size))  # <class 'int'>
# # print("a_path.resolve() --> ", a_path.resolve())    #  /home/jason/tk_rag/tests_code/cc.py
# # print("a_path.resolve().type --> ", type(a_path.resolve()))    # <class 'pathlib.PosixPath'>
# # print("a_path.parent --> ", a_path.parent)  # /home/jason/tk_rag/tests_code
# # print("a_path.parent.type --> ", type(a_path.parent))  # <class 'pathlib.PosixPath'>
# # print("a_path.name --> ", a_path.name)  # cc.py
# # print("a_path.name.type --> ", type(a_path.name))  # <class 'str'>
# # print("a_path.absolute() --> ", a_path.absolute())  # /home/jason/tk_rag/tests_code/cc.py
# # print("a_path.absolute().type --> ", type(a_path.absolute()))  # <class 'pathlib.PosixPath'>
# # print("a_path.is_absolute() --> ", a_path.is_absolute())    # False
# # print("a_path.is_absolute().type --> ", type(a_path.is_absolute()))    # <class 'bool'>
# # print("abs_path.is_absolute() --> ", abs_path.is_absolute())    # True
# # print("abs_path.is_absolute() --> ", abs_path.is_absolute())    # True
# # print("abs_dir.rglob('*') -->", list(abs_dir.rglob("*")))   # 查看
#
# print("a_path.exists() --> ", a_path.exists())    # True



# from pathvalidate._base import BaseFile
#
# # POSIX (Linux / macOS)
# print("POSIX非法字符:", BaseFile._INVALID_FILENAME_CHARS)
#
# # Windows
# print("Windows非法字符:", BaseFile._INVALID_WIN_FILENAME_CHARS)

# a = []
# print(True if a else False)

# a = '1'
# for b in a.split(","):
#     print(b)

# from langchain.text_splitter import RecursiveCharacterTextSplitter
#
# # 初始化分块器
# text_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=500,
#     chunk_overlap=100,
#     length_function=len,
#     separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
# )
# print(text_splitter._chunk_size)
# print(text_splitter.__dict__)

# import tiktoken
#
# def get_tokenizer(model_name: str = GlobalConfig.LLM_NAME):
#     try:
#         encoding = tiktoken.encoding_for_model(model_name)
#     except KeyError:
#         print("No model named '{}'".format(model_name))
#         # 若模型不在 tiktoken 支持的列表中，回退到 cl100k_base
#         encoding = tiktoken.get_encoding("cl100k_base")
#     return encoding
#
# # 示例
# encoding = get_tokenizer("gpt-3.5-turbo")
#
# text = "你好，今天的会议内容总结如下：……"
# token_count = len(encoding.encode(text))
# print(f"Token 数量: {token_count}")

# a = {1:"111",2:"222",3:"333",4:"444",5:"555",6:"666"}
# print( [{"doc_id":"1","page_idx":k,"page_pdf_path":v}  for k,v in a.items()] )

# a = """
#
# <html><body><table><tr><td colspan="3"></td></tr><tr><td></td><td></td><td>协助部门负责人对下属子公司信息化管理工作的对接。</td></tr><tr><td>2</td><td>文秘 管理</td><td>起草信息化建设相关文件、工作计划、工作总结、工作报告等。</td></tr><tr><td>3</td><td>会务 管理 服务工作；</td><td>协助做好董事会、党委会、总经理办公会及总经理专题工作会的会务</td></tr><tr><td>4</td><td>综合行 政管理</td><td>落实总部办公区域信息化资源调配及维护工作； 落实信息化安全管理，贯彻国家有关法规，建立信息安全规章制度， 制定预案，并组织实施日常检查和监督工作。</td></tr><tr><td>5</td><td>部门 管理</td><td>协助部门负责人抓好内部制度体系建设、工作计划管理、部门员工考 核、预算编制，资产管理、综合事务管理。</td></tr><tr><td colspan="3">三、任职资格 1.学历与职称（职业资格）：具有计算机、网络、电子、通信、信息管理、数学、</td></tr><tr><td colspan="3">软件工程、自动化等相关专业硕士及以上学历；具有计算机、软件、硬件、网络等相关 高级资格证书或高级职称的优先 2.履历：具有8年以上大型公司IT战略规划、大数据中心建设、应用系统建设、网 络管理、信息安全管理等相关工作经验；有在中央、省属国有企业信息化办公室从事IT 管理者优先。</td></tr><tr><td colspan="3">3.知识、技能与素质： （1）精通java或python至少一种开发语言；精通分布式、微服务、容器、大数</td></tr><tr><td colspan="3">据、服务治理等新技术架构；精通 Spring Cloud 技术体系；熟悉mysql、nosql、 hive、HDFS等。熟悉网络架构设计和安全体系技术规范及国密相关要求；</td></tr><tr><td colspan="3">（2）了解数字化项目标准化管理工作，有一定的项目管理能力，具有大型信息化 项目管理经验者优先；</td></tr><tr><td colspan="4">（3）在计算机、软件相关领域具有丰富的工作经验，能独立开展工作，在例行事 务中能够承担主要责任； (4）具备体系化的思考能力，为人踏实敬业，做事严谨细致；</td></tr><tr><td colspan="4"></td></tr><tr><td colspan="4">4.胜任力要求：具备一定的沟通协调能力、较好的写作功底、高度的责任心，执行 能力强，能承受较大的工作压力；</td></tr><tr><td colspan="4">5.绩效与纪律：前三年绩效考核结果未出现不称职；未受过纪律处分或不在纪律处</td></tr><tr><td colspan="4"></td></tr><tr><td colspan="4">分的影响期内；</td></tr><tr><td colspan="4"></td></tr><tr><td colspan="4">6.年龄：40周岁及以下。</td></tr><tr><td colspan="4">薪酬面议。</td></tr></table></body></html>
# """
# print(len(a))

# import pandas as pd
#
#
# def linearize_table(df: pd.DataFrame, table_caption: str = None) -> str:
#     lines = []
#     if table_caption:
#         lines.append(f"{table_caption}\n")
#     lines.append("表格内容如下：")
#
#     for i, row in df.iterrows():
#         cells = []
#         for col in df.columns:
#             value = str(row[col]).strip()
#             if value:
#                 cells.append(f"{col}为“{value}”")
#         line = f"第{i + 1}行：" + "，".join(cells) + "。"
#         lines.append(line)
#
#     return "\n".join(lines)
#
#
# # 示例 DataFrame
# df = pd.DataFrame([
#     ["文秘管理", "起草信息化建设相关文件、总结、报告等"],
#     ["会务管理", "协助做好董事会、办公会等会务工作"]
# ], columns=["岗位类别", "岗位职责"])
#
# print(linearize_table(df, table_caption="岗位职责说明表"))




a = {'fid': 83, 'doc_id': 'b7c2b2ba0cbed49de6403d133ca0b648a733be6dd0ccfa0b483788cadf4feb0b', 'doc_name': 'RAG技术详解', 'doc_ext': '.docx', 'doc_path': '/home/wumingxing/tk_rag/datas/raw/RAG技术详解.docx', 'doc_size': '122.36 KiB', 'doc_http_url': '', 'doc_pdf_path': '/home/wumingxing/tk_rag/datas/processed/RAG技术详解/_home_wumingxing_tk_rag_datas_raw_RAG技术详解.pdf', 'doc_json_path': '/home/wumingxing/tk_rag/datas/processed/RAG技术详解/RAG技术详解_mineru.json', 'doc_images_path': '/home/wumingxing/tk_rag/datas/processed/RAG技术详解/images', 'doc_process_path': '/home/wumingxing/tk_rag/datas/processed/RAG技术详解/RAG技术详解_mineru_merged.json', 'process_status': 'chunked', 'error_message': None, 'created_at': 1, 'updated_at': 1, 'doc_output_dir': '/home/wumingxing/tk_rag/datas/processed/RAG技术详解'}

for key in ["doc_path", "doc_pdf_path", "doc_json_path", "doc_images_path",
            "doc_process_path", "doc_output_dir"]:
    delete_path = a.get(key, "").strip()
    print(delete_path)