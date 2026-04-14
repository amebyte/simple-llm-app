"""用于协调聊天频道的频道管理器。"""

import asyncio
from typing import Any

from loguru import logger

from events import OutboundMessage
from message_bus import MessageBus
from base import BaseChannel


class ChannelManager:
    """
    管理聊天频道并协调消息路由。

    职责：
    - 注册频道实例（飞书、Telegram 等）
    - 启动/停止频道
    - 将出站消息路由到正确的频道
    """

    def __init__(self, bus: MessageBus):
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # 注册渠道
    # ------------------------------------------------------------------

    def register(self, channel: BaseChannel) -> None:
        """按名称注册频道实例。"""
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

        # 先启动出向派发器（确保出向链路在渠道上线前就绪）
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # 并发启动所有渠道
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"Starting {name} channel...")
            await channel.start()
            # tasks.append(asyncio.create_task(channel.start()))

        # 等待所有渠道任务（正常情况下永不结束）
        # await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """停止所有频道和分发器。"""
        logger.info("Stopping all channels...")

        # 第一阶段：取消派发器
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        # 第二阶段：逐一停止渠道
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
        """将出站消息分发到相应的频道。"""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0,
                )

                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                else:
                    logger.warning(f"Unknown channel: {msg.channel}")

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # ------------------------------------------------------------------
    # 辅助接口
    # ------------------------------------------------------------------

    def get_channel(self, name: str) -> BaseChannel | None:
        """按名称获取频道。"""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """获取所有频道的状态。"""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running,
            }
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """获取已注册的频道名称列表。"""
        return list(self.channels.keys())