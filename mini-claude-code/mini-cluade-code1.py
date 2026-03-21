import os
import json
import subprocess
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
            "description": "执行 shell 命令并返回输出",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "可选的命令执行工作目录(相对于 workspace)"
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
        
class ExecTool:
    def __init__(self, timeout: int = 60):
        # 持久化工作目录状态
        self.working_dir: Path = WORKDIR
        self.timeout = timeout

    def execute(self, command: str, working_dir: str = "") -> str:
        try:
            cwd = checkPath(working_dir) if working_dir else self.working_dir
            cwd.mkdir(parents=True, exist_ok=True)
            self.working_dir = cwd
            print(f"\n\033[33m📁 [当前目录] {self.working_dir}\033[0m") 
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                cwd=cwd,
                encoding="utf-8",
                timeout=self.timeout,  # 1分钟超时
            )

            output = result.stdout if result.stdout else "(无输出)"
            if result.stderr:
                output += f"\n错误输出: {result.stderr}"

            if result.returncode != 0:
                return f"❌ 命令执行失败 (退出码: {result.returncode})\n{output}"
            # 在结果中附加当前目录，让模型始终感知自己所在位置
            return f"✅ 执行成功 (当前目录: {self.working_dir})\n{output}"
        except subprocess.TimeoutExpired:
            return f"❌ 命令执行超时(>120秒): {command}"
        except Exception as e:
            return f"❌ 执行失败: {str(e)}"
        
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
- `exec`：执行 shell 命令并分析结果，执行前确认命令影响范围；危险命令会等待用户确认。

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