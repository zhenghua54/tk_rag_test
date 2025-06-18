"""测试数据库插入数据"""

import pymysql

conn = pymysql.connect(
    host='localhost',
    port=3306,
    user="root",
    password="Tk@654321",
    database="rag_db_new"
)
cursor = conn.cursor()

# data = ({
#             'seg_id': '60f6a9786769a17500a7879be33aa40bd4f334862e7a7089bcd130ff88603638',
#             'seg_parent_id': '',
#             'seg_content': '杭州天宽科技有限公司\n服务质量体系手册\n最新发布日期：二\uf081二五年一月二十四日',
#             'seg_len': '38', 'seg_type': 'text', 'seg_page_idx': '0',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'},
#         {
#             'seg_id': 'e573ec93250d1e3b8324635852981e89d5e994344eacd87ca796df4611b232d9',
#             'seg_parent_id': '',
#             'seg_content': '质量是企业生存发展的基石，质量作为底线，合规作为前提，要持续构建大质量生态格局观，以客户满意为中心，创新企业新质生产力。\n质量要紧跟公司业务发展，从业务实质角度出发，实事求是，保障公司战略可落地执行，确保公司在数字化建设、新业务等领域方面的质量流程快速落地。\n卢晓飞董事长对公司质量战略提出的要求',
#             'seg_len': '148', 'seg_type': 'text', 'seg_page_idx': '1',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': '8ad3465b680959b6056d4774be54210257c142c033ad3201aeb182440ce8530f',
#             'seg_parent_id': '',
#             'seg_content': '质量文件版本更新管理规定\n大版本更新规则：\n客户侧及公司侧，整体流程变动或大于等于 5 个流程的履行规范变动，所有区域质量经理全员到总部现场刷新所有质量文件。（流程变动包含但不限于华为 IT 系统切换）\n服务中心新增或取消业务流程，所有区域质量经理全员到总部现场刷新质量文件。\n小版本更新规则：\n客户侧及公司侧，小于或等于四个流程的履行规范要求变动，进行小版本更新，质量部门远程组织会议进行具体更新操作。\n每年定期质量与安全管理部组织区域质量经理进行对现有质量文件进行审视优化，更新小版本，更新内容全员通知，区域组织学习。\n版本命名规则：\n初始版本V1.0，大版本 V2.0、V3.0 递增。审核人：服务中心总经理助理，审批人：服务中心总经理。\n初始版本V1.0，小版本 V1.1、V1.2 递增。审核人：服务中心总经理助理，审批人：服务中心总经理。',
#             'seg_len': '375',
#             'seg_type': 'text',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_parent_id': '',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'表格展示了不同版本及其批次的关系，包括大版本V1.0、V2.0、V3.0及其对应的次版本A/1、B/1、C/1等。\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_image_path': '/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系_第1部分_1-22/images/f13131369ef429578b856f70b6131e34ec3ebb9ad531f09012f0d039cd7054bb.jpg',
#             'seg_caption': '初始版本V1.0，小版本 V1.1、V1.2 递增。审核人：服务中心总经理助理，审批人：服务中心总经理。',
#             'seg_footnote': [], 'seg_len': '2046', 'seg_type': 'table', 'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': 'ca9ef8677d7d011520d98494fb435d28f782bf0958be40db2bf01c365a0486a9',
#             'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'| 版本演进及版本与版本批次关系   | 版本演进及版本与版本批次关系   | 版本演进及版本与版本批次关系   | 版本演进及版本与版本批次关系   | 版本演进及版本与版本批次关系   |         |        |         |       |     |       |     |       |     |       |     |       |     |       |     |    |    |    |    |    |\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_len': '234',
#             'seg_type': 'table',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': 'f51b79b62d7baee63dc0a5318767ffdf699f14fce5fdbb51564bcb83e05641bd',
#             'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'|:-------------------------------|:-------------------------------|:-------------------------------|:-------------------------------|:-------------------------------|:--------|:-------|:--------|:------|:----|:------|:----|:------|:----|:------|:----|:------|:----|:------|:----|:---|:---|:---|:---|:---|\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_len': '304',
#             'seg_type': 'table',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': 'f1012a99e32934275007cc325cf44307e834602c14da786dfb7f088dd3d3ef9c',
#             'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'|                                |                                |                                |                                | 大版本                         | 版本/次 | 小版本 | 版本/次 |       |     |       |     |       |     |       |     |       |     |       |     |    |    |    |    |    |\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_len': '292',
#             'seg_type': 'table',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': '516c47cea46f0bfe319406db105fea9415aca4a330bb1177d1b223c41c113610',
#             'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'|                                |                                |                                |                                |                                |         |        |         | V1. 0 | A/1 | V1. 1 | A/2 | ：    |     |       |     |       |     |       |     |    |    |    |    |    |\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_len': '303',
#             'seg_type': 'table',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': 'c984479c03f9d6c95a68e2cd405813ca4ec3b67136c5fb16a58f99d19e4da7d2',
#             'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'|                                |                                |                                |                                |                                |         |        |         |       |     |       |     | V2. 0 | B/1 | V2. 1 | B/2 | ：    |     |       |     |    |    |    |    |    |\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_len': '303',
#             'seg_type': 'table',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': 'aa7a10ab18ab4f63748201a5bd807e67371bcc667c5cbfa29a7c125831c5e687',
#             'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'|                                |                                |                                |                                |                                |         |        |         |       |     |       |     |       |     |       |     | V3. 0 | C/1 | V3. 1 | C/2 | ： |    |    |    |    |\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_len': '303',
#             'seg_type': 'table',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         },
#         {
#             'seg_id': 'aa5f60f2e6079b68848623ca5a539ffd636a3470115e1632610f14023e418670',
#             'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
#             'seg_content': 'CONCAT(\'"\', REPLACE(\'|                                |                                |                                |                                |                                |         |        |         |       |     |       |     |       |     |       |     |       |     |       |     |    | ： | …  | ： | ： |\', \'"\', \'\\\\"\'), \'"\')',
#             'seg_len': '301',
#             'seg_type': 'table',
#             'seg_page_idx': '2',
#             'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
#         }
# )

data1 = "\n\n<html><body><table><tr><td colspan=\"5\">版本演进及版本与版本批次关系</td></tr><tr><td>大版本</td><td>版本/次</td><td>小版本</td><td>版本/次</td><td></td></tr><tr><td>V1. 0</td><td>A/1</td><td>V1. 1</td><td>A/2</td><td>：</td></tr><tr><td>V2. 0</td><td>B/1</td><td>V2. 1</td><td>B/2</td><td>：</td></tr><tr><td>V3. 0</td><td>C/1</td><td>V3. 1</td><td>C/2</td><td>：</td></tr><tr><td></td><td>：</td><td>…</td><td>：</td><td>：</td></tr></table></body></html>\n\n"
datas = {
    'seg_id': 'aa5f60f2e6079b68848623ca5a539ffd636a3470115e1632610f14023e418670',
    'seg_parent_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
    'seg_content': data1,
    'seg_len': '301',
    'seg_type': 'table',
    'seg_page_idx': '2',
    'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'
}

fields = list(datas.keys())
placeholders = ",".join(['%s'] * len(fields))
# print(fields)
# print(placeholders)
# exit()
sql = f'INSERT INTO segment_info ({",".join(fields)}) VALUES ({placeholders})'

values = list(datas.values())
print(values)
try:
    cursor.execute(sql, values)
    conn.commit()
except Exception as e:
    print(e)

# try:
#     for item in datas:
#         values = [item.get(field, "") for field in fields]
#         cursor.execute(sql, values)
#     conn.commit()
# except Exception as e:
#     raise ValueError(f"数据异常: {str(e)}")
#
# finally:
cursor.close()
conn.close()

# print(sql)
# html_table = ""
# seg_id = "7734b36ac7d51c9b38c3070a4041f3c9ec5cc692897cc6b95db18720c8b28a57"
# sql = 'insert into segment_info %s values %s'
#
# cursor.execute()
#
# print("conn", conn)
# print("cursor", cursor)

a = {
    'seg_id': '437cd245a92d0dd4fe7a870adeb237091de2ea8526c86256e443e2d7127f61f0',
    'seg_parent_id': '',
    'seg_content': '<html><body><table><tr><td colspan="5">版本演进及版本与版本批次关系</td></tr><tr><td>大版本</td><td>版本/次</td><td>小版本</td><td>版本/次</td><td></td></tr><tr><td>V1. 0</td><td>A/1</td><td>V1. 1</td><td>A/2</td><td>：</td></tr><tr><td>V2. 0</td><td>B/1</td><td>V2. 1</td><td>B/2</td><td>：</td></tr><tr><td>V3. 0</td><td>C/1</td><td>V3. 1</td><td>C/2</td><td>：</td></tr><tr><td></td><td>：</td><td>…</td><td>：</td><td>：</td></tr></table></body></html>',
    'seg_image_path': '/home/jason/tk_rag/datas/processed/天宽服务质量体系_第1部分_1-22/images/f13131369ef429578b856f70b6131e34ec3ebb9ad531f09012f0d039cd7054bb.jpg',
    'seg_caption': '初始版本V1.0，小版本 V1.1、V1.2 递增。审核人：服务中心总经理助理，审批人：服务中心总经理。',
    'seg_footnote': [],
    'seg_len': '2046',
    'seg_type': 'table',
    'seg_page_idx': '2', 'doc_id': '162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26'}
