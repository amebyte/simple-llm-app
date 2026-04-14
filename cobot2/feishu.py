"""基于 lark-oapi SDK 使用 WebSocket 长连接的飞书/Lark 渠道实现。"""

import asyncio
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from base import BaseChannel
from events import OutboundMessage
from message_bus import MessageBus


# ---------- 配置数据类 ----------

@dataclass
class FeishuConfig:
    """飞书渠道配置。"""
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    # 白名单：允许发消息的 open_id 列表，为空则不限制
    allow_from: list[str] = field(default_factory=list)


# ---------- lark_oapi import ----------

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        CreateMessageReactionRequest,
        CreateMessageReactionRequestBody,
        P2ImMessageReceiveV1,
        Emoji,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None


# ---------- 飞书 Channel 实现 ----------

class FeishuChannel(BaseChannel):
    """
    使用 WebSocket 长连接的飞书/Lark 渠道。

    使用 WebSocket 接收事件 - 无需公网 IP 或 webhook。

    要求：
    - 飞书开放平台的 App ID 和 App Secret
    - 启用机器人能力
    - 启用事件订阅 (im.message.receive_v1)
    """

    name = "feishu"

    def __init__(self, config: FeishuConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: FeishuConfig = config
        self._client = None
        self._ws_client = None
        self._ws_thread = None
        self._processed_message_ids = set()  # 去重的消息ID集合
        self._loop = None

    async def start(self) -> None:
        """使用 WebSocket 长连接启动飞书机器人。"""
        if not FEISHU_AVAILABLE:
            logger.error("飞书 SDK 未安装。运行：pip install lark-oapi")
            return

        if not self.config.app_id or not self.config.app_secret:
            logger.error("飞书 app_id 和 app_secret 未配置")
            return

        self._running = True
        self._loop = asyncio.get_running_loop()

        # 创建用于发送消息的 Lark 客户端
        self._client = lark.Client.builder() \
            .app_id(self.config.app_id) \
            .app_secret(self.config.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # 创建事件处理器（只注册消息接收事件，忽略其他事件）
        event_handler = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key or "",
            self.config.verification_token or "",
        ).register_p2_im_message_receive_v1(
            self._on_message_sync
        ).build()

        # 在独立线程中启动 WebSocket 客户端，使用自己的事件循环
        def run_ws():
            try:
                # 在此线程中创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # 技巧：lark_oapi.ws.client 将 loop 存储为模块级变量。
                # 用新循环覆盖它，避免 "loop is already running" 错误。
                import lark_oapi.ws.client
                lark_oapi.ws.client.loop = loop

                # 在线程内部创建使用自己循环的 WebSocket 客户端
                ws_client = lark.ws.Client(
                    self.config.app_id,
                    self.config.app_secret,
                    event_handler=event_handler,
                    log_level=lark.LogLevel.INFO
                )
                self._ws_client = ws_client

                # 运行 WebSocket 连接的阻塞调用
                ws_client.start()
            except Exception as e:
                logger.error(f"飞书 WebSocket 错误：{e}")
            finally:
                loop.stop()
                loop.close()

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()

        logger.info("飞书机器人已通过 WebSocket 长连接启动")
        logger.info("无需公网 IP - 使用 WebSocket 接收事件")

        # 持续运行直到停止
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """停止飞书机器人。"""
        self._running = False
        logger.info("飞书机器人已停止")

    def _add_reaction(self, message_id: str, emoji_type: str = "SMILE") -> None:
        """
        给消息添加反应表情。

        常见的表情类型：THUMBSUP, OK, EYES, DONE, OnIt, HEART
        """
        if not self._client:
            logger.warning("无法添加反应：客户端未初始化")
            return

        try:
            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                ).build()

            response = self._client.im.v1.message_reaction.create(request)

            if not response.success():
                logger.warning(f"添加反应失败：code={response.code}, msg={response.msg}")
            else:
                logger.info(f"已向消息 {message_id} 添加 {emoji_type} 反应")
        except Exception as e:
            logger.warning(f"添加反应时出错：{e}")

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

    def _on_message_sync(self, data: "P2ImMessageReceiveV1") -> None:
        """
        同步处理接收到的消息（从 WebSocket 线程调用）。
        在主线程序事件循环中调度异步处理。
        """
        try:
            if self._loop and self._loop.is_running():
                # 在主线程序事件循环中调度异步处理器
                asyncio.run_coroutine_threadsafe(
                    self._on_message(data),
                    self._loop
                )
            else:
                # 备用方案：在新事件循环中运行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._on_message(data))
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"处理飞书消息时出错：{e}")

    async def _on_message(self, data: "P2ImMessageReceiveV1") -> None:
        """处理来自飞书的传入消息。"""
        try:
            event = data.event
            message = event.message
            sender = event.sender

            # 获取消息ID用于去重
            message_id = message.message_id
            if message_id in self._processed_message_ids:
                logger.debug(f"跳过重复消息：{message_id}")
                return
            self._processed_message_ids.add(message_id)

            # 限制去重缓存大小
            if len(self._processed_message_ids) > 1000:
                self._processed_message_ids = set(list(self._processed_message_ids)[-500:])

            # 提取发送者信息
            sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
            sender_type = sender.sender_type  # "user" 或 "bot"

            # 跳过机器人消息
            if sender_type == "bot":
                return

            # 给用户消息添加反应以表示"已读" (👍 THUMBSUP)
            self._add_reaction(message_id, "THUMBSUP")

            # 获取用于回复的 chat_id
            chat_id = message.chat_id
            chat_type = message.chat_type  # "p2p" 或 "group"

            # 解析消息内容
            content = ""
            msg_type = message.message_type

            if msg_type == "text":
                # 文本消息：{"text": "hello"}
                try:
                    content_obj = json.loads(message.content)
                    content = content_obj.get("text", "")
                except json.JSONDecodeError:
                    content = message.content or ""
            elif msg_type == "image":
                content = "[image]"
            elif msg_type == "audio":
                content = "[audio]"
            elif msg_type == "file":
                content = "[file]"
            elif msg_type == "sticker":
                content = "[sticker]"
            else:
                content = f"[{msg_type}]"

            if not content:
                return

            logger.debug(f"来自 {sender_id} 在 {chat_id} 的飞书消息：{content[:50]}...")

            # 转发到消息总线
            # 群聊使用 chat_id，私聊使用发送者的 open_id
            # 注意：当前的 base._handle_message 只接收 sender_id, chat_id, content
            # 如有需要，未来会单独传递元数据
            reply_to = chat_id if chat_type == "group" else sender_id

            await self._handle_message(
                sender_id=sender_id,
                chat_id=reply_to,
                content=content,
            )

        except Exception as e:
            logger.error(f"处理飞书消息时出错：{e}")