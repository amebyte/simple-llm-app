"""消息总线的事件类型"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InboundMessage:
    """从聊天通道接收到的消息"""
    
    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # 用户标识符
    chat_id: str  # 聊天/通道标识符
    content: str  # 消息文本
    timestamp: datetime = field(default_factory=datetime.now)  # 通道特定数据
    
    @property
    def session_key(self) -> str:
        """用于会话标识的唯一键"""
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """要发送到聊天通道的消息"""
    
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None