import os
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
# 加载环境变量（如 DEEPSEEK_API_KEY）
load_dotenv()
# ---------- 初始化客户端 ----------
# 创建 OpenAI 客户端实例，使用 DeepSeek API 密钥和基础 URL
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

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

# -- 核心模式：一个不断调用工具的 while 循环，直到模型停止 --
def agent_loop(messages: list):
    """
    核心代理循环：
    不断地调用大模型，如果模型返回了工具调用，则执行工具并将结果发回给模型，
    直到模型不再需要调用工具并返回最终文本回复为止。
    """
    while True:
        # 调用大模型，传入历史消息、工具列表，并让模型自动决定是否调用工具
        response = client.chat.completions.create(
            model="deepseek-chat", # 使用的模型名称
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        msg = response.choices[0].message
        
        # 将助手的回复（可能包含工具调用，也可能是普通文本）添加到历史记录中
        messages.append(msg)
        
        # 如果模型没有调用工具，说明已完成任务，返回模型回复的文本内容
        if not msg.tool_calls:
            return msg.content

        # 否则，模型决定调用工具，遍历所有的工具调用
        for tool_call in msg.tool_calls:
            if tool_call.function.name == "read_file":
                # 解析模型生成的工具调用参数
                args = json.loads(tool_call.function.arguments)
                print(f"\033[33m🔧 调用工具: {tool_call.function.name}, 参数: {args}\033[0m")
                # 执行工具函数
                result = file_tool.execute(**args)
                # 打印工具执行结果的前200个字符
                print(f"✅ 工具执行结果:\n{result[:200]}\n")
                # 将工具执行结果作为 tool 类型的消息追加到历史记录中
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result
                })

SYSTEM = "你是一个文件读取助手，必要时可以调用工具帮助用户读取文件内容。"

if __name__ == "__main__":
    # 初始化历史消息列表，包含系统提示词，系统提示词，用于指导助手的行为
    history = [
        {"role": "system", "content": "你是一个文件读取助手，必要时可以调用工具帮助用户读取文件内容。"}
    ]
    # 启动交互式终端会话
    while True:
        try:
            # 获取用户输入
            query = input("\033[36m用户 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            # 处理 Ctrl+D 或 Ctrl+C 退出的情况
            break
        # 处理正常退出的输入
        if query.strip().lower() in ("q", "exit", "退出"):
            break
        
        # 将用户输入追加到历史记录中
        history.append({"role": "user", "content": query})
        # 启动代理循环进行对话
        final_answer = agent_loop(history)
        
        # 打印助手给出的最终答案
        if final_answer:
            print(f"\033[32m助手: {final_answer}\033[0m\n")                