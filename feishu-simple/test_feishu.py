from loguru import logger
from feishu2 import FeishuChannel, FeishuConfig

async def main():
    # 1. 填入你的飞书机器人凭证
    config = FeishuConfig(
        app_id="cli_a95a40acebf8dbd7",         # 替换为真实的 App ID
        app_secret="jhpD9BKbL7corqa8BqRnpbwHzd2sEQGO",    # 替换为真实的 App Secret
        encrypt_key="",                      # 如果飞书后台配置了 Encrypt Key 则填入，否则留空
        verification_token=""                # 如果配置了 Verification Token 则填入，否则留空
    )
    
    # 2. 初始化频道并启动长连接
    channel = FeishuChannel(config=config)
    
    logger.info("正在启动飞书机器人长连接...")
    
    # 3. 启动并保持运行
    try:
        await channel.start()
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭...")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
