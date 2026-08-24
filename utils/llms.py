import os
import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .config import Config

logger = logging.getLogger(__name__)


def _build_model_configs():
    dashscope_key = os.getenv("DASHSCOPE_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    oneapi_key = os.getenv("ONEAPI_API_KEY", "")
    return {
        "openai": {
            "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "api_key": openai_key,
            "chat_model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        },
        "oneapi": {
            "base_url": os.getenv("ONEAPI_BASE_URL", "http://localhost:3000/v1"),
            "api_key": oneapi_key,
            "chat_model": os.getenv("ONEAPI_CHAT_MODEL", "qwen-plus"),
            "embedding_model": os.getenv("ONEAPI_EMBEDDING_MODEL", "text-embedding-v2"),
        },
        "qwen": {
            "base_url": os.getenv(
                "QWEN_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            "api_key": dashscope_key,
            "chat_model": os.getenv("QWEN_CHAT_MODEL", "qwen-plus"),
            "embedding_model": os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v2"),
        },
        "ollama": {
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "api_key": os.getenv("OLLAMA_API_KEY", "ollama"),
            "chat_model": os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:8b"),
            "embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"),
        },
    }


DEFAULT_LLM_TYPE = Config.LLM_TYPE
DEFAULT_TEMPERATURE = 0.7


class LLMInitializationError(Exception):
    """自定义异常类用于LLM初始化错误"""
    pass


def initialize_llm(llm_type: str = DEFAULT_LLM_TYPE) -> tuple[ChatOpenAI, OpenAIEmbeddings]:
    try:
        configs = _build_model_configs()
        if llm_type not in configs:
            raise ValueError(f"不支持的LLM类型: {llm_type}. 可用的类型: {list(configs.keys())}")

        config = configs[llm_type]
        if not config["api_key"] and llm_type != "ollama":
            raise ValueError(
                f"{llm_type} 缺少 API Key。请在 .env 中设置 DASHSCOPE_API_KEY / OPENAI_API_KEY / ONEAPI_API_KEY"
            )

        if llm_type == "ollama":
            os.environ["OPENAI_API_KEY"] = "NA"

        llm_chat = ChatOpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"] or "NA",
            model=config["chat_model"],
            temperature=DEFAULT_TEMPERATURE,
            timeout=30,
            max_retries=2,
        )

        # DashScope 兼容接口需关闭 ctx length 预检查，否则易 400
        llm_embedding = OpenAIEmbeddings(
            base_url=config["base_url"],
            api_key=config["api_key"] or "NA",
            model=config["embedding_model"],
            check_embedding_ctx_length=False,
        )

        logger.info(f"成功初始化 {llm_type} LLM chat={config['chat_model']} embed={config['embedding_model']}")
        return llm_chat, llm_embedding

    except ValueError as ve:
        logger.error(f"LLM配置错误: {str(ve)}")
        raise LLMInitializationError(f"LLM配置错误: {str(ve)}")
    except Exception as e:
        logger.error(f"初始化LLM失败: {str(e)}")
        raise LLMInitializationError(f"初始化LLM失败: {str(e)}")


def get_llm(llm_type: str = DEFAULT_LLM_TYPE):
    try:
        return initialize_llm(llm_type)
    except LLMInitializationError as e:
        logger.warning(f"使用默认配置重试: {str(e)}")
        if llm_type != DEFAULT_LLM_TYPE:
            return initialize_llm(DEFAULT_LLM_TYPE)
        raise
