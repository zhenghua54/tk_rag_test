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
from openai import OpenAI, RateLimitError, APIError
from requests import RequestException
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.log_utils import logger, log_exception
from config.global_config import GlobalConfig
from utils.simple_rate_limiter import rate_limiter


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
            logger.debug(f"[模型加载] 首次使用，开始加载{self.__class__.__name__}模型...")
            self._model = self._init_model()
            self._is_initialized = True
            logger.info(f"[模型加载] {self.__class__.__name__}模型加载完成")
        return self._model

    def check_idle(self):
        """检查模型是否空闲， 如果空闲时间超过 _idle_timeout 则卸载模型"""
        if self._is_initialized and self._last_used_time:
            idle_time = time.time() - self._last_used_time
            if idle_time > self._idle_timeout:  # 如果空闲时间超过 _idle_timeout 则卸载模型
                logger.info(f"[模型卸载] {self.__class__.__name__}模型已空闲{idle_time:.2f}秒，进行卸载")
                self.unload_model()

    @staticmethod
    def clear_cache():
        """清理模型缓存"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    def unload_model(self):
        """重写卸载方法，同时清理 client"""
        if self._is_initialized:
            logger.info(f"[模型卸载] 开始卸载{self.__class__.__name__}模型")
            self.clear_cache()
            self._model = None
            self._client = None
            self._is_initialized = False
            logger.info(f"[模型卸载] {self.__class__.__name__}模型卸载完成")

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
            logger.error(f"[Embedding模型失败] error_msg={str(e)}")
            raise

    def embed_text(self, text: Union[str, List[str]]) -> List[float]:
        """单段文本向量化, 支持单段和批量"""
        model = self.get_model()
        try:
            # 采用向量归一化， 将向量归一化到 [-1, 1] 之间，提高相似度计算的准确性, 减少向量长度对相似度计算的影响，余弦相似度计算更稳定
            embedding = model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"[文本向量化失败] error_msg={str(e)}")
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
            logger.error(f"[Rerank模型失败] error_msg={str(e)}")
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
            logger.error(f"[重排序失败] error_msg={str(e)}")
            raise

    def unload_model(self):  # 重写卸载方法，同时清理 tokenizer
        """重写卸载方法，同时清理 tokenizer"""
        if self._is_initialized:
            logger.info(f"[模型卸载] 开始卸载{self.__class__.__name__}模型")
            self.clear_cache()
            self._model = None
            self._tokenizer = None  # 清理 tokenizer
            self._is_initialized = False
            self._last_used_time = None
            logger.info(f"[模型卸载] {self.__class__.__name__}模型卸载完成")


class LLMManager(ModelManager):
    """LLM模型管理器"""
    _idle_timeout = 1800  # LLM 模型 30 分钟不使用则卸载
    _client = None  # 添加 LLM 模型 client， 用于调用 LLM
    _model_config = None  # 存储模型配置
    _model_name = None  # 存储模型实际名称

    def __init__(self):
        super().__init__()
        # 初始化时获取配置
        self._model_config = GlobalConfig.get_current_llm_config()
        self._model_name = self._model_config["name"]
        logger.info(f"[LLM初始化] 使用模型={self._model_name}")

    def _init_model(self) -> OpenAI:
        """初始化LLM模型"""
        try:
            client = OpenAI(
                api_key=self._model_config["api_key"],
                base_url=self._model_config["base_url"],
                timeout=60.0
            )
            self._client = client
            return client
        except Exception as e:
            logger.error(f"[LLM模型失败] error_msg={str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(5),  # 最多重试 5 次
        wait=wait_exponential(multiplier=2, min=1, max=60),  # 指数回退， 最大等待 60秒
        retry=retry_if_exception_type((RequestException, RateLimitError, APIError)),  # 捕获所有异常类型，添加 429(超限)错误处理
        reraise=True  # 重试后失败仍抛出异常
    )
    def invoke(self,
               messages: Optional[List[Dict]] = None,
               prompt: Optional[str] = None,
               model: str = None,
               temperature: float = 0.3,
               top_p: float = 0.9,
               stream: bool = False,
               system_prompt: Optional[str] = None,
               max_tokens: Optional[int] = None,
               invoke_type: Optional[str] = None) -> str:  # 最大输出 token
        """支持 Chat-style 调用"""
        # 统一限流控制
        rate_limiter.wait_if_needed()

        model_name = model or self._model_name

        client = self.get_model()
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt:
                messages.append({"role": "user", "content": prompt})
        if messages is None and  system_prompt is None and prompt is None:
            raise ValueError("未提供 Prompt 或 messages")

        params = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
            "seed": 1,  # 种子数,确保输出结果的确定性
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        try:
            completion = client.chat.completions.create(**params)
            logger.debug(
                f"[LLM调用] {invoke_type}, 模型={completion.model}, 输入Token={completion.usage.prompt_tokens}, 输出Token={completion.usage.completion_tokens}, 总Token={completion.usage.total_tokens}")
            return completion.choices[0].message.content
        except RateLimitError as e:
            logger.warning(f"[LLM限流] error_msg={e}, 将进行重试")
            raise
        except APIError as e:
            logger.warning(f"[LLM错误] error_msg={e}, 将进行重试")
            raise
        except Exception as e:
            logger.error(f"[LLM调用失败] error_msg={str(e)}")
            raise

    def unload_model(self):
        """重写卸载方法，同时清理 client"""
        if self._is_initialized:
            logger.info(f"[模型卸载] 开始卸载{self.__class__.__name__}模型")
            self.clear_cache()
            self._model = None
            self._client = None
            self._is_initialized = False
            self._last_used_time = None
            logger.info(f"[模型卸载] {self.__class__.__name__}模型卸载完成")

    @staticmethod
    def count_tokens(message: Union[BaseMessage, str, List[Union[BaseMessage, str]]]) -> int:

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

        # 获取分词器计算 token 数
        try:
            logger.debug(f"[Token计算] 使用cl100k_base分词器")
            encoding = tiktoken.get_encoding("cl100k_base")
            encoding_ids = encoding.encode(message)
            logger.debug(f"[Token计算] token数量={len(encoding_ids)}")
            return len(encoding_ids)
        except Exception as e:
            logger.error(f"[Token计算失败] error_msg={str(e)}")
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
        logger.error(f"[提示词组装失败] error_msg={str(e)}")
        raise e


def get_messages_for_rag(history: List[BaseMessage],
                         docs: List[Document], question: str) -> List[Dict]:
    """通过系统提示词, 历史对话, 用户提示词构造用于 Chat-style 模型的 messages 消息结构
    - 注意: 该方法为 OPENAI 接口构建数据,因此角色名称应为: system, user, assistant

    Args:
        history: 历史对话
        docs: 知识库信息, 分数在 metadata 中
        question: 用户最新问题
    """
    try:
        # 记录输入参数基本信息
        logger.info(f"[消息构建] 开始, history条数={len(history)}, docs条数={len(docs)}, question长度={len(question)}")

        # 初始化长度剪裁参数
        # token_total = 32768  # Qwen Turbo 模型输入输出总长度
        context_max_len = 10000
        history_max_len = 10000
        messages = []
        total_tokens = 0

        # ===== 知识库信息 =====
        docs_content = ""
        if docs:
            token_total = 0
            context_lines = []
            processed_docs = 0

            for doc in docs:
                if hasattr(doc, "metadata") and doc.metadata:
                    seg_content = doc.metadata.get("seg_content", "")
                    if seg_content:
                        # 计算当前片段的 token 数
                        segment_tokens = llm_count_tokens(seg_content)
                        # 超限切割
                        if token_total + segment_tokens > context_max_len:
                            logger.debug(f"[消息构建] 知识库内容token数达到限制，裁剪后续内容")
                            break

                        docs_content += f"{seg_content}\n\n"
                        token_total += segment_tokens
                        context_lines.append(seg_content)
                        processed_docs += 1

            # 如果知识库信息不为空，则添加到 messages
            if docs_content:
                logger.info(
                    f"[消息构建] 知识库处理完成, 处理文档数={processed_docs}/{len(docs)}, context段数={len(context_lines)}, token数={token_total}")
            else:
                docs_content += '知识库中无相关信息'
                logger.debug(f"[消息构建] 知识库中无相关信息")
        else:
            # 当docs为空时，添加无相关信息提示
            docs_content += '知识库中无相关信息'
            logger.debug(f"[消息构建] 检索结果为空，知识库中无相关信息")

        # ==== 构建完整的系统提示词 ====
        logger.debug(f"[消息构建] 开始构建系统提示词, 知识库内容长度={len(docs_content)}")
        complete_system_prompt, _ = render_prompt("rag_system_prompt", {
            "retrieved_knowledge": docs_content,
        })
        system_tokens = llm_count_tokens(complete_system_prompt)
        total_tokens += system_tokens

        # 添加系统提示词(包含知识库信息)
        messages.append({"role": "system", "content": complete_system_prompt.strip()})
        logger.debug(f"[消息构建] 系统提示词构建完成, token数={system_tokens}")

        # ===== 历史对话处理 =====
        if history:
            logger.debug(f"[消息构建] 开始处理历史对话, 原始条数={len(history)}")

            # 剪裁历史对话, 控制最大 token 长度, 避免使用 start_on 参数, 如果历史对话为空或只有一条消息，则不进行裁剪
            if len(history) <= 1:
                trimmed_history = history
                logger.debug(f"[消息构建] 历史对话为空或只有一条消息，不进行裁剪")
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
                logger.info(f"[消息构建] 历史对话裁剪完成, 原始条数={len(history)}, 裁剪后条数={len(trimmed_history)}")

            # 转换为 OpenAI 接口格式
            history_tokens = 0
            for msg in trimmed_history:
                if not msg.content or not msg.content.strip():
                    continue  # 忽略空内容

                msg_tokens = llm_count_tokens(msg.content)
                history_tokens += msg_tokens

                if isinstance(msg, HumanMessage):
                    messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages.append({"role": "assistant", "content": msg.content})

            total_tokens += history_tokens
            logger.debug(
                f"[消息构建] 历史对话处理完成, 有效条数={len([m for m in messages if m['role'] in ['user', 'assistant']])}, token数={history_tokens}")

        else:
            logger.debug(f"[消息构建] 无历史对话")

        # ===== 当前问题 =====
        if question and question.strip():
            question_tokens = llm_count_tokens(question.strip())
            total_tokens += question_tokens
            messages.append({"role": "user", "content": question.strip()})
            logger.debug(f"[消息构建] 当前问题添加完成, token数={question_tokens}")

        else:
            logger.warning(f"[消息构建] 当前问题为空")

        # 记录最终结果
        logger.info(
            f"[消息构建] 完成, 构建消息条数={len(messages)}, 总token数={total_tokens}, 角色分布={dict([(role, len([m for m in messages if m['role'] == role])) for role in ['system', 'user', 'assistant']])}")

        return messages

    except Exception as e:
        logger.error(f"[消息构建] 失败: {str(e)}")
        log_exception("消息构建异常", exc=e)
        raise e


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
