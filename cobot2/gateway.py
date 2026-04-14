import asyncio
import os
import sys

from dotenv import load_dotenv
from loguru import logger

# 将当前目录加入模块搜索路径（方便直接 python gateway.py 运行）
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

# ---------- 日志格式 ----------
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    level="INFO",
)


def main() -> None:
    """启动 mini OpenClaw demo gateway。"""

    # ── 1. 读取飞书配置 ──────────────────────────────────────────────
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        logger.error(
            "请先在 .env 中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET"
        )
        sys.exit(1)

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        logger.error("请先在 .env 中配置 DEEPSEEK_API_KEY")
        sys.exit(1)

    # ── 2. 组装各组件 ────────────────────────────────────────────────
    from message_bus import MessageBus
    from loop import AgentLoop
    from manager import ChannelManager
    from feishu import FeishuChannel, FeishuConfig

    bus = MessageBus()

    agent = AgentLoop(
        bus=bus,
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        max_iterations=20,
    )

    feishu_cfg = FeishuConfig(app_id=app_id, app_secret=app_secret)
    feishu_channel = FeishuChannel(config=feishu_cfg, bus=bus)

    channels = ChannelManager(bus=bus)
    channels.register(feishu_channel)

    logger.info("🤖 Mini OpenClaw gateway starting...")
    logger.info(f"   渠道: {channels.enabled_channels}")
    logger.info(f"   模型: {agent.model}")

    # ── 3. 并发运行 ──────────────────────────────────────────────────
    async def run() -> None:
        try:
            await asyncio.gather(
                agent.run(),          # 持续消费 inbound 队列，调用 LLM
                channels.start_all(), # 飞书长连接 + 出向派发器
            )
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Shutting down...")
            agent.stop()
            await channels.stop_all()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Bye!")


if __name__ == "__main__":
    main()