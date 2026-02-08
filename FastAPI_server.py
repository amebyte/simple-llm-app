import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llm_app import SimpleLLMApp
from models import ChatRequest, HealthResponse

app = FastAPI(title="Simple LLM Chat API")

# CORS 配置：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中建议设置为具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 LLM 应用实例
llm_app = None

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化 LLM"""
    global llm_app
    try:
        print("正在初始化 LLM 应用...")
        llm_app = SimpleLLMApp()
        print("✅ LLM 应用初始化成功")
    except Exception as e:
        print(f"❌ LLM 应用初始化失败: {e}")

@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status="healthy" if llm_app else "unhealthy",
        model="deepseek-chat",
        api_configured=llm_app is not None,
        timestamp=datetime.now().isoformat()
    )

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口"""
    if not llm_app:
        raise HTTPException(status_code=500, detail="LLM 服务未就绪")
    
    async def generate():
        try:
            # 1. 发送开始事件
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            await asyncio.sleep(0.01) # 让出控制权
            
            full_response = ""
            
            # 2. 生成并发送 token
            # 注意：llm_app.stream_chat 是同步生成器，但在 FastAPI 中可以正常工作
            # 如果需要完全异步，需要使用 AsyncChatOpenAI，这里为了简单保持同步调用
            for token in llm_app.stream_chat(request.message, request.chat_history):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                await asyncio.sleep(0.01)
            
            # 3. 发送结束事件
            yield f"data: {json.dumps({'type': 'end', 'full_response': full_response})}\n\n"
            
        except Exception as e:
            error_msg = str(e)
            print(f"生成错误: {error_msg}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)