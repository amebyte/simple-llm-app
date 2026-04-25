import json
import subprocess

clientProtocolVersion = '2025-12-25'
# ---------- MCP 客户端 ----------
class MCPClient:

    def __init__(self, server_command):
        self.server_command = server_command
        self.process = None
        self.request_id = 0
        self.initialized = False

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
            "protocolVersion": clientProtocolVersion,
        })
        result = response.get("result", {})
        server_version = result.get("protocolVersion")
        if server_version != clientProtocolVersion:
            raise Exception(
                f"协议版本不兼容：客户端版本 {clientProtocolVersion}，服务端版本 {server_version}"
            )
        self.negotiated_version = server_version
        # 初始化完成
        self.initialized = True

        print(f"MCP 服务器已连接（协议版本：{self.negotiated_version}）")

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