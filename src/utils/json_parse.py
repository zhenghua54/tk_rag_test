"""json 文件内容解析"""
import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")

import json
import os
from tqdm import tqdm
from rich import print

from tests.table_body_format import html_table_to_dataframe

json_file_path = "/Users/jason/PycharmProjects/tk_rag/datas/processed"


def search_file(path):
    """遍历 json 文件获取文档内容"""
    json_file_paths = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".json"):
                json_file_paths.append(os.path.join(root, file))
        if len(dirs) > 0:
            for dir in dirs:
                search_file(os.path.join(root, dir))
    return json_file_paths


if __name__ == '__main__':

    # type_set = set()
    # json_file_paths = search_file(json_file_path)
    # for json_file_path in json_file_paths:
    #     with open(json_file_path) as json_file:
    #         data = json.load(json_file)
    #         for item in data:
    #             keys = [k.strip() for k in item.keys()]
    #             type_set.add(tuple(keys))
    # print(type_set)
    #
    # exit()

    # 提取 json 文件内容
    json_file = "/Users/jason/PycharmProjects/tk_rag/datas/processed/QSG A0303008-2024 新界泵业应届大学生培养及管理办法/QSG A0303008-2024 新界泵业应届大学生培养及管理办法_content_list.json"
    with open(json_file) as f:
        data = json.load(f)
        for span in tqdm(data):
            # 如果是表格,做表格内容清晰
            if span['type'] == 'table':
                span['table_body'] = html_table_to_dataframe(span['table_body'])['table_format_str']

    # print(len(data))
    for row in tqdm(data):
        print(row)
        # if row['type'] == 'table':
        #     print(type(row['table_body']))
        # exit()
