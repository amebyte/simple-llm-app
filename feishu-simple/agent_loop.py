import os
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量（如 DEEPSEEK_API_KEY）
load_dotenv()

# ---------- 工具定义 ----------
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要读取的文件路径"},
                    "encoding": {"type": "string", "enum": ["utf-8", "gbk"], "description": "文件编码格式"}
                },
                "required": ["path"]
            }
        }
    }
]

# ---------- 工具实现 ----------
class ReadFileTool:
    def execute(self, path: str, encoding: str = "utf-8") -> str:
        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return f"❌ 文件不存在: {path}"
            return file_path.read_text(encoding=encoding)
        except Exception as e:
            return f"❌ 读取失败: {str(e)}"

file_tool = ReadFileTool()

# ---------- 初始化客户端 ----------
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

SYSTEM = "你是一个文件读取助手，必要时可以调用工具帮助用户读取文件内容。"
MODEL = "deepseek-chat"

# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    while True:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        msg = response.choices[0].message
        
        # 添加助手的回复
        messages.append(msg)
        
        # 如果模型没有调用工具，说明已完成任务
        if not msg.tool_calls:
            return msg.content

        # 否则，执行每个工具调用并收集结果
        for tool_call in msg.tool_calls:
            if tool_call.function.name == "read_file":
                args = json.loads(tool_call.function.arguments)
                print(f"\033[33m🔧 调用工具: {tool_call.function.name}, 参数: {args}\033[0m")
                result = file_tool.execute(**args)
                print(f"✅ 工具执行结果:\n{result[:200]}\n")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result
                })

if __name__ == "__main__":
    history = [
        {"role": "system", "content": "你是一个文件读取助手，必要时可以调用工具帮助用户读取文件内容。"}
    ]
    while True:
        try:
            query = input("\033[36m用户 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        
        history.append({"role": "user", "content": query})
        final_answer = agent_loop(history)
        
        if final_answer:
            print(f"\033[32m助手: {final_answer}\033[0m\n")