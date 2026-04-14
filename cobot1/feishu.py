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
from events import InboundMessage, OutboundMessage
from message_bus import MessageBus

@dataclass
class FeishuConfig:
    """飞书渠道配置"""
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""

class FeishuChannel:
    """极简版飞书 WebSocket 长连接机器人"""
    name = "feishu"
    def __init__(self, config: FeishuConfig, bus: MessageBus):
        self.config = config
        self.bus = bus
        self._client = lark.Client.builder() \
            .app_id(config.app_id) \
            .app_secret(config.app_secret) \
            .build()

    async def start(self) -> None:
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

        def run_ws():
            # 为 WebSocket 客户端所在线程设置专属的事件循环，避免报错
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            import lark_oapi.ws.client
            lark_oapi.ws.client.loop = loop
            # 初始化长连接客户端
            ws_client = lark.ws.Client(
                self.config.app_id, 
                self.config.app_secret, 
                event_handler=handler
            )
            ws_client.start()
        # 在独立线程中运行飞书的 WebSocket 客户端，避免与主线程的事件循环冲突
        threading.Thread(target=run_ws, daemon=True).start()
        logger.info("✅ 飞书极简版机器人已启动 (WebSocket)")

        # 保持主协程存活
        while True:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        logger.info("飞书机器人已停止")

    async def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        """接收到消息时的回调"""
        msg = data.event.message
        sender = data.event.sender
        # 只处理用户发送的纯文本消息
        if data.event.sender.sender_type == "bot" or msg.message_type != "text":
            return

        content = json.loads(msg.content).get("text", "")
        if not content:
            return
        # 提取发送者信息
        sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
        # 获取用于回复的 chat_id
        chat_id = msg.chat_id
        chat_type = msg.chat_type  # "p2p" 或 "group"
        reply_to = chat_id if chat_type == "group" else sender_id
        # 将消息转发到总线
        await self._handle_message(
            sender_id=sender_id,
            chat_id=reply_to,
            content=content,
        )

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
    ) -> None:
        """
        处理来自聊天平台的传入消息。
        此方法将消息转发到总线。
        
        参数:
            sender_id: 发送者的标识符。
            chat_id: 聊天/通道的标识符。
            content: 消息文本内容。
        """
        
        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content
        )
        
        await self.bus.publish_inbound(msg)

    async def send(self, msg: OutboundMessage) -> None:
        """通过飞书发送消息。"""
        if not self._client:
            logger.warning("飞书客户端未初始化")
            return

        try:
            # 根据 chat_id 格式确定 receive_id_type
            # open_id 以 "ou_" 开头，chat_id 以 "oc_" 开头
            if msg.chat_id.startswith("oc_"):
                receive_id_type = "chat_id"
            else:
                receive_id_type = "open_id"

            # 构建文本消息内容
            content = json.dumps({"text": msg.content})

            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(msg.chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                ).build()

            # OpenAPI 调用是同步的，在线程中运行以避免阻塞
            response = await asyncio.to_thread(
                self._client.im.v1.message.create, request
            )

            if not response.success():
                logger.error(
                    f"发送飞书消息失败：code={response.code}, "
                    f"msg={response.msg}, log_id={response.get_log_id()}"
                )
            else:
                logger.debug(f"飞书消息已发送至 {msg.chat_id}")

        except Exception as e:
            logger.error(f"发送飞书消息时出错：{e}")