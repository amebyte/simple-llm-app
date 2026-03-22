import os
import json
import subprocess
import threading
import time
import signal
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

WORKDIR = Path.cwd() / 'workspace'

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件的内容。用于查看现有代码、配置文件或文档。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径(相对或绝对路径)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建新文件或完全覆盖现有文件的内容。用于生成新代码文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的完整文件内容"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "编辑现有文件,通过查找和替换特定文本来修改文件。用于修改已存在的代码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要编辑的文件路径"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "要替换的原始文本(必须精确匹配)"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "新的替换文本"
                    }
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出指定目录下的所有文件和子目录。用于探索项目结构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出的目录路径"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exec",
            "description": (
                "执行 shell 命令并返回输出。\n"
                "• 短命令（install、build、test 等）：同步执行，返回完整输出。\n"
                "• 长时守护进程（pnpm dev、npm start、uvicorn、flask run 等）：自动在后台启动，"
                "等待 8 秒后返回 PID 和启动日志，进程继续在后台运行。\n"
                "• 后台进程管理命令（无需 working_dir）：\n"
                "  - bg_list          列出所有后台进程\n"
                "  - bg_logs <pid>    查看指定进程的最新日志\n"
                "  - bg_kill <pid>    终止指定后台进程"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令，或后台管理命令（bg_list / bg_logs <pid> / bg_kill <pid>）"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "可选的命令执行工作目录(相对于 workspace)，后台管理命令不需要此参数"
                    }
                },
                "required": ["command"]
            }
        }
    }
]

def checkPath(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"路径不在工作区内: {p}")
    return path

class ReadFileTool:
    def execute(self, path: str) -> str:
        try:
            # 先检查路径是否合规
            file_path = checkPath(path).expanduser()
            if not file_path.exists():
                return f"❌ 文件不存在: {path}"
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ 读取失败: {str(e)}"
        
class WriteFileTool:
    def execute(self, path: str, content: str) -> str:
        try:
            file_path = checkPath(path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"✅ 成功写入 {len(content)} 字节到 {path}"
        except Exception as e:
            return f"❌ 写入失败: {str(e)}"
        
class EditFileTool:
    def execute(self, path: str, old_text: str, new_text: str) -> str:
        try:
            file_path = checkPath(path).expanduser()
            if not file_path.exists():
                return f"❌ 文件不存在: {path}"
            
            content = file_path.read_text(encoding="utf-8")
            
            if old_text not in content:
                return f"❌ 未找到要替换的文本"
            
            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")
            
            return f"✅ 成功编辑 {path}"
        except Exception as e:
            return f"❌ 编辑失败: {str(e)}"
        
class ListDirTool:
    def execute(self, path: str) -> str:
        try:
            dir_path = checkPath(path).expanduser()
            if not dir_path.exists():
                return f"❌ 目录不存在: {path}"
            if not dir_path.is_dir():
                return f"❌ 不是目录: {path}"
            
            items = []
            for item in sorted(dir_path.iterdir()):
                icon = "📁" if item.is_dir() else "📄"
                items.append(f"{icon} {item.name}")
            
            return "\n".join(items) if items else "📭 空目录"
        except Exception as e:
            return f"❌ 列出失败: {str(e)}"
        
# 后台进程注册表：{pid: {"process": Popen, "command": str, "log": [str], "cwd": Path}}
_background_processes: dict = {}

# 长时进程关键词匹配（自动识别守护进程）
_DAEMON_KEYWORDS = [
    "dev", "start", "serve", "watch",
    "run server", "runserver", "preview",
    "nodemon", "uvicorn", "gunicorn", "flask run",
    "vite", "webpack", "--watch", "--hot",
]

def _is_daemon_command(command: str) -> bool:
    """判断是否为长时运行的守护进程命令"""
    cmd_lower = command.lower().strip()
    return any(kw in cmd_lower for kw in _DAEMON_KEYWORDS)


class ExecTool:
    def __init__(self):
        # 持久化工作目录状态
        self.working_dir: Path = WORKDIR

    def execute(self, command: str, working_dir: str = "") -> str:
        # 优先处理后台管理命令（不需要 cwd）
        bg_result = self._handle_bg_command(command)
        if bg_result is not None:
            return bg_result

        try:
            cwd = checkPath(working_dir) if working_dir else self.working_dir
            cwd.mkdir(parents=True, exist_ok=True)
            self.working_dir = cwd
            print(f"\n\033[33m📁 [当前目录] {self.working_dir}\033[0m")

            if _is_daemon_command(command):
                return self._run_background(command, cwd)
            else:
                return self._run_foreground(command, cwd)

        except Exception as e:
            return f"❌ 执行失败: {str(e)}"

    # ------------------------------------------------------------------
    # 前台模式：适用于短命令（install、build、test 等）
    # ------------------------------------------------------------------
    def _run_foreground(self, command: str, cwd: Path) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                cwd=cwd,
                encoding="utf-8",
                timeout=120,  # 2 分钟超时
                capture_output=True,
            )
            output = result.stdout if result.stdout else "(无输出)"
            if result.stderr:
                output += f"\n错误输出: {result.stderr}"
            if result.returncode != 0:
                return f"❌ 命令执行失败 (退出码: {result.returncode})\n{output}"
            return f"✅ 执行成功 (当前目录: {self.working_dir})\n{output}"
        except subprocess.TimeoutExpired:
            return f"❌ 命令执行超时(>120秒): {command}"

    # ------------------------------------------------------------------
    # 后台模式：适用于长时守护进程（dev server、watch 等）
    # ------------------------------------------------------------------
    def _run_background(self, command: str, cwd: Path) -> str:
        log_lines: list = []

        # 跨平台：Unix 用 os.setsid 创建独立进程组，Windows 用 CREATE_NEW_PROCESS_GROUP
        is_windows = os.name == "nt"
        popen_kwargs = dict(
            shell=True,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并 stderr → stdout
        )
        if is_windows:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["preexec_fn"] = os.setsid  # 创建独立进程组，便于后续整组 kill

        proc = subprocess.Popen(command, **popen_kwargs)

        pid = proc.pid
        _background_processes[pid] = {
            "process": proc,
            "command": command,
            "log": log_lines,
            "cwd": str(cwd),
            "started_at": time.strftime("%H:%M:%S"),
        }

        # 后台线程持续收集输出
        def _collect_output():
            for line in iter(proc.stdout.readline, ""):
                log_lines.append(line.rstrip())
                # 最多保留最近 500 行
                if len(log_lines) > 500:
                    log_lines.pop(0)
            proc.stdout.close()

        t = threading.Thread(target=_collect_output, daemon=True)
        t.start()

        # 等待最多 8 秒，收集启动阶段日志
        time.sleep(8)

        # 检查进程是否意外退出
        exit_code = proc.poll()
        if exit_code is not None:
            recent_log = "\n".join(log_lines[-30:]) or "(无输出)"
            del _background_processes[pid]
            return (
                f"❌ 进程意外退出 (退出码: {exit_code})\n"
                f"命令: {command}\n"
                f"输出:\n{recent_log}"
            )

        # 启动成功，返回摘要
        startup_log = "\n".join(log_lines) or "(暂无输出，进程正在初始化)"
        return (
            f"✅ 后台进程已启动\n"
            f"  PID        : {pid}\n"
            f"  命令       : {command}\n"
            f"  工作目录   : {cwd}\n"
            f"  启动日志   :\n{startup_log}\n\n"
            f"💡 提示: 可用 exec(\"bg_logs {pid}\") 查看最新日志，"
            f"exec(\"bg_kill {pid}\") 停止进程"
        )

    # ------------------------------------------------------------------
    # 内置管理命令：bg_list / bg_logs <pid> / bg_kill <pid>
    # ------------------------------------------------------------------
    def _handle_bg_command(self, command: str) -> str | None:
        cmd = command.strip()

        if cmd.startswith("bg_list"):
            if not _background_processes:
                return "📭 当前没有后台进程"
            lines = ["📋 后台进程列表:"]
            for pid, info in _background_processes.items():
                alive = info["process"].poll() is None
                status = "🟢 运行中" if alive else "🔴 已退出"
                lines.append(f"  [{pid}] {status} | {info['command']} | 启动于 {info['started_at']}")
            return "\n".join(lines)

        if cmd.startswith("bg_logs "):
            try:
                pid = int(cmd.split()[1])
                if pid not in _background_processes:
                    return f"❌ 未找到 PID={pid} 的后台进程"
                logs = _background_processes[pid]["log"]
                recent = "\n".join(logs[-50:]) or "(暂无日志)"
                return f"📄 PID={pid} 最近日志:\n{recent}"
            except (IndexError, ValueError):
                return "❌ 用法: bg_logs <pid>"

        if cmd.startswith("bg_kill "):
            try:
                pid = int(cmd.split()[1])
                if pid not in _background_processes:
                    return f"❌ 未找到 PID={pid} 的后台进程"
                proc = _background_processes[pid]["process"]
                try:
                    if os.name == "nt":
                        # Windows：发送 CTRL_BREAK_EVENT 给进程组
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        # Unix：kill 整个进程组（含子进程）
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    proc.terminate()
                del _background_processes[pid]
                return f"✅ 已终止后台进程 PID={pid}"
            except (IndexError, ValueError):
                return "❌ 用法: bg_kill <pid>"

        return None  # 不是管理命令
        
file_tools = {
    "read_file": ReadFileTool(),
    "write_file": WriteFileTool(),
    "edit_file": EditFileTool(),
    "list_dir": ListDirTool(),
    "exec": ExecTool()
}

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def agent_loop(messages: list) -> str:
    max_iterations = 100
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print(f"\n\033[33m🤔 正在思考... \033[0m")   # 加个提示方便调试
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        msg = response.choices[0].message
        messages.append(msg)
        
        if not msg.tool_calls:
            return msg.content
        
        # 可能有多个工具调用（比如同时读写多个文件）
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            # 打印工具调用信息（可选）
            print(f"\n\033[33m🛠️ [调用工具] {tool_name}\033[0m")
            print(f"\033[90m   参数: {json.dumps(args, ensure_ascii=False, indent=2)}\033[0m")
            
            # 执行对应的工具
            if tool_name in file_tools:
                result = file_tools[tool_name].execute(**args)
            else:
                result = f"❌ 未知工具: {tool_name}"
            
            # 截断过长的输出
            display_result = result if len(result) < 500 else result[:500] + "\n... (输出已截断)"
            print(f"\033[32m   结果: {display_result}\033[0m")
            
            # 把结果放回消息列表
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": result
            })
    
    return "⚠️ 达到最大迭代次数，任务可能未完成"

SYSTEM_PROMPT = f"""你是 Mini Claude Code，
一个专业的 AI 编程助手，能够理解需求、生成代码、管理文件并执行命令。

# 行为准则

1. **先读后改**：修改文件前先用 read_file 读取，确认理解了上下文再动手。
2. **最小化操作**：只做任务必需的改动，不引入无关修改。
3. **局部优先**：能用 edit_file 局部替换的，不用 write_file 全量覆盖。
4. **及时说明**：每次工具调用后，简要说明做了什么、发现了什么。
5. **不确定就问**：不要猜测用户意图，不确定时直接提问。
6. **路径安全**：所有文件操作限制在工作目录`{WORKDIR}/`内

# 工具使用建议

- `read_file`：读取文件。大文件用 offset + limit 分段读，不要一次读全量。
- `write_file`：适合创建新文件或完整重写；局部修改请用 edit_file。
- `edit_file`：old_text 必须在文件中唯一，先用 read_file 确认再调用。
- `exec` - 执行 shell 命令，**自动区分短命令和长时守护进程**：
  - 普通命令（install/build/test）：同步执行并返回完整输出
  - 守护进程（pnpm dev/npm start/uvicorn 等）：**自动后台启动**，返回 PID 和启动日志
  - 后台管理：`bg_list` 列出进程，`bg_logs <pid>` 查看日志，`bg_kill <pid>` 终止后台进程，而不是当前进程

## 执行守护进程的规则

1. **守护进程后台化**：执行 `pnpm dev`、`npm start`、`uvicorn`、`flask run` 等长时命令时，
   工具会自动后台启动，返回启动成功的 PID 即代表服务已启动，**不要**认为是失败
2. **验证服务状态**：后台启动后可用 `exec("bg_logs <pid>")` 查看日志确认服务是否就绪
3. **守护进程管理**：使用 `exec("bg_list")` 查看所有后台进程，使用 `exec("bg_kill <pid>")` 停止不再需要的服务，使用 `exec("bg_logs <pid>")` 实时监控服务日志，确保服务稳定运行

# 输出规范

- 使用中文与用户交流
- 代码块注明语言类型
- 任务完成后给出简洁总结（做了什么、改了哪些文件）
"""

def main():
    print("  Mini Claude Code - 专业的 AI 程序员助手")
    
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    while True:
        try:
            user_input = input("\033[1;36m > \033[0m")
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见!")
            break
        
        if user_input.strip().lower() in ("q", "exit", "quit", "退出"):
            print("\n👋 再见!")
            break
        
        if not user_input.strip():
            continue
        
        history.append({"role": "user", "content": user_input})
        print()
        
        try:
            final_answer = agent_loop(history)
            if final_answer:
                print(f"\n\033[1;32m🤖 助手:\033[0m\n{final_answer}\n")
        except Exception as e:
            print(f"\n\033[31m❌ 错误: {str(e)}\033[0m\n")
            # 移除出错的用户消息，允许重试
            history.pop()

if __name__ == "__main__":
    main()