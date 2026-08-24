# 导入操作系统接口模块，用于处理文件路径和环境变量
import os
# 用于正则表达式匹配和处理字符串
import re
# 用于JSON数据的序列化和反序列化
import json
# 用于定义异步上下文管理器
from contextlib import asynccontextmanager
# 用于类型提示，定义列表和可选参数
from typing import List, Tuple
# 用于创建Web应用和处理HTTP异常
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import Request
# 用于返回JSON和流式响应
from fastapi.responses import JSONResponse, StreamingResponse
# 用于运行FastAPI应用
import uvicorn
# 导入日志模块，用于记录程序运行时的信息
import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
# 导入系统模块，用于处理系统相关的操作，如退出程序
import sys
import time
# 导入UUID模块，用于生成唯一标识符
import uuid
# 从typing模块导入类型提示工具
from typing import Optional
# 导入Pydantic的基类和字段定义工具
from pydantic import BaseModel, Field
# 从自定义的库中引入函数
os.makedirs("output", exist_ok=True)

from demoRagAgent import (
    ToolConfig,
    create_graph,
    save_graph_visualization,
    get_llm,
    get_tools,
    Config,
    ConnectionPool,
    ConnectionPoolError,
    monitor_connection_pool,
)

graph = None
tool_config = None
db_connection_pool = None
security = HTTPBearer(auto_error=False)


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not Config.APP_API_KEY:
        return
    token = credentials.credentials if credentials else ""
    if token != Config.APP_API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "unauthorized", "message": "Invalid or missing API key"},
        )


def classify_error(exc: Exception) -> tuple[int, str]:
    msg = str(exc).lower()
    if "timeout" in msg:
        return 504, "llm_timeout"
    if "pool" in msg or "connection" in msg or "postgres" in msg:
        return 503, "db_unavailable"
    return 500, "internal_error"


# Author:@南哥AGI研习社 (B站 or YouTube 搜索“南哥AGI研习社”)






# # 设置日志基本配置，级别为DEBUG或INFO
logger = logging.getLogger(__name__)
# 设置日志器级别为DEBUG
logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)
logger.handlers = []  # 清空默认处理器
# 使用ConcurrentRotatingFileHandler
handler = ConcurrentRotatingFileHandler(
    # 日志文件
    Config.LOG_FILE,
    # 日志文件最大允许大小为5MB，达到上限后触发轮转
    maxBytes = Config.MAX_BYTES,
    # 在轮转时，最多保留3个历史日志文件
    backupCount = Config.BACKUP_COUNT
)
# 设置处理器级别为DEBUG
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
))
logger.addHandler(handler)


# 定义消息类，用于封装API接口返回数据
# 定义Message类
class Message(BaseModel):
    role: str
    content: str

# 定义ChatCompletionRequest类
class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    stream: Optional[bool] = False
    userId: Optional[str] = None
    conversationId: Optional[str] = None

# 定义ChatCompletionResponseChoice类
class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Message
    finish_reason: Optional[str] = None

# 定义ChatCompletionResponse类
class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    choices: List[ChatCompletionResponseChoice]
    system_fingerprint: Optional[str] = None
    used_tools: List[str] = Field(default_factory=list)
    rewrite_count: int = 0


def _tool_call_name(tool_call) -> Optional[str]:
    if isinstance(tool_call, dict):
        return tool_call.get("name")
    return getattr(tool_call, "name", None)


def _append_trace_footer(text: str, used_tools: list, rewrite_count: int) -> str:
    tools = ", ".join(used_tools) if used_tools else "无"
    return f"{text}\n\n---\n本次调用工具: {tools} | rewrite_count={rewrite_count}"


def format_response(response):
    """对输入的文本进行段落分隔，便于阅读。"""
    paragraphs = re.split(r'\n{2,}', response)
    # 空列表，用于存储格式化后的段落
    formatted_paragraphs = []
    # 遍历每个段落进行处理
    for para in paragraphs:
        # 检查段落中是否包含代码块标记
        if '```' in para:
            # 将段落按照```分割成多个部分，代码块和普通文本交替出现
            parts = para.split('```')
            for i, part in enumerate(parts):
                # 检查当前部分的索引是否为奇数，奇数部分代表代码块
                if i % 2 == 1:  # 这是代码块
                    # 将代码块部分用换行符和```包围，并去除多余的空白字符
                    parts[i] = f"\n```\n{part.strip()}\n```\n"
            # 将分割后的部分重新组合成一个字符串
            para = ''.join(parts)
        else:
            # 否则，将句子中的句点后面的空格替换为换行符，以便句子之间有明确的分隔
            para = para.replace('. ', '.\n')
        # 将格式化后的段落添加到formatted_paragraphs列表
        # strip()方法用于移除字符串开头和结尾的空白字符（包括空格、制表符 \t、换行符 \n等）
        formatted_paragraphs.append(para.strip())
    # 将所有格式化后的段落用两个换行符连接起来，以形成一个具有清晰段落分隔的文本
    return '\n\n'.join(formatted_paragraphs)


# 管理 FastAPI 应用生命周期的异步上下文管理器，负责启动和关闭时的初始化与清理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    管理 FastAPI 应用生命周期的异步上下文管理器，负责启动和关闭时的初始化与清理。

    Args:
        app (FastAPI): FastAPI 应用实例。

    Yields:
        None: 在 yield 前完成初始化，yield 后执行清理。

    Raises:
        ConnectionPoolError: 数据库连接池初始化或操作失败时抛出。
        Exception: 其他未预期的异常。
    """
    global graph, tool_config, db_connection_pool
    db_connection_pool = None
    try:
        if Config.enable_langsmith():
            logger.info(f"LangSmith tracing enabled project={os.getenv('LANGCHAIN_PROJECT')}")
        else:
            logger.info("LangSmith tracing disabled (set LANGCHAIN_API_KEY in .env to enable)")
        # 调用 get_llm 初始化聊天模型和嵌入模型
        llm_chat, llm_embedding = get_llm(Config.LLM_TYPE)

        # 获取工具列表，基于嵌入模型
        tools = get_tools(llm_embedding)

        # 创建工具配置实例
        tool_config = ToolConfig(tools)

        # 定义数据库连接参数：自动提交、无预准备阈值、5秒超时
        connection_kwargs = {"autocommit": True, "prepare_threshold": 0, "connect_timeout": 5}
        # 创建数据库连接池：最大20个连接，最小2个活跃连接，超时10秒
        db_connection_pool = ConnectionPool(
            conninfo=Config.DB_URI,
            max_size=20,
            min_size=2,
            kwargs=connection_kwargs,
            timeout=10
        )

        # 尝试打开数据库连接池
        try:
            # 打开连接池以启用数据库连接
            db_connection_pool.open()
            # 记录连接池初始化成功的日志（INFO 级别）
            logger.info("Database connection pool initialized")
            # 记录详细调试日志（DEBUG 级别）
            logger.debug("Database connection pool initialized")
        except Exception as e:
            # 记录连接池打开失败的错误日志
            logger.error(f"Failed to open connection pool: {e}")
            # 抛出自定义连接池异常
            raise ConnectionPoolError(f"无法打开数据库连接池: {str(e)}")

        # 启动连接池监控线程，60秒检查一次，设置为守护线程
        monitor_thread = monitor_connection_pool(db_connection_pool, interval=60)

        # 尝试创建状态图
        try:
            # 使用数据库连接池和模型创建状态图
            graph = create_graph(db_connection_pool, llm_chat, llm_embedding, tool_config)
        except ConnectionPoolError as e:
            # 记录状态图创建失败的错误日志
            logger.error(f"Graph creation failed: {e}")
            # 退出程序，返回状态码 1
            sys.exit(1)

        # 保存状态图的可视化表示
        save_graph_visualization(graph)

    except ConnectionPoolError as e:
        # 捕获并记录连接池相关异常
        logger.error(f"Connection pool error: {e}")
        # 退出程序，返回状态码 1
        sys.exit(1)
    except Exception as e:
        # 捕获并记录其他未预期的异常
        logger.error(f"Unexpected error: {e}")
        # 退出程序，返回状态码 1
        sys.exit(1)

    # yield 表示应用运行期间，初始化完成后进入运行状态
    yield
    # 检查并关闭数据库连接池（清理资源）
    if db_connection_pool and not db_connection_pool.closed:
        # 关闭连接池
        db_connection_pool.close()
        # 记录连接池关闭的日志
        logger.info("Database connection pool closed")
    # 记录服务关闭的日志
    logger.info("The service has been shut down")

# 创建FastAPI实例 lifespan参数用于在应用程序生命周期的开始和结束时执行一些初始化或清理工作
app = FastAPI(title="流量包推荐 Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    user_id = request.headers.get("x-user-id", "-")
    logger.info(
        f"{request.method} {request.url.path} status={response.status_code} "
        f"user_id={user_id} elapsed_ms={elapsed_ms:.1f}"
    )
    return response


class BusinessChatRequest(BaseModel):
    user_id: str
    conversation_id: str
    message: str
    stream: Optional[bool] = False


# 处理非流式响应的异步函数，生成并返回完整的响应内容
async def handle_non_stream_response(user_input, graph, tool_config, config):
    """
    处理非流式响应的异步函数，生成并返回完整的响应内容。

    Args:
        user_input (str): 用户输入的内容。
        graph: 图对象，用于处理消息流。
        tool_config: 工具配置对象，包含可用工具的名称和定义。
        config (dict): 配置参数，包含线程和用户标识。

    Returns:
        JSONResponse: 包含格式化响应的 JSON 响应对象。
    """
    # 初始化 content 变量，用于存储最终响应内容
    content = None
    used_tools = []
    rewrite_count = 0
    try:
        events = graph.stream({"messages": [{"role": "user", "content": user_input}], "rewrite_count": 0}, config)
        for event in events:
            for value in event.values():
                if isinstance(value, dict) and "rewrite_count" in value and value["rewrite_count"] is not None:
                    rewrite_count = value["rewrite_count"]
                if "messages" not in value or not isinstance(value["messages"], list):
                    logger.warning("No valid messages in response")
                    continue

                last_message = value["messages"][-1]

                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    for tool_call in last_message.tool_calls:
                        name = _tool_call_name(tool_call)
                        if name:
                            used_tools.append(name)
                            logger.info(f"Calling tool: {name}")
                    continue

                if hasattr(last_message, "content"):
                    content = last_message.content
                    if hasattr(last_message, "name") and last_message.name in tool_config.get_tool_names():
                        tool_name = last_message.name
                        used_tools.append(tool_name)
                        logger.info(f"Tool Output [{tool_name}]: {content}")
                    else:
                        logger.info(f"Final Response is: {content}")
                else:
                    logger.info("Message has no content, skipping")
    except ValueError as ve:
        logger.error(f"Value error in response processing: {ve}")
    except Exception as e:
        logger.error(f"Error processing response: {e}")

    unique_tools = list(dict.fromkeys(used_tools))
    formatted_response = str(format_response(content)) if content else "No response generated"
    formatted_response = _append_trace_footer(formatted_response, unique_tools, rewrite_count)
    logger.info(f"Results for Formatting: {formatted_response}")

    try:
        response = ChatCompletionResponse(
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=Message(role="assistant", content=formatted_response),
                    finish_reason="stop"
                )
            ],
            used_tools=unique_tools,
            rewrite_count=rewrite_count,
        )
    except Exception as resp_error:
        # 捕获并记录构造响应对象时的异常
        logger.error(f"Error creating response object: {resp_error}")
        # 构造错误响应对象
        response = ChatCompletionResponse(
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=Message(role="assistant", content="Error generating response"),
                    finish_reason="error"
                )
            ]
        )

    # 记录发送给客户端的响应内容日志
    logger.info(f"Send response content: \n{response}")
    # 返回 JSON 格式的响应对象
    return JSONResponse(content=response.model_dump())


# 处理流式响应的异步函数，生成并返回流式数据
async def handle_stream_response(user_input, graph, config, tool_config):
    async def generate_stream():
        try:
            chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
            used_tools = []
            stream_data = graph.stream(
                {"messages": [{"role": "user", "content": user_input}], "rewrite_count": 0},
                config,
                stream_mode="messages"
            )
            for message_chunk, metadata in stream_data:
                try:
                    node_name = metadata.get("langgraph_node") if metadata else None
                    tname = getattr(message_chunk, "name", None)
                    if tname and tname in tool_config.get_tool_names():
                        used_tools.append(tname)
                    if hasattr(message_chunk, "tool_call_chunks"):
                        for tc in message_chunk.tool_call_chunks or []:
                            n = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                            if n:
                                used_tools.append(n)
                    if node_name in ["generate", "agent"]:
                        chunk = getattr(message_chunk, 'content', '')
                        logger.info(f"Streaming chunk from {node_name}: {chunk}")
                        yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'choices': [{'index': 0, 'delta': {'content': chunk}, 'finish_reason': None}]})}\n\n"
                except Exception as chunk_error:
                    logger.error(f"Error processing stream chunk: {chunk_error}")
                    continue

            unique_tools = list(dict.fromkeys(used_tools))
            footer = _append_trace_footer("", unique_tools, 0)
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'choices': [{'index': 0, 'delta': {'content': footer}, 'finish_reason': None}]})}\n\n"
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
        except Exception as stream_error:
            logger.error(f"Stream generation error: {stream_error}")
            yield f"data: {json.dumps({'error': 'Stream processing failed'})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


# 依赖注入函数，用于获取 graph 和 tool_config
async def get_dependencies() -> Tuple[any, any]:
    if not graph or not tool_config:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "db_unavailable", "message": "Service not initialized"},
        )
    return graph, tool_config


@app.get("/health")
async def health():
    postgres_ok = False
    chroma_ok = False
    try:
        if db_connection_pool and not db_connection_pool.closed:
            with db_connection_pool.connection() as conn:
                conn.execute("SELECT 1")
            postgres_ok = True
    except Exception as e:
        logger.warning(f"health postgres check failed: {e}")
    try:
        import chromadb
        client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
        names = []
        for c in client.list_collections():
            names.append(c if isinstance(c, str) else getattr(c, "name", str(c)))
        chroma_ok = Config.CHROMADB_COLLECTION_NAME in names
    except Exception as e:
        logger.warning(f"health chroma check failed: {e}")
    status = "ok" if postgres_ok else "degraded"
    return {
        "status": status,
        "postgres": postgres_ok,
        "chroma_collection": chroma_ok,
        "chroma_name": Config.CHROMADB_COLLECTION_NAME,
        "dashscope_key_configured": bool(Config.DASHSCOPE_API_KEY),
        "langsmith": bool(os.getenv("LANGCHAIN_API_KEY", "").strip()),
        "llm_type": Config.LLM_TYPE,
        "bss": True,
    }


@app.get("/v1/orders")
async def get_orders(user_id: Optional[str] = None, _: None = Depends(verify_api_key)):
    from utils.orders import list_orders
    return list_orders(user_id)


class BssProvisionRequest(BaseModel):
    plan_name: str
    user_id: str = "anonymous"
    campus_student: bool = False
    idempotency_key: Optional[str] = None
    order_id: Optional[str] = None


@app.post("/v1/bss/provision")
async def bss_provision_api(request: BssProvisionRequest, _: None = Depends(verify_api_key)):
    from utils.bss_mock import provision

    return provision(
        request.plan_name,
        user_id=request.user_id,
        campus_student=request.campus_student,
        idempotency_key=request.idempotency_key,
        order_id=request.order_id,
    )


@app.get("/v1/bss/tickets/{ticket_id}")
async def bss_ticket_api(ticket_id: str, _: None = Depends(verify_api_key)):
    from utils.bss_mock import query_ticket

    return query_ticket(ticket_id=ticket_id)


@app.post("/v1/chat")
async def business_chat(
    request: BusinessChatRequest,
    dependencies: Tuple[any, any] = Depends(get_dependencies),
    _: None = Depends(verify_api_key),
):
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail={"error_code": "empty_message", "message": "message cannot be empty"},
        )
    graph_obj, tool_cfg = dependencies
    logger.info(
        f"business_chat user_id={request.user_id} stream={request.stream} "
        f"conversation_id={request.conversation_id}"
    )
    config = {
        "configurable": {
            "thread_id": f"{request.user_id}@@{request.conversation_id}",
            "user_id": request.user_id,
        }
    }
    try:
        if request.stream:
            return await handle_stream_response(request.message, graph_obj, config, tool_cfg)
        return await handle_non_stream_response(request.message, graph_obj, tool_cfg, config)
    except HTTPException:
        raise
    except Exception as e:
        status, code = classify_error(e)
        logger.error(f"business_chat error: {e}")
        raise HTTPException(status_code=status, detail={"error_code": code, "message": str(e)})


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    dependencies: Tuple[any, any] = Depends(get_dependencies),
    _: None = Depends(verify_api_key),
):
    try:
        graph_obj, tool_cfg = dependencies
        if not request.messages or not request.messages[-1].content:
            logger.error("Invalid request: Empty or invalid messages")
            raise HTTPException(
                status_code=400,
                detail={"error_code": "empty_message", "message": "Messages cannot be empty or invalid"},
            )
        user_input = request.messages[-1].content
        logger.info(f"The user's user_input is: {user_input}")

        config = {
            "configurable": {
                "thread_id": f"{getattr(request, 'userId', 'unknown')}@@{getattr(request, 'conversationId', 'default')}",
                "user_id": getattr(request, "userId", "unknown"),
            }
        }

        if request.stream:
            return await handle_stream_response(user_input, graph_obj, config, tool_cfg)
        return await handle_non_stream_response(user_input, graph_obj, tool_cfg, config)

    except HTTPException:
        raise
    except Exception as e:
        status, code = classify_error(e)
        logger.error(f"Error handling chat completion:\n\n {str(e)}")
        raise HTTPException(status_code=status, detail={"error_code": code, "message": str(e)})


if __name__ == "__main__":
    logger.info(f"Start the server on port {Config.PORT}")
    # uvicorn是一个用于运行ASGI应用的轻量级、超快速的ASGI服务器实现
    # 用于部署基于FastAPI框架的异步PythonWeb应用程序
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)


