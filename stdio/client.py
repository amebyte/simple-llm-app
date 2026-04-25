#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path

# 路径
server_path = Path(__file__).parent / "server.js"
# 启动子进程，连接其 stdin/stdout
proc = subprocess.Popen(
    ["node", server_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=None,          # 也可以单独重定向 stderr 看日志
    text=True             # 以文本模式操作，自动处理编解码
)

# 构造请求（JSON 行）
request = {"text": "Hello, stdio!"}
request_line = json.dumps(request) + "\n"

# 发送请求到子进程的 stdin
proc.stdin.write(request_line)
proc.stdin.flush()

# 读取子进程 stdout 的一行响应
response_line = proc.stdout.readline()
response = json.loads(response_line)

print("收到响应:", response)

# 关闭子进程
proc.terminate()
proc.wait()