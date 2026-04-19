import os
import json
import subprocess
import sys
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

# ---------- 本地工具定义 ----------
tools = []

# ---------- MCP 客户端 ----------
class MCPClient:
    def __init__(self, server_command):
        self.server_command = server_command
        self.process = None
        self.request_id = 0
        self.initialized = False

    def start(self):
        print("Starting MCP server...")
        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )
        # 发送初始化请求
        self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "agent-loop", "version": "1.0.0"}
        })
        self.initialized = True
        print("MCP server connected successfully")

    def send_request(self, method, params=None):
        if not self.process:
            raise Exception("MCP server not started")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            # 简单的读取方式，兼容 Windows
            import time
            start_time = time.time()
            response_line = ""
            
            while time.time() - start_time < 5:
                # 尝试读取一行
                response_line = self.process.stdout.readline()
                if response_line and response_line.strip():
                    break
                time.sleep(0.1)
            
            if not response_line or not response_line.strip():
                # 检查是否有错误输出
                stderr_output = self.process.stderr.read()
                if stderr_output:
                    raise Exception(f"MCP server error: {stderr_output}")
                raise Exception("No response from MCP server")
            
            return json.loads(response_line)
        except Exception as e:
            raise Exception(f"MCP request failed: {e}")

    def list_tools(self):
        result = self.send_request("tools/list")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name, arguments):
        result = self.send_request("tools/call", {"name": name, "arguments": arguments})
        tool_result = result.get("result", {})
        content_parts = tool_result.get("content", [])
        return "\n".join(part.get("text", "") for part in content_parts)

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                self.process.kill()
                self.process.wait()

try:
    # 初始化 MCP 客户端
    mcp_client = MCPClient(["node", "mcp-server.js"])
    mcp_client.start()

    # 获取 MCP 工具列表并转换为 OpenAI 格式
    print("Getting MCP tools list...")
    mcp_tools = []
    for tool in mcp_client.list_tools():
        mcp_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["inputSchema"]
            }
        })
    print(f"Found {len(mcp_tools)} MCP tools")

    # 合并原有的工具和 MCP 工具
    tools = tools + mcp_tools
except Exception as e:
    print(f"MCP initialization failed: {e}")
    print("Using local tools instead")
    mcp_client = None

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
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"Calling tool: {tool_name}, args: {args}")
            
            # 检查是否是 MCP 工具（优先尝试）
            if mcp_client:
                try:
                    result = mcp_client.call_tool(tool_name, args)
                except Exception as e:
                    print(f"MCP call failed: {e}, using local implementation")
                    # 如果 MCP 调用失败，回退到本地实现
                    if tool_name == "read_file":
                        result = file_tool.execute(**args)
                    else:
                        result = f"Unknown tool: {tool_name}"
            else:
                # MCP 不可用，使用本地实现
                if tool_name == "read_file":
                    # result = file_tool.execute(**args)
                    result = "❌ MCP 不可用，无法调用 read_file 工具"
                else:
                    result = f"Unknown tool: {tool_name}"
            
            # 打印工具执行结果的前200个字符
            print(f"Tool result:\n{result[:200]}\n")
            # 将工具执行结果作为 tool 类型的消息追加到历史记录中
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": result
            })

if __name__ == "__main__":
    try:
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
    finally:
        # 清理资源，停止 MCP 服务器
        if mcp_client:
            mcp_client.stop()                