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
from firecrawl import FirecrawlApp, ScrapeOptions
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

if not FIRECRAWL_API_KEY:
    logger.error("环境变量中未设置 FIRECRAWL_API_KEY。")
    raise EnvironmentError("请设置 FIRECRAWL_API_KEY 环境变量。")

if not SUPABASE_TOKEN:
    logger.error("环境变量中未设置 SUPABASE_ACCESS_TOKEN。")
    raise EnvironmentError("请设置 SUPABASE_ACCESS_TOKEN 环境变量。")

firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)


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
            lambda: firecrawl_app.crawl_url(
                url,
                limit=limit,
                scrape_options=ScrapeOptions(formats=["text", "markdown"])
            )
        )
        logger.info("Firecrawl 返回了 %d 个页面", len(result))
        return result
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
    server = MCPServerStdio(
        "npx",
        args=["-y", "@supabase/mcp-server-supabase@latest", "--access-token", SUPABASE_TOKEN],
    )
    await server.__aenter__()

    try:
        supabase_tools = await build_livekit_tools(server)
        tools = [firecrawl_search] + supabase_tools

        agent = Agent(
            instructions=(
                "您可以通过 `firecrawl_search` 执行实时网络搜索，"
                "或通过 Supabase MCP 工具执行数据库查询。"
                "根据用户需要新鲜的网络数据（新闻、外部事实）"
                "还是内部 Supabase 数据来选择合适的工具。"
            ),
            tools=tools,
        )

        session = AgentSession(
            vad=silero.VAD.load(min_silence_duration=0.1),
            stt=assemblyai.STT(word_boost=["Supabase"]),
            llm=openai.LLM(model="gpt-4o"),
            tts=openai.TTS(voice="ash"),
        )

        await session.start(agent=agent, room=ctx.room)
        await session.generate_reply(instructions="你好！我今天能为您做些什么？")

        # 保持会话活动直到取消
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("会话已取消，正在关闭。")

    finally:
        await server.__aexit__(None, None, None)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
