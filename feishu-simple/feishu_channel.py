import json
import logging
import lark_oapi as lark
from lark_oapi import ws, LogLevel, EventDispatcherHandler
from lark_oapi.api.im.v1 import *

# ---------- 1. 配置区域 ----------
# 请将下面的值替换为你自己的 App ID 和 App Secret
APP_ID = "cli_a938f2c38eb8dbc9"      # 替换为你的 App ID
APP_SECRET = "t9SAelVdeaLulI4UVCh9hZBse0dRJWsJ"  # 替换为你的 App Secret
# ------------------------------

# 配置日志，方便查看运行状态
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ---------- 2. 定义消息处理函数 ----------
# 这个函数会在每次收到新消息时被调用
def handle_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    """
    处理接收到的消息事件 (im.message.receive_v1)
    """
    # 从事件数据中解析关键信息
    # data 是一个对象，可以转为字典方便操作
    message_dict = json.loads(json.dumps(data, default=lambda x: x.__dict__))
    
    # 提取消息内容 (content 字段是 JSON 字符串，需要二次解析)
    # 注意：不同消息类型（文本、图片等）的 content 结构不同，这里只处理纯文本
    event = message_dict.get("event", {})
    message = event.get("message", {})
    content_str = message.get("content", "{}")
    
    try:
        content = json.loads(content_str)
        text = content.get("text", "")
    except json.JSONDecodeError:
        text = "无法解析的消息内容"
    
    # 提取发送者信息
    sender = event.get("sender", {})
    sender_id_info = sender.get("sender_id", {})
    # 注意：open_id 是用户的唯一标识，推荐使用它来回复消息
    open_id = sender_id_info.get("open_id") 
    message_id = message.get("message_id") # 也可以使用 message_id 来回复

    logging.info(f"收到来自用户 {open_id} 的消息: {text}")

    # ---------- 3. 在这里编写你的业务逻辑 ----------
    # 例如：调用AI接口、查询数据库、执行命令等
    # 这里我们简单处理，回复一句 "已收到：{你的消息}"
    reply_text = f"已收到：{text}"
    # ------------------------------------------

    # ---------- 4. 调用飞书API发送回复 ----------
    # 4.1 创建一个API客户端
    # 【注意】飞书的长连接客户端 (ws.Client) 只能用来"接收"事件，不能用来"发送"消息！
    # 如果要主动发消息或回复消息，必须使用普通的 Open API 客户端 (lark.Client)
    client = lark.Client.builder() \
        .app_id(APP_ID) \
        .app_secret(APP_SECRET) \
        .log_level(LogLevel.INFO) \
        .build()
    
    # 4.2 构建发送消息的请求
    # 推荐使用 "回复消息" 接口，它需要 message_id
    request = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(ReplyMessageRequestBody.builder()
                      .msg_type("text")
                      .content(json.dumps({"text": reply_text}))
                      .build()) \
        .build()
    
    # 4.3 发送请求
    # 消除类型检查(linter)对 Optional 的报错
    assert client.im is not None 
    response = client.im.v1.message.reply(request)
    
    if not response.success():
        logging.error(f"回复消息失败: {response.msg}")

# ---------- 5. 初始化事件处理器 ----------
# 使用 EventDispatcherHandler 的构建器来注册我们关心的事件
# 这里只注册了 "接收消息 v1.0" 事件
event_handler = EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(handle_p2_im_message_receive_v1) \
    .build()

# ---------- 6. 启动长连接客户端 ----------
def main():
    # 创建长连接客户端
    # 参数：App ID, App Secret, 事件处理器, 日志级别
    cli = ws.Client(
        APP_ID, 
        APP_SECRET, 
        event_handler=event_handler, 
        log_level=LogLevel.INFO
    )
    
    logging.info("正在启动飞书长连接客户端...")
    # start() 方法会阻塞主线程，持续运行
    cli.start()

if __name__ == "__main__":
    main()