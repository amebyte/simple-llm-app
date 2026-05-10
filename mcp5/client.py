import json
import subprocess

# ---------- 本地工具定义 ----------
tools = []

# ---------- MCP 客户端 ----------
class MCPClient:
    # 客户端支持的协议版本
    clientProtocolVersion = '2025-12-25'
    # 客户端自身声明的 capabilities（告知服务器本客户端支持哪些特性）
    CLIENT_CAPABILITIES = {
        "tools": {
            "listChanged": True    # 客户端可以处理工具列表变更通知
        },
    }
    def __init__(self, server_command):
        self.server_command = server_command
        self.process = None
        self.request_id = 0
        self.initialized = False
        self.negotiated_version = None    # 协商后的协议版本
        self.server_capabilities = {}     # 服务器声明的 capabilities（握手后填入）

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
        print("正在启动 MCP 服务器...")
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
        # 发送消息
        response = self.send_request("initialize", {
            "protocolVersion": self.clientProtocolVersion,
            "capabilities": self.CLIENT_CAPABILITIES,
            "clientInfo": {
                "name": "mcp-agent-loop",
                "version": "1.0.0",
            }
        })
        # 检查服务器是否返回了错误（版本不兼容）
        if "error" in response:
            err = response["error"]
            self.stop()
            raise ConnectionError(
                f"协议版本协商失败 "
                f"Server error [{err.get('code')}]: {err.get('message')}. "
                f"Details: {err.get('data', {})}"
            )
        result = response.get("result", {})
        server_version = result.get("protocolVersion")
        # 保存协商后的协议版本
        self.negotiated_version = server_version
        # 能力发现：保存服务器 capabilities
        self.server_capabilities = result.get("capabilities", {})    
        # 初始化完成
        self.initialized = True

        print(f"MCP 服务器已连接（协议版本：{self.negotiated_version}）")
        # 验证服务器是否支持 tools（若不支持则后续调用无意义）
        if not self.server_has("tools"):
                    print("[WARN] 服务器未声明 'tools' 能力。"
                        "工具调用很可能会失败。")  

    # -------- 底层通信 --------
    def send_request(self, method, params=None):
        if not self.process:
            raise Exception("MCP 服务器未启动")

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
            # 延迟 5 毫秒读取
            while time.time() - start_time < 5:
                # 读取子进程响应
                response_line = self.process.stdout.readline()
                if response_line and response_line.strip():
                    break
                time.sleep(0.1)

            if not response_line or not response_line.strip():
                stderr_output = self.process.stderr.read()
                if stderr_output:
                    raise Exception(f"MCP 服务器错误：{stderr_output}")
                raise Exception("未收到 MCP 服务器的响应")
            # 解析响应
            parsed = json.loads(response_line)

            return parsed
        except Exception as e:
            raise Exception(f"MCP 请求失败：{e}")
        
    # -------- 工具调用（带能力前置检查）--------
    def list_tools(self):
        # 调用前检查服务器是否声明了 tools capability
        if not self.server_has("tools"):
            raise Exception(
                "服务器不支持 'tools' 能力。"
                f"服务器能力列表：{self.server_capabilities}"
            )
        result = self.send_request("tools/list")
        return result.get("result", {}).get("tools", [])

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                self.process.kill()
                self.process.wait()

# 初始化 MCP 客户端
mcp_client = MCPClient(["node", "server.js"])
mcp_client.start()

# 获取 MCP 工具列表
print("获取 MCP 工具列表...")
mcp_tools_raw = mcp_client.list_tools()
print(f"发现 {len(mcp_tools_raw)} 个 MCP 工具")

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