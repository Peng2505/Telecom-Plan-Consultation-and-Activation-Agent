from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from .bss_mock import query_ticket as query_ticket_data
from .config import Config
from .orders import create_order_data, dumps_order
from .plans import dumps, estimate_overage_data, lookup_plan_data, recommend_plan_data


def get_tools(llm_embedding):
    """创建流量套餐检索与业务工具列表。"""
    vectorstore = Chroma(
        persist_directory=Config.CHROMADB_DIRECTORY,
        collection_name=Config.CHROMADB_COLLECTION_NAME,
        embedding_function=llm_embedding,
    )
    retriever = vectorstore.as_retriever()

    @tool
    def retrieve_plans(query: str) -> str:
        """检索流量套餐 FAQ、超套规则、转套餐、校园认证、流量是否清零等说明。价格数字请改用 lookup_plan。"""
        docs = retriever.invoke(query)
        if not docs:
            return "未检索到相关说明。"
        return "\n\n".join(getattr(d, "page_content", str(d)) for d in docs)

    @tool
    def lookup_plan(query: str = "", campus_student: bool = False) -> str:
        """查询套餐权威价表。query 可为套餐名、最便宜、全部、对比；campus_student 表示用户是否在校生。"""
        return dumps(lookup_plan_data(query, campus_student=campus_student))

    @tool
    def estimate_overage(monthly_usage_gb: float, current_plan: str) -> str:
        """按月用量(GB)和当前套餐名估算超套费用。单价固定每GB 10元、月封顶200元，结果以 JSON 为准。"""
        return dumps(estimate_overage_data(monthly_usage_gb, current_plan))

    @tool
    def recommend_plan(monthly_usage_gb: float, campus_student: bool = False) -> str:
        """用户提供月用量或要求推荐时调用；按学生资格返回满足用量且月费最低的权威套餐。"""
        return dumps(recommend_plan_data(monthly_usage_gb, campus_student))

    @tool
    def create_order(
        plan_name: str,
        campus_student: bool = False,
        note: str = "",
        config: RunnableConfig = None,
    ) -> str:
        """用户要求办理/开通/下单时调用。生成待办工单并提交模拟业支受理，不会在当次返回开通成功。校园套餐必须 campus_student=true。"""
        configurable = (config or {}).get("configurable", {})
        return dumps_order(
            create_order_data(
                plan_name,
                user_id=configurable.get("user_id", "anonymous"),
                thread_id=configurable.get("thread_id", "default"),
                campus_student=campus_student,
                note=note,
            )
        )

    @tool
    def query_ticket(ticket_id: str = "", config: RunnableConfig = None) -> str:
        """查询模拟业支开通回执。用户问工单进度、开通进度时调用。ticket_id 可空，则按当前 user_id 查最近一张。"""
        configurable = (config or {}).get("configurable", {})
        return dumps(
            query_ticket_data(
                ticket_id=ticket_id or "",
                user_id=configurable.get("user_id", "anonymous"),
            )
        )

    return [retrieve_plans, lookup_plan, estimate_overage, recommend_plan, create_order, query_ticket]
