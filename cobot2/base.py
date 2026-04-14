"""聊天平台的基础通道接口"""

from abc import ABC, abstractmethod
from typing import Any

from events import InboundMessage, OutboundMessage
from message_bus import MessageBus


class BaseChannel(ABC):
    """
    聊天通道实现的抽象基类。
    
    每个通道（Telegram、Discord 等）都应实现此接口，
    以便与 nanobot 消息总线集成。
    """
    
    name: str = "base"
    
    def __init__(self, config: Any, bus: MessageBus):
        """
        初始化通道。
        
        参数:
            config: 通道特定的配置。
            bus: 用于通信的消息总线。
        """
        self.config = config
        self.bus = bus
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """
        启动通道并开始监听消息。
        
        这应该是一个长期运行的异步任务，负责：
        1. 连接到聊天平台
        2. 监听传入的消息
        3. 通过 _handle_message() 将消息转发到总线
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止通道并清理资源。"""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        通过此通道发送消息。
        
        参数:
            msg: 要发送的消息。
        """
        pass
    
    def is_allowed(self, sender_id: str) -> bool:
        """
        检查发送者是否被允许使用此机器人。
        
        参数:
            sender_id: 发送者的标识符。
        
        返回:
            允许返回 True，否则返回 False。
        """
        allow_list = getattr(self.config, "allow_from", [])
        
        # 如果没有白名单，允许所有人
        if not allow_list:
            return True
        
        return str(sender_id) in allow_list
    
    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
    ) -> None:
        """
        处理来自聊天平台的传入消息。
        
        此方法检查权限并将消息转发到总线。
        
        参数:
            sender_id: 发送者的标识符。
            chat_id: 聊天/通道的标识符。
            content: 消息文本内容。
        """
        if not self.is_allowed(sender_id):
            return
        
        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content
        )
        
        await self.bus.publish_inbound(msg)
    
    @property
    def is_running(self) -> bool:
        """检查通道是否正在运行。"""
        return self._running