import os
from loguru import logger
from feishu import FeishuChannel, FeishuConfig
from message_bus import MessageBus
from loop import AgentLoop
from manager import ChannelManager

async def main():
    # 1. 填入你的飞书机器人凭证
    config = FeishuConfig(
        app_id="cli_a95a40acebf8dbd7",         # 替换为真实的 App ID
        app_secret="jhpD9BKbL7corqa8BqRnpbwHzd2sEQGO",    # 替换为真实的 App Secret
        encrypt_key="",                      # 如果飞书后台配置了 Encrypt Key 则填入，否则留空
        verification_token=""                # 如果配置了 Verification Token 则填入，否则留空
    )
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    # 2. 创建总线
    bus = MessageBus()
    # 3. 创建 Agent 循环
    agent = AgentLoop(
        bus=bus,
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        max_iterations=20,
    )
    
    # 4. 创建飞书渠道（传入总线，以便它 publish_inbound）
    feishu_channel = FeishuChannel(config=config, bus=bus)
    # 5. 创建渠道管理器，并注册飞书渠道
    channels = ChannelManager(bus=bus)
    channels.register(feishu_channel)
    
    logger.info("正在启动 Mini OpenClaw 网关...")
    
    # 6. 并发运行
    try:
        await asyncio.gather(
            agent.run(),          # 持续消费 inbound 队列，调用 LLM
            channels.start_all(), # 飞书长连接 + 出向派发器
        )
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("收到退出信号，正在关闭...")
        agent.stop()
        await channels.stop_all()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
