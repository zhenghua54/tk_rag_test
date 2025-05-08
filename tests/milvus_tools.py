# stats = vectorstore.client.get_collection_stats(collection_name=db.collection_name)
# print(stats)
# total_docs = stats["row_count"]
# print(f"数据库中的文档总数: {total_docs}")

# from pymilvus import MilvusClient

# client = MilvusClient(uri="http://10.211.55.3:19530/", token="root:Milvus")
# client.using_database("tk_db")  # 切换到你的数据库
# stats = client.get_collection_stats(collection_name="enterprise_doc_vectors")
# print(stats)
# print("条目数：", stats["row_count"])




#     # 测试插入数据
#     from sentence_transformers import SentenceTransformer
#     from langchain_huggingface import HuggingFaceEmbeddings
#     # 初始化 embeddings
#     embeddings = HuggingFaceEmbeddings(
#         model_name=Config.MODEL_PATHS["embedding"],
#         model_kwargs={'device': Config.DEVICE}
#     )
#     test_text = """
#     发行人在行业中的竞争情况

# （一）发行人在行业中的竞争地位

# 公司成立于2007年，是国内领先的数智化服务供应商，被工信部认定为专精特新“小巨人”企业，通过CMMI 5级能力成熟度认证，还荣获高新技术企业称号。自成立以来，公司依托长期的技术积累、优质的产品以及专业的服务质量管理，已经发展成为面向全国的数智化服务领域综合服务商。截至2024年12月31日，公司业务已经覆盖全国主要省份，并在欧洲设立分支机构。

# 在与主要客户关系方面，公司已与华为合作超17年，是昇腾生态运营伙伴、昇腾原生开发伙伴（大模型方向）、昇腾算力使能服务伙伴，是华为政企主流服务供应商，是华为终端解决方案合作伙伴。曾先后荣获华为各类奖项50余项，近2年连续获得其“中国区技术服务大比武一等奖”，近2年连续获得其“地区部能力建设专项奖”，获得其“政企服务金牌供应商奖”，获得其“企业服务战略贡献奖”，曾连续3年获得华为终端“黄金级解决方案合作伙伴”，获得华为云“优秀解决方案供应商”，华为云CTSP资质，昇腾创新大赛（杭州）银奖、开发者大赛（贵州）一等奖、鲲鹏创新大赛银奖等。"""

#     model = SentenceTransformer(Config.MODEL_PATHS["embedding"])

#     # 插入一条新数据
#     row = {
#         'id': 9999,
#         'vector': model.encode(test_text),
#         'title': test_text,
#         'document_source': 'test',
#         'partment': '',
#         'role': '',
#         'doc_id': 'test'
#     }
#     db.insert_data([row])