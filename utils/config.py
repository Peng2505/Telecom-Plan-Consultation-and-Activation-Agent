# config.py
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    """统一的配置类，集中管理所有常量"""
    PROMPT_TEMPLATE_TXT_AGENT = "prompts/prompt_template_agent.txt"
    PROMPT_TEMPLATE_TXT_GRADE = "prompts/prompt_template_grade.txt"
    PROMPT_TEMPLATE_TXT_REWRITE = "prompts/prompt_template_rewrite.txt"
    PROMPT_TEMPLATE_TXT_GENERATE = "prompts/prompt_template_generate.txt"

    KNOWLEDGE_MD = os.getenv("KNOWLEDGE_MD", "knowledge/data_plans.md")
    CHROMADB_DIRECTORY = os.getenv("CHROMADB_DIRECTORY", "chromaDB")
    CHROMADB_COLLECTION_NAME = os.getenv("CHROMADB_COLLECTION_NAME", "data_plans")

    LOG_FILE = "output/app.log"
    MAX_BYTES = 5 * 1024 * 1024
    BACKUP_COUNT = 3

    DB_URI = os.getenv(
        "DB_URI",
        "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable",
    )

    LLM_TYPE = os.getenv("LLM_TYPE", "qwen")
    EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "1536"))

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8012"))

    APP_API_KEY = os.getenv("APP_API_KEY", "").strip()
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()

    LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "").strip()
    LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "data-plan-agent")
    ORDERS_FILE = os.getenv("ORDERS_FILE", "output/orders.json")
    BSS_STORE = os.getenv("BSS_STORE", "output/bss_tickets.json")

    @staticmethod
    def enable_langsmith() -> bool:
        key = os.getenv("LANGCHAIN_API_KEY", "").strip()
        if not key:
            return False
        os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "true")
        os.environ["LANGCHAIN_API_KEY"] = key
        os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "data-plan-agent")
        return True
