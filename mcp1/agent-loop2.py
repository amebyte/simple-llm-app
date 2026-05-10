import os
import json
import subprocess
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
    # 客户端支持的所有协议版本（按优先级从高到低）
    SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

    # 客户端自身声明的 capabilities（告知服务器本客户端支持哪些特性）
    CLIENT_CAPABILITIES = {
        "tools": {
            "listChanged": True    # 客户端可以处理工具列表变更通知
        },
        "notifications": {
            "tools": {
                "listChanged": True    # 客户端能接收 notifications/tools/list_changed
            }
        }
    }

    def __init__(self, server_command):
        self.server_command = server_command
        self.process = None
        self.request_id = 0
        self.initialized = False
        self.negotiated_version = None       # 协商后的协议版本
        self.server_capabilities = {}        # 服务器声明的 capabilities（握手后填入）

    # -------- 能力查询辅助方法 --------
    def _has_capability(self, caps: dict, path: str) -> bool:
        """
        检查 capabilities 字典中是否存在给定的能力路径。
        path 为 '.' 分隔的键序列，例如 'tools.listChanged'。
        """
        obj = caps
        for key in path.split("."):
            if not isinstance(obj, dict) or key not in obj:
                return False
            obj = obj[key]
        return True

    def server_has(self, path: str) -> bool:
        """检查服务器是否声明了某项 capability。"""
        return self._has_capability(self.server_capabilities, path)

    def client_has(self, path: str) -> bool:
        """检查客户端自身是否声明了某项 capability。"""
        return self._has_capability(self.CLIENT_CAPABILITIES, path)

    # -------- 启动与握手 --------
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

        # -------- 协议版本协商 + 能力发现 --------
        # 同时发送：版本列表 + 客户端 capabilities
        response = self.send_request("initialize", {
            "protocolVersion": self.SUPPORTED_VERSIONS,
            "capabilities": self.CLIENT_CAPABILITIES,
            "clientInfo": {"name": "mcp-agent-loop", "version": "1.0.0"}
        })

        # 检查服务器是否返回了错误（版本不兼容）
        if "error" in response:
            err = response["error"]
            self.stop()
            raise ConnectionError(
                f"Protocol version negotiation failed. "
                f"Server error [{err.get('code')}]: {err.get('message')}. "
                f"Details: {err.get('data', {})}"
            )

        result = response.get("result", {})

        # ── 版本校验 ──
        server_version = result.get("protocolVersion")
        if server_version not in self.SUPPORTED_VERSIONS:
            self.stop()
            raise ConnectionError(
                f"Protocol version negotiation failed: "
                f"server returned unsupported version '{server_version}'. "
                f"Client supports: {self.SUPPORTED_VERSIONS}"
            )

        # ── 能力发现：保存服务器 capabilities ──
        self.server_capabilities = result.get("capabilities", {})

        self.negotiated_version = server_version
        # 初始化完成
        self.initialized = True

        print(f"MCP server connected (protocol version: {self.negotiated_version})")
        print(f"Server capabilities: {json.dumps(self.server_capabilities, ensure_ascii=False)}")

        # 验证服务器是否支持 tools（若不支持则后续调用无意义）
        if not self.server_has("tools"):
            print("[WARN] Server does not declare 'tools' capability. "
                  "Tool calls will likely fail.")

    # -------- 通知处理 --------
    def handle_notification(self, message: dict):
        """处理来自服务器的异步通知（无 id 字段的消息）。"""
        method = message.get("method", "")
        if method == "notifications/tools/list_changed":
            # 仅当本客户端声明了对应能力时才处理
            if self.client_has("notifications.tools.listChanged"):
                print("[Notification] Tool list changed – refreshing tool list...")
                # 重新拉取最新工具列表
                return True   # 调用方据此决定是否刷新
        return False

    # -------- 底层通信 --------
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

            import time
            start_time = time.time()
            response_line = ""

            while time.time() - start_time < 5:
                response_line = self.process.stdout.readline()
                if response_line and response_line.strip():
                    break
                time.sleep(0.1)

            if not response_line or not response_line.strip():
                stderr_output = self.process.stderr.read()
                if stderr_output:
                    raise Exception(f"MCP server error: {stderr_output}")
                raise Exception("No response from MCP server")

            parsed = json.loads(response_line)

            # 如果服务器推送了异步通知（无 id），先处理通知，再读取真正的响应
            if "id" not in parsed and "method" in parsed:
                self.handle_notification(parsed)
                # 继续读取真正的响应
                response_line = self.process.stdout.readline()
                if not response_line or not response_line.strip():
                    raise Exception("No response after notification from MCP server")
                parsed = json.loads(response_line)

            return parsed
        except Exception as e:
            raise Exception(f"MCP request failed: {e}")

    # -------- 工具调用（带能力前置检查）--------
    def list_tools(self):
        # 调用前检查服务器是否声明了 tools capability
        if not self.server_has("tools"):
            raise Exception(
                "Server does not support 'tools' capability. "
                f"Server capabilities: {self.server_capabilities}"
            )
        result = self.send_request("tools/list")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name, arguments):
        # 调用前检查服务器是否声明了 tools capability
        if not self.server_has("tools"):
            raise Exception(
                f"Cannot call tool '{name}': "
                "server does not support 'tools' capability."
            )
        result = self.send_request("tools/call", {"name": name, "arguments": arguments})
        tool_result = result.get("result", {})
        content_parts = tool_result.get("content", [])
        return "\n".join(part.get("text", "") for part in content_parts)

    def set_log_level(self, level: str = "info"):
        """设置服务器日志级别（仅在服务器声明了 logging capability 时才发送）。"""
        if not self.server_has("logging"):
            print(f"[WARN] Server does not support 'logging' capability, skipping setLevel.")
            return
        self.send_request("logging/setLevel", {"level": level})
        print(f"Server log level set to: {level}")

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

    # 可选：如果服务器支持 logging，设置日志级别
    mcp_client.set_log_level("debug")

    # 获取 MCP 工具列表并转换为 OpenAI 格式
    print("Getting MCP tools list...")
    mcp_tools_raw = mcp_client.list_tools()
    print(f"Found {len(mcp_tools_raw)} MCP tools")

    # ── 格式转换：MCP 格式 → OpenAI tools 格式 ──────────────────────────────
    # MCP tools/list 返回的格式：
    #   { name, title, description, inputSchema }
    # OpenAI API 期望的格式：
    #   { type: "function", function: { name, description, parameters } }
    def mcp_tool_to_openai(mcp_tool: dict) -> dict:
        return {
            "type": "function",
            "function": {
                "name": mcp_tool["name"],
                "description": mcp_tool.get("description", mcp_tool.get("title", "")),
                "parameters": mcp_tool.get("inputSchema", {"type": "object", "properties": {}})
            }
        }

    mcp_tools = [mcp_tool_to_openai(t) for t in mcp_tools_raw]

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
                        result = "MCP 不可用，无法调用 read_file 工具"
                    else:
                        result = f"Unknown tool: {tool_name}"
            else:
                # MCP 不可用，使用本地实现
                if tool_name == "read_file":
                    result = "MCP 不可用，无法调用 read_file 工具"
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