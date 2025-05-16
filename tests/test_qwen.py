from modelscope import AutoModelForCausalLM, AutoTokenizer

model_name = "/Users/jason/models/LLM/Qwen/Qwen3-8B"

# load the tokenizer and the model
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map=None,
    trust_remote_code=True
).to("mps")

# prepare the model input
prompt = "Give me a short introduction to large language model."

text = r"""
    发行人在行业中的竞争情况

    __（一）发行人在行业中的竞争地位__

    公司成立于2007年，是国内领先的数智化服务供应商，被工信部认定为专精特新"小巨人"企业，通过CMMI 5级能力成熟度认证，还荣获高新技术企业称号。自成立以来，公司依托长期的技术积累、优质的产品以及专业的服务质量管理，已经发展成为面向全国的数智化服务领域综合服务商。截至2024年12月31日，公司业务已经覆盖全国主要省份，并在欧洲设立分支机构。

    在与主要客户关系方面，公司已与华为合作超17年，是昇腾生态运营伙伴、昇腾原生开发伙伴（大模型方向）、昇腾算力使能服务伙伴，是华为政企主流服务供应商，是华为终端解决方案合作伙伴。曾先后荣获华为各类奖项50余项，近2年连续获得其"中国区技术服务大比武一等奖"，近2年连续获得其"地区部能力建设专项奖"，获得其"政企服务金牌供应商奖"，获得其"企业服务战略贡献奖"，曾连续3年获得华为终端"黄金级解决方案合作伙伴"，获得华为云"优秀解决方案供应商"，华为云CTSP资质，昇腾创新大赛（杭州）银奖、开发者大赛（贵州）一等奖、鲲鹏创新大赛银奖等。

    同时，公司在移动终端安全领域还与荣耀、OPPO、VIVO、中国移动、中国电信、中国联通等深度合作，是荣耀企业战略合作伙伴、OPPO企业业务战略合作伙伴、VIVO行业合作伙伴，在中国移动、中国电信、中国联通等运营商上架产品数十款。

    XX\-XXXX 年，公司营业收入保持快速增长，分别为 xxx 万元、xxxx 万元及 xxxx 万元，年均复合增长率为 xxxx%。根据可比上市公司同期数据，公司业务规模居于行业前列水平。

    __（二）发行人在行业中的竞争优势和劣势__

    1、竞争优势

    （1）AI产业的先行者，先发领跑优势

    公司是国内最早一批承担昇腾人工智能计算中心建设和运营的服务商，自2021年起负责承建与运营杭州市人工智能计算中心，并实现了连续三年的扩容，三期总建设规模达到了约6亿元。通过与华为的紧密合作，基于昇腾AI平台，公司提供涵盖咨询、集成、算力、模型、数据及服务在内的一站式AI解决方案，在昇腾AI生态系统中占据了重要的行业地位。

    （2）AI生态联接广，未来充满爆点。
    """

instruction = """
你是一位专业的文档分析专家。请严格按照以下要求对用户提供的文档内容进行分块：
1. 不得篡改原文
2. 根据自然段落和语义完整性分块
3. 每块长度 300-500 字左右
4. 每块以'[chunk_start]'标记开头
5. 优先按照文档内的标题分层进行分块
6. 连续的标题序号不要切断
"""
messages = [
    {"role":"system","content":instruction},
    {"role": "user", "content": text}
]
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
    enable_thinking=False # Switch between thinking and non-thinking modes. Default is True.
)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

# conduct text completion
generated_ids = model.generate(
    **model_inputs,
    max_new_tokens=32768
)
output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()

# parsing thinking content
try:
    # rindex finding 151668 (</think>)
    index = len(output_ids) - output_ids[::-1].index(151668)
except ValueError:
    index = 0

thinking_content = tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
content = tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")

print("thinking content:", thinking_content)
print("content:", content)
