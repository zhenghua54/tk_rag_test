import os

import tiktoken
import torch
import gc
import time
import jinja2.exceptions

from typing import Optional, List, Dict, Any, Union
from abc import ABC, abstractmethod

from jinja2 import Template
from langchain_core.documents import Document
from langchain_core.messages import trim_messages, BaseMessage, HumanMessage, AIMessage
from openai import OpenAI
from requests import RequestException
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.log_utils import logger
from config.global_config import GlobalConfig


class ModelManager(ABC):
    """模型管理器基类，实现单例模式"""
    _instance = None  # 单例模式
    _model = None  # 模型实例
    _is_initialized = False  # 是否初始化
    _last_used_time = None  # 模型最后一次使用时间
    _idle_timeout = 3600  # 模型空闲超时时间,默认 1 小时不使用则考虑卸载

    @classmethod
    def get_instance(cls):
        """获取模型管理器"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @abstractmethod
    def _init_model(self):
        """初始化模型的具体实现， 支持子类重写"""
        pass

    def get_model(self):
        """懒加载模型， 如果模型未初始化，则初始化模型"""
        self._last_used_time = time.time()  # 更新模型最后一次使用时间
        if not self._is_initialized:
            logger.info(f"首次使用，开始加载{self.__class__.__name__}模型...")
            self._model = self._init_model()
            self._is_initialized = True
            logger.info(f"{self.__class__.__name__}模型加载完成")
        return self._model

    def check_idle(self):
        """检查模型是否空闲， 如果空闲时间超过 _idle_timeout 则卸载模型"""
        if self._is_initialized and self._last_used_time:
            idle_time = time.time() - self._last_used_time
            if idle_time > self._idle_timeout:  # 如果空闲时间超过 _idle_timeout 则卸载模型
                logger.info(f"{self.__class__.__name__}模型已空闲 {idle_time:.2f} 秒， 进行卸载")
                self.unload_model()

    @staticmethod
    def clear_cache():
        """清理模型缓存"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    def unload_model(self):
        """卸载模型释放资源"""
        if self._is_initialized:
            logger.info(f"开始卸载{self.__class__.__name__}模型...")
            self.clear_cache()
            self._model = None
            self._is_initialized = False
            # 疑问
            logger.info(f"{self.__class__.__name__}模型卸载完成")

    def get_model_status(self) -> Dict[str, Any]:
        """获取模型状态"""
        return {
            "is_initialized": self._is_initialized,
            "model_name": self._model.__class__.__name__ if self._is_initialized else None,
            "memory_usage": torch.cuda.memory_allocated() if torch.cuda.is_available() and self._is_initialized else 0
        }


class EmbeddingManager(ModelManager):
    """Embedding模型管理器"""
    _idle_timeout = 3600  # Embedding 模型 1 小时不使用则卸载

    def _init_model(self) -> SentenceTransformer:
        """初始化Embedding模型"""
        try:
            model = SentenceTransformer(
                GlobalConfig.MODEL_PATHS.get("embedding"),
                device=GlobalConfig.DEVICE,
            )
            # 设置最大序列长度
            model.max_seq_length = 1024
            return model
        except Exception as e:
            logger.error(f"Embedding模型加载失败: {str(e)}")
            raise

    def embed_text(self, text: Union[str, List[str]]) -> List[float]:
        """单段文本向量化, 支持单段和批量"""
        model = self.get_model()
        try:
            # 采用向量归一化， 将向量归一化到 [-1, 1] 之间，提高相似度计算的准确性, 减少向量长度对相似度计算的影响，余弦相似度计算更稳定
            embedding = model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"文本向量化失败: {str(e)}")
            raise


class RerankManager(ModelManager):
    """Rerank模型管理器"""
    _idle_timeout = 3600  # Rerank 模型 1 小时不使用则卸载
    _tokenizer = None  # 添加重排序模型 tokenizer， 用于分词

    def _init_model(self) -> AutoModelForSequenceClassification:
        """初始化Rerank模型"""
        try:
            model = AutoModelForSequenceClassification.from_pretrained(
                GlobalConfig.MODEL_PATHS.get("rerank"),
                device_map="auto",  # 自动设备分配， 需要 'accelerate>=0.26.0' 支持
                max_memory={0: "40GiB"},  # 指定每个 GPU 的最大内存
                offload_folder="offload",  # 将部分权重卸载到 CPU
                offload_state_dict=True  # 自动管理状态字典
            )
            self._tokenizer = AutoTokenizer.from_pretrained(GlobalConfig.MODEL_PATHS.get("rerank"))
            return model
        except Exception as e:
            logger.error(f"Rerank模型加载失败: {str(e)}")
            raise

    def rerank(self, query: str, passages: List[str]) -> List[float]:
        """重排序"""
        model = self.get_model()
        try:
            # 构建输入
            inputs = self._tokenizer(
                [query] * len(passages),
                passages,
                padding=True,
                truncation=True,
                return_tensors="pt"
            )

            # 移动到正确的设备
            inputs = {k: v.to(model.device) for k, v in inputs.items()}

            # 计算分数
            with torch.no_grad():
                outputs = model(**inputs)
                scores = outputs.logits.squeeze(-1)

            return scores.cpu().numpy().tolist()
        except Exception as e:
            logger.error(f"重排序失败: {str(e)}")
            raise

    def unload_model(self):  # 重写卸载方法，同时清理 tokenizer
        """重写卸载方法，同时清理 tokenizer"""
        if self._is_initialized:
            logger.info(f"开始卸载{self.__class__.__name__}模型...")
            self.clear_cache()
            self._model = None
            self._tokenizer = None  # 清理 tokenizer
            self._is_initialized = False
            self._last_used_time = None
            logger.info(f"{self.__class__.__name__}模型卸载完成")


class LLMManager(ModelManager):
    """LLM模型管理器"""
    _idle_timeout = 1800  # LLM 模型 30 分钟不使用则卸载
    _client = None  # 添加 LLM 模型 client， 用于调用 LLM

    def _init_model(self) -> OpenAI:
        """初始化LLM模型"""
        try:
            api_key = os.getenv("DASHSCOPE_API_KEY")
            if not api_key:
                raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")

            self._client = OpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            return self._client
        except Exception as e:
            logger.error(f"LLM模型加载失败: {str(e)}")
            raise

    @property
    def api_key(self) -> str:
        """获取 LLM 模型 api_key"""
        return os.getenv("DASHSCOPE_API_KEY")

    @retry(
        stop=stop_after_attempt(3),  # 最多重试 3 次
        wait=wait_exponential(multiplier=1, min=1, max=8),  # 指数回退策略
        retry=retry_if_exception_type(RequestException),  # 捕获所有异常类型，可按需改
        reraise=True  # 重试后失败仍抛出异常
    )
    def invoke(self,
               messages: Optional[List[Dict]] = None,
               prompt: Optional[str] = None,
               model: str = GlobalConfig.LLM_NAME,
               temperature: float = 0.3,
               top_p: float = 0.9,
               stream: bool = False,
               system_prompt: Optional[str] = None,
               max_tokens: Optional[int] = None,
               invoke_type: Optional[str] = None) -> str:  # 最大输出 token
        """支持 Chat-style 调用"""

        client = self.get_model()
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt:
                messages.append({"role": "user", "content": prompt})
            else:
                raise ValueError("未提供 Prompt 或 messages")

        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
            "seed": 1,  # 种子数,确保输出结果的确定性
        }
        if max_tokens:
            params["max_tokens"] = max_tokens

        completion = client.chat.completions.create(**params)
        logger.info(
            f"本次{invoke_type}使用情况 --> 模型: {completion.model}, 输入 Token: {completion.usage.prompt_tokens}, 输出 Token: {completion.usage.completion_tokens}, 总 Token: {completion.usage.total_tokens}")

        return completion.choices[0].message.content

    def upload_model(self):
        """重写卸载方法，同时清理 client"""
        if self._is_initialized:
            logger.info(f"开始卸载{self.__class__.__name__}模型...")
            self.clear_cache()
            self._model = None
            self._client = None
            self._is_initialized = False
            self._last_used_time = None
            logger.info(f"{self.__class__.__name__}模型卸载完成")

    @staticmethod
    def count_tokens(message: Union[BaseMessage, str, List[Union[BaseMessage, str]]],
                     model_name: str = "qwen-turbo") -> int:

        # 统一转字符串
        if isinstance(message, list):
            message = "".join([
                m.content if isinstance(m, BaseMessage) else str(m)
                for m in message
            ])
        elif isinstance(message, BaseMessage):
            message = message.content
        elif not isinstance(message, str):
            message = str(message)

        if not message or not isinstance(message, str):
            return 0

        # 获取 tokenizer
        try:
            encoding = tiktoken.encoding_for_model(model_name)
            logger.info(f"使用 {model_name} 模型的 tokenizer")
        except KeyError:
            logger.warning(f"没有 {model_name} 模型的 tokenizer, 使用 cl100k_base")
            # 若模型不在 tiktoken 支持的列表中，回退到 cl100k_base
            encoding = tiktoken.get_encoding("cl100k_base")

        try:
            encoding_ids = encoding.encode(message)
            logger.info(f"token 数量为: {len(encoding_ids)}")
            return len(encoding_ids)
        except Exception as e:
            logger.error(f"计算 token 失败: {str(e)}")
            return 0


# 为了保持向后兼容性，创建全局实例
embedding_manager = EmbeddingManager.get_instance()
rerank_manager = RerankManager.get_instance()
llm_manager = LLMManager.get_instance()
llm_count_tokens = llm_manager.count_tokens


# 创建定时任务检查模型状态
def check_models_status():
    """定期检查所有模型状态"""
    embedding_manager.check_idle()
    rerank_manager.check_idle()
    llm_manager.check_idle()


def render_prompt(name: str, variables: Dict[str, str], as_str: bool = True) -> Union[str, Template, tuple[str, Dict]]:
    """渲染提示词模板为字符串（或返回模板对象）"""
    prompt_config = GlobalConfig.PROMPT_TEMPLATE[name]
    prompt_path = os.path.join(GlobalConfig.BASE_DIR, 'config', prompt_config['prompt_file'])
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    try:
        rendered = template.render(**variables)
        return (rendered, prompt_config) if as_str else (template, prompt_config)
    except jinja2.exceptions.TemplateError as e:
        logger.error("提示词组装失败", e)
        raise e


def get_messages_for_rag(system_prompt: str, history: List[BaseMessage],
                         docs: List[Document], question: str) -> List[Dict]:
    """通过系统提示词, 历史对话, 用户提示词构造用于 Chat-style 模型的 messages 消息结构
    - 注意: 该方法为 OPENAI 接口构建数据,因此角色名称应为: system, user, assistant

    Args:
        system_prompt: 系统提示词
        history: 历史对话
        docs: 知识库信息, 分数在 metadata 中
        question: 用户最新问题
    """
    logger.info(f"[get_messages_for_rag] 输入 history 条数: {len(history)}")

    # 初始化长度剪裁参数
    token_total = 32768 # Qwen Turbo 模型输入输出总长度
    context_max_len = 10000
    history_max_len = 10000

    messages = []
    
    # ===== 系统提示词 =====
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt.strip()})
    print(f"\n 系统提示词后的messages: {messages} \n")

    # ===== 知识库信息 =====
    if docs:
        # 构建知识库信息
        docs_content = "【知识库信息】\n"
        token_total = 0
        context_lines = []
        
        for doc in docs:
            if hasattr(doc, "metadata" ) and doc.metadata:
                seg_content = doc.metadata.get("seg_content", "")
                if seg_content:
                    # 计算当前片段的 token 数
                    segment_tokens = llm_count_tokens(seg_content)
                    # 超限切割
                    if token_total + segment_tokens > context_max_len:
                        logger.info("知识库内容 token 数达到限制, 裁剪后续内容")
                        break

                    docs_content += f"{seg_content}\n\n"
                    token_total += segment_tokens
                    context_lines.append(docs_content)

        # 如果知识库信息不为空，则添加到 messages
        if docs_content != "【知识库信息】\n":
            messages.append({"role": "user","content": docs_content})
        logger.info(f"知识库 context 剪裁后共 {len(context_lines)} 段，token 总数 {token_total}")

    print(f"\n 知识库信息拼装后的messages: {messages} \n")
    print(f"\n 接收到的对话历史: {history} \n")

    # ===== 历史对话处理 =====
    if history:
        # 剪裁历史对话, 控制最大 token 长度, 避免使用 start_on 参数, 如果历史对话为空或只有一条消息，则不进行裁剪
        if len(history) <= 1:
            trimmed_history = history
            logger.info(f"历史对话为空或只有一条消息，不进行裁剪")
        else:
            trimmed_history: List[BaseMessage] = trim_messages(
                messages=history,  # List[BaseMessage]（历史对话）
                token_counter=llm_count_tokens,  # 函数，逐条调用, 计算每条消息的 token 数
                max_tokens=history_max_len,  # 限定最大 token 数
                strategy="last",  # 保留最近对话, "first"保留最早对话
                start_on="human",  # 裁剪指定角色前的内容, "ai"为从 AI 回答开始
                include_system=True,  # 是否保留 system message
                allow_partial=True  # 超限时是否保留部分片段
            )
        logger.info(f"\n 裁剪后的历史对话: {trimmed_history} \n")

        # 转换为 OpenAI 接口格式
        for msg in trimmed_history:
            if not msg.content or not msg.content.strip():
                continue  # 忽略空内容
            
            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                message_dict = {"role": "assistant", "content": msg.content}
                
                # # 预留未来对 tool calls/ function 调用的支持
                # # 添加工具调用信息
                # if msg.additional_kwargs.get("tool_calls"):
                #     message_dict["tool_calls"] = msg.additional_kwargs["tool_calls"]
                
                # # 添加函数调用信息
                # if msg.additional_kwargs.get("function_call"):
                #     message_dict["function_call"] = msg.additional_kwargs["function_call"]
                    
                messages.append(message_dict)
                
        logger.info(f"\n 历史对话后的messages: {messages} \n")

    # ===== 新问题 =====
    if question and question.strip():
        messages.append({"role": "user", "content": question.strip()})

    logger.info(f"最终构建的 messages 数量: {len(messages)}")
    return messages


def trim_context_by_token(context_chunks: List[str], max_tokens: int) -> str:
    """裁剪上下文, 避免超长"""
    result = []
    total = 0
    for chunk in context_chunks:
        t = llm_count_tokens(chunk)
        if total + t > max_tokens:
            break
        result.append(chunk)
        total += t
    return "\n\n".join(result) or "(无)"
