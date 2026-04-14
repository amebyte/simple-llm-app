"""用于解耦频道与智能体通信的异步消息队列"""
import asyncio
from loguru import logger
from events import InboundMessage, OutboundMessage

class MessageBus:
    """
    异步消息总线，用于将聊天频道与智能体核心解耦。
    频道将消息推送到入站队列，智能体处理它们并将响应推送到出站队列。
    """
    def __init__(self):
        # 入站异步队列
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        # 出站异步队列
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
    
    async def publish_inbound(self, msg: InboundMessage) -> None:
        """将来自频道的消息发布给智能体"""
        await self.inbound.put(msg)
    
    async def consume_inbound(self) -> InboundMessage:
        """消费下一条入站消息（阻塞直到有消息可用）"""
        return await self.inbound.get()
    
    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """将智能体的响应发布给频道"""
        await self.outbound.put(msg)
    
    async def consume_outbound(self) -> OutboundMessage:
        """消费下一条出站消息（阻塞直到有消息可用）"""
        return await self.outbound.get()