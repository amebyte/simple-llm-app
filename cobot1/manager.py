"""用于协调聊天频道的频道管理器。"""

import asyncio
from typing import Any

from loguru import logger
from message_bus import MessageBus
from feishu import FeishuChannel


class ChannelManager:
    """
    管理聊天频道并协调消息路由。

    职责：
    - 注册频道实例（飞书、微信 等）
    - 启动/停止频道
    - 将出站消息路由到正确的频道
    """

    def __init__(self, bus: MessageBus):
        self.bus = bus
        self.channels: dict[str, FeishuChannel] = {}
        self._dispatch_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # 注册渠道
    # ------------------------------------------------------------------

    def register(self, channel: FeishuChannel) -> None:
        """注册一个渠道适配器。要求该适配器必须有 name 属性和 send 方法。"""
        self.channels[channel.name] = channel
        logger.info(f"Channel registered: {channel.name}")

    # ------------------------------------------------------------------
    # 启动 / 停止
    # ------------------------------------------------------------------

    async def start_all(self) -> None:
        """启动所有已注册的频道以及出站分发器。"""
        if not self.channels:
            logger.warning("No channels registered")
            return

        # 先启动出站分发器协程（确保一有出站消息就能被处理）
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # 并发启动所有渠道（每个渠道的 start 方法负责建立长连接或监听 Webhook）
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"Starting {name} channel...")
            # await channel.start()
            tasks.append(asyncio.create_task(channel.start()))

        # 注意：通常渠道的 start 会永久阻塞（如 WebSocket 循环），因此 gather 不会返回
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """优雅停止所有渠道和出站分发器。"""
        logger.info("Stopping all channels...")

        # 第一阶段：取消出站分发器任务
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        # 第二阶段：逐个停止渠道（每个渠道的 stop 方法应关闭连接、释放资源）
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

    # ------------------------------------------------------------------
    # 出向消息派发（拉模式）
    # ------------------------------------------------------------------

    async def _dispatch_outbound(self) -> None:
        """
        出站分发器：持续消费 outbound 队列，将消息发送到对应的渠道。
        这是一个后台协程，在 start_all 时启动。
        """
        logger.info("Outbound dispatcher started")

        while True:
            try:
                # 可中断阻塞读取，每隔1秒检查一次取消信号
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0,
                )
                # 根据消息中的 channel 字段找到对应的适配器
                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        # 调用适配器的 send 方法（各渠道自己实现转换和发送逻辑）
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                else:
                    logger.warning(f"Unknown channel: {msg.channel}")

            except asyncio.TimeoutError:
                # 超时不是错误，只是没有消息，继续循环
                continue
            except asyncio.CancelledError:
                break