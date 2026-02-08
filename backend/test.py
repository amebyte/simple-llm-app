import json
import asyncio
from llm_app import LLMApp
from models import ChatRequest, ChatMessage


# 测试
llmApp = LLMApp()

# 模拟聊天历史
chat_history = [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮助你的吗？"},
]
# 模拟用户输入
user_input = "请介绍一下人工智能"

async def chat_stream(request: ChatRequest):
    # 1. 发送开始事件
    yield f"data: {json.dumps({'type': 'start'})}\n\n"
    await asyncio.sleep(0.01) # 让出控制权
    
    full_response = ""
    
    # 2. 生成并发送 token
    for token in llmApp.stream_chat(request.message, request.chat_history):
        full_response += token
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        await asyncio.sleep(0.01)
    
    # 3. 发送结束事件
    yield f"data: {json.dumps({'type': 'end', 'full_response': full_response})}\n\n"

# 异步测试函数
async def test_chat_stream():
    # 使用 Pydantic 模型实现数据序列化和反序列化（即将JSON数据转换为Python对象）
    request = ChatRequest(message=user_input, chat_history=chat_history)
    async for chunk in chat_stream(request):
        print(chunk)
# 在异步编程中，我们使用asyncio.run()来运行一个异步函数（coroutine）作为程序的入口点。
asyncio.run(test_chat_stream())