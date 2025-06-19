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