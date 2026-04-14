import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
from loguru import logger
from openai import AsyncOpenAI

from events import InboundMessage, OutboundMessage
from message_bus import MessageBus

load_dotenv()

# ---------- 内置工具定义 ----------
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文本文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "encoding": {
                        "type": "string",
                        "enum": ["utf-8", "gbk"],
                        "description": "文件编码，默认 utf-8",
                    },
                },
                "required": ["path"],
            },
        },
    }
]


def _execute_tool(name: str, arguments: dict) -> str:
    """同步执行内置工具，返回字符串结果。"""
    if name == "read_file":
        from pathlib import Path

        path = arguments.get("path", "")
        encoding = arguments.get("encoding", "utf-8")
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return f"❌ 文件不存在: {path}"
            return p.read_text(encoding=encoding)
        except Exception as e:
            return f"❌ 读取失败: {e}"
    return f"❌ 未知工具: {name}"

# ---------- 会话历史管理（按 session_key 隔离） ----------
# 全局字典：存储所有会话的对话历史
# - Key: session_key，用于唯一标识一个会话（例如 "feishu:chat_id"）
# - Value: 消息列表，每个元素是 OpenAI API 兼容的消息字典（包含 role, content 等字段）
_sessions: dict[str, list[dict]] = {}

# 系统提示词：定义 AI 助手的角色、能力和行为准则
SYSTEM_PROMPT = (
    "你是一个智能助手，可以通过工具帮助用户完成任务。"
    "请简洁、准确地回答用户问题。"
)
# 获取会话历史
def _get_history(session_key: str) -> list[dict]:
    # 若为新会话，自动初始化一条包含 system prompt 的消息
    if session_key not in _sessions:
        _sessions[session_key] = [{"role": "system", "content": SYSTEM_PROMPT}]
    # 返回该会话的历史列表（引用，允许外部修改）
    return _sessions[session_key]

class AgentLoop:
    """
    智能体循环是核心处理引擎。

    它的功能：
    1. 从总线接收消息
    2. 维护每个会话的对话历史
    3. 调用 LLM（通过 OpenAI 兼容 API，例如 DeepSeek）
    4. 循环执行工具调用，直到模型停止
    5. 通过总线发送响应
    """

    def __init__(
        self,
        bus: MessageBus,
        max_iterations: int = 200,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ):
        self.bus = bus
        # 最大工具调用轮次，防止死循环
        self.max_iterations = max_iterations
        self.model = model
        self._running = False
        # 初始化 OpenAI异步客户端 兼容客户端（如 DeepSeek）
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url=base_url,
        )

    # ------------------------------------------------------------------
    # 主循环：持续消费 入站异步队列
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """运行智能体循环，处理来自总线的消息。"""
        self._running = True
        logger.info("Agent loop started")

        while self._running:
            try:
                # 从入站队列消费下一条消息，设置超时以便能定期检查 _running 标志
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0,
                )
                try:
                    # 处理消息并获取响应
                    response = await self._process_message(msg)
                    if response:
                        # 将响应发布到出站队列
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=f"抱歉，处理消息时出错：{e}",
                        )
                    )
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        """停止智能体循环。"""
        self._running = False
        logger.info("Agent loop stopping")

    # ------------------------------------------------------------------
    # 单条消息处理：tool-call 循环
    # ------------------------------------------------------------------

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        使用 OpenAI 工具调用循环处理单条入站消息。

        持续调用 LLM 并执行工具，直到模型返回纯文本响应（无 tool_calls），
        或达到最大迭代次数为止。
        """
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")

        # 1. 获取当前会话的历史，并追加用户消息
        messages = _get_history(msg.session_key)
        messages.append({"role": "user", "content": msg.content})

        final_content: str | None = None
        # 2. 进入工具调用循环（最多 max_iterations 次）
        for iteration in range(self.max_iterations):
            # 3. 调用 LLM（异步非阻塞）
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages, 
                tools=TOOLS,
                tool_choice="auto",
            )
            assistant_msg = response.choices[0].message

            # 将助手消息追加到历史
            messages.append(assistant_msg)

            # 4. 如果没有 tool_calls，说明任务完成
            if not assistant_msg.tool_calls:
                final_content = assistant_msg.content or ""
                break

            # 5. 执行所有工具调用，并将结果以 role=tool 追加到历史记录
            for tool_call in assistant_msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                logger.debug(f"Executing tool: {name}, args: {args}")

                result = _execute_tool(name, args)
                logger.debug(f"Tool result: {result[:100]}")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": result,
                    }
                )
        else:
            # 达到最大迭代次数
            final_content = "已达到最大处理轮次，无法给出最终答案。"

        if final_content is None:
            final_content = "处理完成，但没有内容返回。"
        # 6. 构造出站消息返回给用户
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
        )