"""基于 lark-oapi SDK 使用 WebSocket 长连接的飞书/Lark 渠道实现。"""

import json
from dataclasses import dataclass
from loguru import logger
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)
import agent_loop as agent  # 导入本地 AI Agent 逻辑模块

@dataclass
class FeishuConfig:
    """飞书渠道配置"""
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = "" # 可选字段，空字符串表示不使用加密
    verification_token: str = "" # 可选字段，空字符串表示不验证消息来源

class FeishuChannel:
    """极简版飞书 WebSocket 长连接机器人"""
    
    def __init__(self, config: FeishuConfig):
        self.config = config
        # 构建 API Client
        self._client = lark.Client.builder() \
            .app_id(config.app_id) \
            .app_secret(config.app_secret) \
            .build()

    def start(self) -> None:
        """启动长连接"""
        # 注意：飞书的长连接客户端 (ws.Client) 只能用来"接收"事件，不能用来"发送"消息！
        # 如果要主动发消息或回复消息，必须使用普通的 Open API 客户端 (lark.Client)
        # 构建事件处理器
        builder = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key, 
            self.config.verification_token
        )
        # 注册接收消息事件处理函数 im.message.receive_v1
        handler = builder.register_p2_im_message_receive_v1(self._on_message).build()
        # 初始化长连接客户端并传入事件处理器    
        ws_client = lark.ws.Client(
            self.config.app_id, 
            self.config.app_secret, 
            event_handler=handler
        )
        # start() 方法会阻塞主线程，持续运行，直到手动关闭
        ws_client.start()

        logger.info("✅ 飞书极简版机器人已启动 (WebSocket)")

    def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        """接收到消息时的回调"""
        msg = data.event.message
        # 只处理用户发送的纯文本消息
        if data.event.sender.sender_type == "bot" or msg.message_type != "text":
            return

        content = json.loads(msg.content).get("text", "")
        if not content:
            return
        logger.info(f"收到{msg.chat_id}消息: {content}")
        # 发送消息到 AI Agent 处理并进行回复
        self._process_and_reply(msg.chat_id, content)

    def _process_and_reply(self, chat_id: str, content: str) -> None:
        """调用本地 AI Agent 获取结果并调用飞书 API 发送"""
        try:
            history = [
                {"role": "system", "content": getattr(agent, "SYSTEM", "你是一个 AI 助手")},
                {"role": "user", "content": content}
            ]
            
            # 1. 运行 AI 思考逻辑
            reply_text = agent.agent_loop(history)
            if not reply_text:
                return

            # 2. 发送回复
            receive_id_type = "chat_id" if chat_id.startswith("oc_") else "open_id"
            req = CreateMessageRequest.builder().receive_id_type(receive_id_type).request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": reply_text}))
                .build()
            ).build()
            
            resp = self._client.im.v1.message.create(req)
            if resp.success():
                logger.info(f"➡️ 成功回复消息到: {chat_id}")
            else:
                logger.error(f"❌ 回复失败: {resp.msg}")
                
        except Exception as e:
            logger.error(f"❌ 处理异常: {e}")