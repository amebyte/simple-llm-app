"""基于 lark-oapi SDK 使用 WebSocket 长连接的飞书/Lark 渠道实现。"""

import asyncio
import json
import threading
from dataclasses import dataclass
from loguru import logger
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)
import agent_loop as agent  # 导入 AI 逻辑模块

@dataclass
class FeishuConfig:
    """飞书渠道配置"""
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""

class FeishuChannel:
    """极简版飞书 WebSocket 长连接机器人"""
    
    def __init__(self, config: FeishuConfig):
        self.config = config
        self._client = lark.Client.builder() \
            .app_id(config.app_id) \
            .app_secret(config.app_secret) \
            .build()

    async def start(self) -> None:
        """启动长连接"""
        handler = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key, 
            self.config.verification_token
        ).register_p2_im_message_receive_v1(self._on_message).build()

        def run_ws():
            # 为 WebSocket 客户端所在线程设置专属的事件循环，避免报错
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            import lark_oapi.ws.client
            lark_oapi.ws.client.loop = loop
            
            ws_client = lark.ws.Client(
                self.config.app_id, 
                self.config.app_secret, 
                event_handler=handler
            )
            ws_client.start()

        threading.Thread(target=run_ws, daemon=True).start()
        logger.info("✅ 飞书极简版机器人已启动 (WebSocket)")

        # 保持主协程存活
        while True:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        logger.info("飞书机器人已停止")

    def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        """接收到消息时的回调"""
        msg = data.event.message
        # 只处理用户发送的纯文本消息
        if data.event.sender.sender_type == "bot" or msg.message_type != "text":
            return

        content = json.loads(msg.content).get("text", "")
        if not content:
            return

        # 启动独立线程处理 AI 逻辑并回复，防止阻塞 WebSocket 接收循环
        threading.Thread(
            target=self._process_and_reply, 
            args=(msg.chat_id, content)
        ).start()

    def _process_and_reply(self, chat_id: str, content: str) -> None:
        """调用 temp.py 获取回复并调用飞书 API 发送"""
        try:
            history = [
                {"role": "system", "content": getattr(agent, "SYSTEM", "你是一个助手")},
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