"""
MCP 语音智能体，将查询路由到 Firecrawl 网络搜索或通过 MCP 路由到 Supabase。
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
from typing import Any, Callable, List, Optional

import inspect
from dotenv import load_dotenv
from firecrawl import Firecrawl
from pydantic_ai.mcp import MCPServerStdio

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import assemblyai, openai, silero

# ------------------------------------------------------------------------------
# 配置和日志
# ------------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
SUPABASE_TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # 可选：用于中转站等自定义 API 端点
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "Qwen/Qwen2.5-7B-Instruct")  # OpenAI 模型名称（需支持函数调用）
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")  # Ollama 模型名称
USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"  # 是否强制使用本地 Ollama（优先级高于 OpenAI）
TTS_VOICE = os.getenv("TTS_VOICE", "FunAudioLLM/CosyVoice2-0.5B:claire")  # 硅基流动 TTS 语音

if not FIRECRAWL_API_KEY:
    logger.error("环境变量中未设置 FIRECRAWL_API_KEY。")
    raise EnvironmentError("请设置 FIRECRAWL_API_KEY 环境变量。")

if not SUPABASE_TOKEN:
    logger.warning("环境变量中未设置 SUPABASE_ACCESS_TOKEN。")
    logger.warning("Supabase MCP 集成将不可用，仅使用 Firecrawl 搜索功能。")

# 检查是否使用 OpenAI API 或本地 Ollama
if USE_LOCAL_LLM:
    logger.info("USE_LOCAL_LLM=true，强制使用本地 Ollama 模型。")
    USE_OPENAI = False
elif OPENAI_API_KEY:
    logger.info("检测到 OPENAI_API_KEY，将使用 OpenAI API。")
    USE_OPENAI = True
else:
    logger.info("未检测到 OPENAI_API_KEY，将使用本地 Ollama 模型。")
    USE_OPENAI = False

firecrawl_app = Firecrawl(api_key=FIRECRAWL_API_KEY)


def _py_type(schema: dict) -> Any:
    """将 JSON schema 类型转换为 Python 类型注解。"""
    t = schema.get("type")
    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
    }

    if isinstance(t, list):
        if "array" in t:
            return List[_py_type(schema.get("items", {}))]
        t = t[0]

    if isinstance(t, str) and t in mapping:
        return mapping[t]
    if t == "array":
        return List[_py_type(schema.get("items", {}))]

    return Any


def schema_to_google_docstring(description: str, schema: dict) -> str:
    """
    从 JSON schema 生成 Google 风格的文档字符串部分。
    """
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = [description or "", "参数:"]

    for name, prop in props.items():
        t = prop.get("type", "Any")
        if isinstance(t, list):
            if "array" in t:
                subtype = prop.get("items", {}).get("type", "Any")
                py_type = f"List[{subtype.capitalize()}]"
            else:
                py_type = t[0].capitalize()
        elif t == "array":
            subtype = prop.get("items", {}).get("type", "Any")
            py_type = f"List[{subtype.capitalize()}]"
        else:
            py_type = t.capitalize()

        if name not in required:
            py_type = f"Optional[{py_type}]"

        desc = prop.get("description", "")
        lines.append(f"    {name} ({py_type}): {desc}")

    return "\n".join(lines)


@function_tool
async def firecrawl_search(
    context: RunContext,
    query: str,
    limit: int = 5
) -> List[str]:
    """
    通过 Firecrawl 搜索网络。

    参数:
        context (RunContext): LiveKit 运行时上下文。
        query (str): 搜索查询字符串。
        limit (int): 要爬取的最大页面数。

    返回:
        List[str]: 原始页面内容。
    """
    url = f"https://www.google.com/search?q={query}"
    logger.debug("开始对 URL 进行 Firecrawl 搜索：%s（限制=%d）", url, limit)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: firecrawl_app.crawl(
                url=url,
                limit=limit,
                formats=["markdown", "text"]
            )
        )
        # 新版 API 返回的是 job 对象，包含 data 字段
        data = result.data if hasattr(result, 'data') else result
        logger.info("Firecrawl 返回了 %d 个页面", len(data) if isinstance(data, list) else 1)
        return data
    except Exception as e:
        logger.error("Firecrawl 搜索失败：%s", e, exc_info=True)
        return []


async def build_livekit_tools(server: MCPServerStdio) -> List[Callable]:
    """
    从 Supabase MCP 服务器构建 LiveKit 工具。
    """
    tools: List[Callable] = []
    all_tools = await server.list_tools()
    logger.info("找到 %d 个 MCP 工具", len(all_tools))

    for td in all_tools:
        if td.name == "deploy_edge_function":
            logger.warning("跳过工具 %s", td.name)
            continue

        schema = copy.deepcopy(td.parameters_json_schema)
        if td.name == "list_tables":
            props = schema.setdefault("properties", {})
            props["schemas"] = {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "default": []
            }
            schema["required"] = [r for r in schema.get("required", []) if r != "schemas"]

        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        def make_proxy(
            tool_def=td,
            _props=props,
            _required=required,
            _schema=schema
        ) -> Callable:
            async def proxy(context: RunContext, **kwargs):
                # 将数组参数的 None 转换为 []
                for k, v in list(kwargs.items()):
                    if ((_props[k].get("type") == "array"
                         or "array" in (_props[k].get("type") or []))
                            and v is None):
                        kwargs[k] = []

                response = await server.call_tool(tool_def.name, arguments=kwargs or None)
                if isinstance(response, list):
                    return response
                if hasattr(response, "content") and response.content:
                    text = response.content[0].text
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
                return response

            # 从 schema 构建函数签名
            params = [
                inspect.Parameter("context", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=RunContext)
            ]
            ann = {"context": RunContext}

            for name, ps in _props.items():
                default = ps.get("default", inspect._empty if name in required else None)
                params.append(
                    inspect.Parameter(
                        name,
                        inspect.Parameter.KEYWORD_ONLY,
                        annotation=_py_type(ps),
                        default=default,
                    )
                )
                ann[name] = _py_type(ps)

            proxy.__signature__ = inspect.Signature(params)
            proxy.__annotations__ = ann
            proxy.__name__ = tool_def.name
            proxy.__doc__ = schema_to_google_docstring(tool_def.description or "", _schema)
            return function_tool(proxy)

        tools.append(make_proxy())

    return tools


async def entrypoint(ctx: JobContext) -> None:
    """
    LiveKit 智能体的主入口点。
    """
    await ctx.connect()
    
    # 尝试连接 Supabase MCP 服务器（可选）
    supabase_tools = []
    server = None
    
    if SUPABASE_TOKEN:
        try:
            logger.info("尝试连接 Supabase MCP 服务器...")
            server = MCPServerStdio(
                "npx",
                args=["-y", "@supabase/mcp-server-postgrest@latest", "--access-token", SUPABASE_TOKEN],
            )
            await server.__aenter__()
            supabase_tools = await build_livekit_tools(server)
            logger.info(f"Supabase MCP 连接成功，获得 {len(supabase_tools)} 个工具。")
        except Exception as e:
            logger.warning(f"Supabase MCP 连接失败：{e}")
            logger.warning("将继续使用 Firecrawl 搜索功能。")
            server = None
    else:
        logger.info("未配置 SUPABASE_ACCESS_TOKEN，跳过 Supabase MCP 连接。")
    
    # 构建工具列表
    tools = [firecrawl_search] + supabase_tools
    
    # 构建 Agent 指令
    if supabase_tools:
        instructions = (
            "您可以通过 `firecrawl_search` 执行实时网络搜索，"
            "或通过 Supabase MCP 工具执行数据库查询。"
            "根据用户需要新鲜的网络数据（新闻、外部事实）"
            "还是内部 Supabase 数据来选择合适的工具。"
        )
    else:
        instructions = (
            "您可以通过 `firecrawl_search` 执行实时网络搜索，"
            "获取最新的网络信息、新闻和外部事实。"
        )
    
    agent = Agent(
        instructions=instructions,
        tools=tools,
    )

    try:

        # 根据配置选择 LLM
        if USE_OPENAI:
            if OPENAI_BASE_URL:
                llm = openai.LLM(model=OPENAI_MODEL, base_url=OPENAI_BASE_URL)
                logger.info(f"使用自定义 OpenAI API 端点：{OPENAI_BASE_URL}")
            else:
                llm = openai.LLM(model=OPENAI_MODEL)
                logger.info("使用官方 OpenAI API。")
            logger.info(f"使用 OpenAI {OPENAI_MODEL} 模型。")
        else:
            # 使用 Ollama（通过 openai 插件提供）
            llm = openai.LLM.with_ollama(
                model=OLLAMA_MODEL,
                base_url="http://localhost:11434/v1"
            )
            logger.info(f"使用本地 Ollama {OLLAMA_MODEL} 模型。")
        
        # 使用硅基流动 TTS（通过 OpenAI 兼容接口）
        if not OPENAI_API_KEY:
            logger.error("TTS 配置错误：未设置 OPENAI_API_KEY。")
            logger.error("请在 .env 文件中配置：OPENAI_API_KEY=your-siliconflow-key")
            raise EnvironmentError("需要配置 OPENAI_API_KEY 用于硅基流动 TTS。")
        
        if OPENAI_BASE_URL:
            tts = openai.TTS(voice=TTS_VOICE, base_url=OPENAI_BASE_URL)
        else:
            tts = openai.TTS(voice=TTS_VOICE)
        logger.info(f"使用硅基流动 TTS（语音: {TTS_VOICE}）。")
        
        session = AgentSession(
            vad=silero.VAD.load(min_silence_duration=0.1),
            stt=assemblyai.STT(),
            llm=llm,
            tts=tts,
        )

        await session.start(agent=agent, room=ctx.room)
        # await session.generate_reply(instructions="你好！我今天能为您做些什么？")  # 跳过初始问候，直接开始对话
        logger.info("Agent 已就绪，等待用户输入。按 Ctrl+B 切换文本/音频模式。")

        # 保持会话活动直到取消
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("会话已取消，正在关闭。")

    finally:
        if server:
            await server.__aexit__(None, None, None)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
