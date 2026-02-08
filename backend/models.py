from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    """单条聊天消息"""
    role: str  # "user" 或 "assistant"
    content: str

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    chat_history: Optional[List[ChatMessage]] = []

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    model: str
    api_configured: bool
    timestamp: str