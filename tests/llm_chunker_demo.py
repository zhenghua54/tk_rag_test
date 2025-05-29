import gc
import time
import logging
import torch
import psutil
from transformers import AutoTokenizer, AutoModelForCausalLM
from codes.config import Config

config = Config()

# 日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def print_memory_usage():
    """打印当前内存和 GPU 显存的使用情况"""
    # CPU 内存使用
    process = psutil.Process()
    cpu_memory = process.memory_info().rss / (1024 ** 2)  # 转换为 MB
    logging.info(f"当前 CPU 内存使用量：{cpu_memory:.2f} MB")

    # GPU 显存使用(若可用)
    if torch.cuda.is_available():
        logging.info("正在获取 GPU 显存使用量...")
        gpu_memory_allocated = torch.cuda.memory_allocated() / (1024 ** 2)  # 转换为 MB
        gpu_memory_reserved = torch.cuda.memory_reserved() / (1024 ** 2)
        logging.info(f"当前 GPU 显存使用量：{gpu_memory_allocated:.2f} MB, 已预留: {gpu_memory_reserved:.2f} MB")

    # MPS 内存使用
    elif hasattr(torch.mps, 'current_allocated_memory'):
        # 获取当前分配的 MPS 内存(以字节为单位)
        mps_allocated = torch.mps.current_allocated_memory() / (1024 ** 2)  # 转换为 MB
        logging.info(f"当前 MPS 内存使用量：{mps_allocated:.2f} MB")

    else:
        logging.warning("当前设备不支持 GPU 显存使用量查询")


def segment_text(md_text: str):

    logging.info('初始化模型...')
    # 选择使用的本地模型路径
    LLM_MODEL_PATH = '/Users/jason/models/LLM/Qwen/Qwen2.5-7B-Instruct-1M'
    model = AutoModelForCausalLM.from_pretrained(LLM_MODEL_PATH,
                                                 local_files_only=True,
                                                 trust_remote_code=True
                                                 ).to(config.device).half()

    logging.info('=== 模型加载后 ===')
    print_memory_usage()

    logging.info('加载模型分词器...')
    tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_PATH,
                                              local_files_only=True,
                                              trust_remote_code=True)

    logging.info('=== 分词器加载后 ===')
    print_memory_usage()

    # 定义 Prompt，用于指导 LLM 进行智能分块
    # PROMPT_TEMPLATE = """你是一位专业的文本分析师，擅长对长文档进行智能语义分块，尤其针对 RAG（Retrieval-Augmented Generation）任务。你的目标是根据内容逻辑合理拆分文档，确保每个段落独立清晰，便于检索和理解。
    #
    # 请遵循以下严格要求：
    #
    # 1. **保持语义完整**：不要在同一句话中断开分块，确保每个分块在逻辑和语义上都是完整的。
    # 2. **段落合理**：同一小节的内容尽量归为一个段落；内容过长时，可以自然断开，但不要强行截断。
    # 3. **分块粒度控制**：每个分块控制在适中的长度（约200-300字），过长时合理拆分，过短时适当合并。
    # 4. **标记结尾**：在每个分块的结尾添加 `|||` 符号，表示分块结束。
    # 5. **禁止添加额外解释或总结**，只返回格式化后的纯文本。
    #
    # 请仅返回分块后的结果，不需要其他说明,以下是需要分块的文档内容：
    #
    # {content}
    #
    # """

    instruction = """[INSTRUCTION]
    你是一位专业的文本分析师，擅长对长文档进行智能语义分块，尤其针对 RAG 任务。你的目标是根据内容逻辑合理拆分文档，确保每个段落独立清晰，便于检索和理解。
    请遵循：
    1. 保持语义完整
    2. 段落合理
    3. 分块粒度控制
    4. 标记结尾 '|||'
    5. 禁止总结解释
    """

    # 将文本填充到提示词模板
    content = f"[CONTENT]\n{md_text}"
    prompt_text = f"{instruction} {tokenizer.sep_token} {content}"

    start_time = time.time()

    logging.info('token 转 IDS...')
    # token 转 IDS,添加特殊符号标记,明确界定开始和结束(对小模型)
    inputs = tokenizer(prompt_text, return_tensors="pt", split_special_tokens=True).to(config.device)

    logging.info('=== token 转换后 ===')
    print_memory_usage()

    logging.info('模型推理...')
    # 使用推理模式以减少内存使用
    with torch.inference_mode():
        ouput = model.generate(
            **inputs,
            max_new_tokens=1000,
            pad_token_id=tokenizer.eos_token_id,
            temperature=0.0
        )

    logging.info('=== 推理完成后 ===')
    print_memory_usage()

    logging.info('模型输出...')
    summary = tokenizer.decode(ouput[0], skip_special_tokens=True)

    end_time = time.time()
    logging.info(f'模型运行时间：{end_time - start_time}秒')

    # 清理内存
    del model
    del tokenizer
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.mps.is_available():
        # 手动出发 Python 的垃圾回收机制
        gc.collect()
        if hasattr(torch.mps, 'empty_cache'):
            torch.mps.empty_cache()

    logging.info('=== 清理后状态 ===')
    print_memory_usage()

    return summary


if __name__ == "__main__":
    # 记录起始内存状态
    logging.info('=== 程序启动状态 ===')
    print_memory_usage()

    # with open(
    #         '/Users/jason/PycharmProjects/tk_rag_demo/datas/output_data/1_1_竞争情况（天宽科技）/1_1_竞争情况（天宽科技）.md',
    #         'r', encoding='utf-8') as f:
    #     text = f.read()

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
    try:
        summary = segment_text(text)
        print(summary)
    except Exception as e:
        logging.error(f"处理过程中发生错误：{e}")
        # 确保清理资源
        if 'model' in locals():
            del model
        if 'tokenizer' in locals():
            del tokenizer
        if hasattr(torch.mps, 'empty_cache'):
            torch.mps.empty_cache()
        raise
    logging.info('=== 程序结束状态 ===')
    print_memory_usage()

r"""
    人工智能的要素除了算力，模型，数据，还需要资源政策，科研创新，场景落地能力等要素，将上述要素有机地结合在一起，才能打造闭环的AI商业模式。公司通过平台化运营，深度融合对各级政府政策的精准解读与资源整合能力，高效协同高校及创新企业的前沿科研实力，并依托自身在解决方案设计、技术集成与商业化落地的全链条能力，构建起"政产学研用"一体化的创新生态闭环。并将国产AI技术赋能到央国企的产业龙头，助力打造新质生产力，构建可复制的、可迭代的应用场景，实现强黏性的商业闭环。

    （3）技术研发优势

    公司在ICT领域耕耘10多年，是国内最早开始移动智能终端安全技术研发的企业之一，开创性地提出基于国产华为终端通过框架虚拟化技术来实现端侧的隔离和安全的创新方案。也是国内最早一批基于国产昇腾AI技术开展研发创新的企业之一，开展包括昇腾AI算力优化、模型压缩、训推一体化、端侧模型小型化等技术创新，在算力&模型优化领域技术积累丰富。近两年连续获得浙江省、杭州市国产AI算力&模型优化领域的重大科技项目支持。截至 2024 年 12 月 31 日，公司已获得 80余项专利，其中发明专利60余项，并获得160余项软件著作权。

    同时，公司通过CMMI 5能力成熟度认证，确保技术研发创新工作在全流程中高质量交付与持续优化。通过核心技术和创新产品的深度应用，公司在市场竞争中持续构建差异化优势，实现市场份额与品牌价值的双重跃升。

    （4）领先、全面的昇腾AI技术服务优势

    公司联合华为于2024年上半年向智能体公司实在智能提供昇腾\+DeepSeek（V1 版本）的 MAAS 服务。同时，公司还是全国首个助力客户完成昇腾\+DeepSeek V3适配的企业。并通过深度适配调优，破解DeepSeek\-671B千亿级模型在昇腾端的部署瓶颈，"榨干"AI硬件性能，降低的算力成本、提升用户体验。

    同时，公司是华为云上首家发布"天宽昇腾云行业大模型适配服务解决方案"的服务商，拥有昇腾行业模型开发、模型迁移、模型调优、算子开发等全栈式 AI 解决方案服务能力。

    （5）端侧AI\+安全提前布局，打造"端侧安全智能体"

    公司将AI模型优化上的能力赋能终端侧，开创性打造端侧AI解决方案，以国产AI终端、极简模型压缩算法、系统级隐私保护三位一体，重构安全可信的智能终端生态。未来可应用在手机、平板、PC电脑、具身智能机器人、无人机、汽车、专用设备等各类形态的端上。率先在国内主流终端厂商上实现100%的端侧模型推理，开创了国产大模型在国产智能终端的高效落地先河。

    端侧 AI 极致压缩技术与安全技术深度融合，不仅实现了两大核心业务的协同创新与双向赋能，更构筑了其在端侧智能领域难以逾越的技术壁垒与竞争优势。
"""
