from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class InboundMessage:
    """从聊天频道接收到的消息"""
    channel: str  # 用于区分来源，后续发送回复时需要知道应该调用哪个 IM 的 API（feishu、wechat）
    sender_id: str  # 用户标识符
    chat_id: str  # 聊天/频道标识符
    content: str  # 消息文本
    timestamp: datetime = field(default_factory=datetime.now)  # 消息时间

    @property
    def session_key(self) -> str:
        """用于会话标识的唯一键"""
        return f"{self.channel}:{self.chat_id}"

@dataclass
class OutboundMessage:
    """要发送到聊天频道的消息"""
    
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None # 支持引用回复，用于指明当前回复的是哪一条历史消息