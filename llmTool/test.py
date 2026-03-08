import os
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量 (读取 .env 中的 DEEPSEEK_API_KEY)
load_dotenv()

class ReadFileTool:
    """读取文件内容"""
    def execute(self, path: str, encoding: str = "utf-8") -> str:
        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return f"❌ 文件不存在: {path}"
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ 读取失败: {str(e)}"


# 工具定义
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径"
                    },
                    "encoding": {
                        "type": "string",
                        "enum": ["utf-8", "gbk"],
                        "description": "文件编码格式"
                    }
                },
                "required": ["path"]
            }
        }
    }
]



"""使用 DeepSeek API 和 Function Calling 实现文件读取助手"""
# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),  # 从环境变量获取API密钥
    base_url="https://api.deepseek.com"  # 指定DeepSeek API地址
)

# 初始化工具实例
file_tool = ReadFileTool()

# 模拟构建消息历史
messages = [
    {"role": "system", "content": "你是一个文件读取助手,必要时可以调用工具帮助用户读取文件内容。"}
]

# 用户输入
user_input = "帮我读一下 file.txt"
print(f"👤 用户: {user_input}\n")
messages.append({"role": "user", "content": user_input})

# 第一次调用 - 让 LLM 决定是否需要调用工具
print("🤖 正在请求 AI API...")
response = client.chat.completions.create(
    model="deepseek-chat",
    temperature=0.5,
    messages=messages,
    tools=tools, # 通过 `tools` 参数传入上述工具定义
    tool_choice="auto"  # "auto"：模型自主决定是否调用工具（默认）、"none"：禁止调用工具
)

msg = response.choices[0].message
messages.append(msg.model_dump())

# 检查是否需要调用工具
if msg.tool_calls:
    print(f"🔧 LLM 决定调用工具: {len(msg.tool_calls)} 个\n")
    
    for tool_call in msg.tool_calls:
        if tool_call.function.name == "read_file":
            print(f"📄 调用工具: {tool_call.function.name}")
            print(f"📝 参数: {tool_call.function.arguments}\n")
            
            # 解析参数并调用实际的工具函数
            args = json.loads(tool_call.function.arguments)
            result = file_tool.execute(**args)
            
            print(f"✅ 工具执行结果:\n{result}\n")
            
            # 将工具执行结果添加到消息历史
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })
    
    # 第二次调用 - 让 LLM 基于工具结果生成最终回答
    print("🤖 正在生成最终回答...\n")
    second_response = client.chat.completions.create(
        model="deepseek-chat",
        temperature=0.5,
        messages=messages
    )
    
    final_msg = second_response.choices[0].message
    print(f"💬 助手: {final_msg.content}\n")
else:
    # 如果不需要调用工具,直接输出回答
    print(f"💬 助手: {msg.content}")