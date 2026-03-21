#!/usr/bin/env python3
"""
Mini Claude Code - 专业的 AI 程序员助手
基于文件系统工具和智能 Agent 循环,能够根据用户需求自动生成和管理代码
"""

import os
import sys
import json
import subprocess
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from datetime import datetime

console = Console()

# 加载环境变量
load_dotenv()

WORKDIR = Path.cwd() / 'workspace'

# 检查 DEEPSEEK_API_KEY 是否设置
if not os.getenv("DEEPSEEK_API_KEY"):
    console.print("[bold red]ERROR:[/bold red] 必须在环境变量或 .env 文件中设置 DEEPSEEK_API_KEY")
    sys.exit(1)

# ==================== Claude Code 风格渲染器 ====================

class ToolStatus(Enum):
    SUCCESS = "●"   # 绿色 - 执行成功
    ERROR   = "●"   # 红色 - 执行失败
    RUNNING = "●"   # 黄色 - 执行中


# 工具名映射（Claude Code 风格）
_TOOL_NAME_MAP = {
    "exec":       "bash",
    "write_file": "write",
    "read_file":  "read",
    "edit_file":  "update",
    "list_dir":   "browse",
}

# 各工具的主要参数 key
_TOOL_KEY_ARG = {
    "exec":       "command",
    "write_file": "path",
    "read_file":  "path",
    "edit_file":  "path",
    "list_dir":   "path",
}


def _format_tool_compact(name: str, args: dict) -> str:
    """将工具名和参数格式化为紧凑单行，如 Bash(git status)"""
    display_name = _TOOL_NAME_MAP.get(name, name.title())
    if not args:
        return f"{display_name}()"
    key = _TOOL_KEY_ARG.get(name)
    val = str(args[key]) if key and key in args else str(next(iter(args.values())))
    if len(val) > 50:
        val = val[:47] + "..."
    return f"{display_name}({val})"


def _is_success(content: str) -> bool:
    """判断工具执行结果是否成功"""
    return content.startswith("✅")


def _format_tree_output(content: str, max_lines: int = 8) -> list:
    """将工具输出格式化为树形结构，返回 Rich Text 列表"""
    elements = []
    if not content.strip():
        elements.append(Text("  └ (empty)", style="dim"))
        return elements

    lines = content.strip().split("\n")

    # 过滤掉首行的 ✅/❌ 状态行（如 "✅ 执行成功 (当前目录: ...)"）
    content_lines = []
    for line in lines:
        if line.startswith("✅") or line.startswith("❌"):
            rest = line[1:].strip()
            # 跳过纯状态描述行，保留有实质内容的部分
            skip_prefixes = ("执行成功", "写入", "编辑", "成功写入", "成功编辑")
            if rest and not any(rest.startswith(p) for p in skip_prefixes):
                content_lines.append(rest)
        else:
            content_lines.append(line)

    if not content_lines:
        elements.append(Text("  └ (done)", style="dim"))
        return elements

    total = len(content_lines)
    display_lines = content_lines[:max_lines]
    style = "dim" if _is_success(content) else "red dim"

    for i, line in enumerate(display_lines):
        prefix = "└" if i == 0 else " "
        if len(line) > 80:
            line = line[:77] + "..."
        elements.append(Text(f"  {prefix} {line}", style=style))

    remaining = total - max_lines
    if remaining > 0:
        elements.append(Text(f"    ... +{remaining} lines", style="dim italic"))

    return elements


def render_tool_start(tool_name: str, args: dict):
    """显示工具开始执行（黄色圆点）"""
    compact = _format_tool_compact(tool_name, args)
    line = Text()
    line.append(f"{ToolStatus.RUNNING.value} ", style="bold yellow")
    line.append(compact, style="bold yellow")
    console.print(line)


def render_tool_result(tool_name: str, args: dict, result: str):
    """显示工具执行结果（绿色/红色圆点 + 树形输出）"""
    success = _is_success(result)
    compact = _format_tool_compact(tool_name, args)
    status = ToolStatus.SUCCESS if success else ToolStatus.ERROR
    style = "bold green" if success else "bold red"

    # 状态行（覆盖之前的黄色行，通过新打印一行实现）
    line = Text()
    line.append(f"{status.value} ", style=style)
    line.append(compact, style=style)
    console.print(line)

    # 树形输出（根据工具类型决定行数）
    max_lines_map = {
        "write_file": 1,
        "edit_file":  1,
        "read_file":  5,
        "list_dir":   10,
        "exec":       8,
    }
    max_lines = max_lines_map.get(tool_name, 5)

    # write_file / edit_file 只显示简短状态行
    if tool_name in ("write_file", "edit_file"):
        first_line = result.split("\n")[0].lstrip("✅❌").strip()
        tree_style = "dim" if success else "red dim"
        console.print(Text(f"  └ {first_line}", style=tree_style))
    else:
        for elem in _format_tree_output(result, max_lines=max_lines):
            console.print(elem)


# ==================== 工具定义 ====================

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
            "description": "执行 shell 命令并返回输出。注意：1) 使用 ; 或 && 连接多个命令，不要用换行；2) 所有命令共享同一 shell 会话，环境变量和目录状态会保持；3) 避免使用 cd，优先使用绝对路径。",
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

# ==================== 工具实现 ====================

def checkPath(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"路径不在工作区内: {p}")
    return path

class ReadFileTool:
    def execute(self, path: str) -> str:
        try:
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
    def __init__(self):
        # 持久化工作目录状态，模拟真实 shell 的 cd 行为
        self._cwd: Path = WORKDIR

    def execute(self, command: str, working_dir: str = "") -> str:
        try:
            # 如果显式传入 working_dir，以它为准（并更新持久状态）
            if working_dir:
                cwd = checkPath(working_dir)
                cwd.mkdir(parents=True, exist_ok=True)
                self._cwd = cwd
            else:
                cwd = self._cwd
                cwd.mkdir(parents=True, exist_ok=True)
            print(f"当前目录：{cwd}")
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                cwd=cwd,
                encoding="utf-8",
                timeout=120,  # 2分钟超时
            )

            stdout = result.stdout or ""

            clean_lines = []
            for line in stdout.splitlines():
                clean_lines.append(line)

            output = "\n".join(clean_lines) if clean_lines else "(无输出)"
            if result.stderr:
                output += f"\n错误输出: {result.stderr}"

            if result.returncode != 0:
                return f"❌ 命令执行失败 (退出码: {result.returncode})\n{output}"

            return f"✅ 执行成功 (当前目录: {self._cwd})\n{output}"
        except subprocess.TimeoutExpired:
            return f"❌ 命令执行超时(>120秒): {command}"
        except Exception as e:
            return f"❌ 执行失败: {str(e)}"


# 实例化工具
file_tools = {
    "read_file": ReadFileTool(),
    "write_file": WriteFileTool(),
    "edit_file": EditFileTool(),
    "list_dir": ListDirTool(),
    "exec": ExecTool()
}

# ==================== OpenAI 客户端 ====================

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ==================== 核心 Agent 循环 ====================

def agent_loop(messages: list) -> str:
    """
    智能代理循环:不断调用大模型,自动执行工具,直到完成任务
    """
    max_iterations = 50  # 防止无限循环
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # 调用大模型（显示动态 Thinking 加载效果）
        with Live(
            Spinner("dots2", text=" Thinking...", style="bold cyan"),
            console=console,
            transient=True,
            refresh_per_second=12,
        ):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
        msg = response.choices[0].message
        messages.append(msg)
        
        # 如果没有工具调用,返回最终答案
        if not msg.tool_calls:
            return msg.content
        
        # 执行所有工具调用
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            # 1. 显示"执行中"状态（黄色圆点）
            render_tool_start(tool_name, args)

            # 执行工具
            if tool_name in file_tools:
                result = file_tools[tool_name].execute(**args)
            else:
                result = f"❌ 未知工具: {tool_name}"

            # 2. 显示执行结果（绿色/红色圆点 + 树形输出）
            render_tool_result(tool_name, args, result)

            # 将工具结果返回给模型
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": result
            })

        console.print()  # 工具组之间空行
    
    return "⚠️ 达到最大迭代次数,任务可能未完成"

# ==================== 系统提示词 ====================

SYSTEM_PROMPT = f"""你是 Mini Claude Code,一个专业的 AI 编程助手。

# 核心能力

- 理解并实现各种编程需求
- 系统化地读取、创建和编辑文件
- 探索代码库并理解现有实现
- 提供代码优化和最佳实践建议
- 必要时执行 shell 命令

# 工作目录

- 默认工作空间: `{WORKDIR}/`
- 所有文件必须保存到 `{WORKDIR}/` 目录(除非用户指定绝对路径)
- 相对路径自动添加 `{WORKDIR}/` 前缀

示例:
- 用户说"创建 app.py" → 实际路径: `{WORKDIR}/app.py`
- 用户说"创建 src/main.py" → 实际路径: `{WORKDIR}/src/main.py`

# 可用工具

1. **read_file(path)** - 读取文件内容
   - 查看代码、配置或文档
   - 编辑前必须先读取

2. **write_file(path, content)** - 创建或覆盖文件
   - 用于新文件或完全重写
   - 确保目录结构合理

3. **edit_file(path, old_text, new_text)** - 修改现有文件
   - 必须先用 read_file 读取文件
   - old_text 必须完全匹配(包括空格)

4. **list_dir(path)** - 列出目录内容
   - 探索项目结构
   - 操作前先了解目录结构

5. **exec(command, working_dir?)** - 执行 shell 命令
   - 谨慎使用,超时 120 秒
   - 交互式命令必须用非交互模式:
     ❌ 错误: `pnpm create vite my-app` (会卡住)
     ✅ 正确: `echo y | pnpm create vite my-app --template vue-ts`

# 工作流程

## 修改前
1. 理解需求 - 不明确的地方先询问
2. 探索上下文 - 用 list_dir 和 read_file 了解项目
3. 规划方案 - 考虑依赖和副作用
4. 验证假设 - 不要猜测,读取文件验证

## 编写代码时
- 生成完整可运行的代码,带详细注释
- 遵循语言最佳实践(Python 用 PEP 8 等)
- 包含所有必要的 import 和依赖
- 添加错误处理
- 为复杂逻辑添加注释

## 修改代码时
- **必须先读取文件**再编辑
- 理解现有实现
- 最小化修改
- 保持现有风格和约定
- 确保不破坏依赖关系

## 创建项目时
- 合理的目录结构
- 包含依赖文件(requirements.txt、package.json 等)

- Web 应用要有现代美观的 UI

# 关键模式

**编辑前必须读取 (重要)**
```
✅ 正确流程:
1. read_file("app.py")
2. 分析内容
3. edit_file("app.py", old_text="...", new_text="...")

❌ 错误流程:
1. edit_file("app.py", old_text="...", new_text="...")  # 失败 - 没先读取
```

**创建前先探索**
```
✅ 正确: list_dir(".") → 了解结构 → write_file("src/utils.py", ...)
❌ 错误: write_file("utils.py", ...)  # 位置错误
```

**cd 目录状态会持久化 (重要)**
```
✅ 正确流程:
1. exec("cd vue-todo-app && npm install")  # cd 效果被记住
2. exec("npm run build")  # 自动在 vue-todo-app/ 下执行，无需再 cd
3. exec("pwd")  # 确认当前目录时使用 pwd，而不是再次 cd

❌ 错误流程:
1. exec("cd vue-todo-app && npm install")
2. exec("cd vue-todo-app && npm run build")  # 重复 cd！会进入 vue-todo-app/vue-todo-app/
```

**根据执行结果调整方案 (重要)**
```
✅ 正确流程:
1. exec("npm install")
2. 看到错误: "npm: command not found"
3. 立即分析: 需要先安装 Node.js 或使用其他包管理器
4. 调整: exec("pnpm install") 或安装 npm
5. 继续直到成功

❌ 错误流程:
1. exec("npm install")
2. 看到错误后只是报告: "npm 命令不存在"
3. 停止,等待用户指示  # 应该主动解决!
```

# 命令执行与结果分析

执行命令后,你会收到执行结果。**必须仔细分析结果并采取相应行动**:

1. **成功情况** (看到 ✅ 执行成功):
   - 检查输出是否符合预期
   - 验证是否完成了目标
   - 如果需要后续步骤,继续执行

2. **失败情况** (看到 ❌ 或错误信息):
   - 仔细阅读错误信息,找出失败原因
   - 分析是什么导致了错误(路径错误、依赖缺失、权限问题等)
   - **立即采取修正措施**:
     - 安装缺失的依赖
     - 修正错误的路径或参数
     - 调整命令格式
   - 执行修正后的命令,直到成功

3. **需要调整的情况** (警告或部分成功):
   - 分析输出中的提示信息
   - 根据提示优化方案
   - 继续改进直到完全成功

**关键原则**:
- 不要只报告错误,要**主动解决问题**
- 根据错误信息**立即调整策略**
- 持续迭代直到任务真正完成
- 最多迭代 15 次防止死循环
- 如果多次尝试仍失败,向用户说明情况并请求指导

# 重要提醒

1. **路径安全**: 所有路径必须在 `{WORKDIR}/` 内
2. **先读后改**: 编辑前必须读取文件
3. **完整响应**: 一次性完成任务
4. **不要臆测**: 总是验证文件内容
5. **高效工作**: 避免冗余操作
6. **质量优先**: 第一次就做对

收到任务时的步骤:
1. 确认理解需求
2. 必要时探索项目(list_dir, read_file)
3. 执行方案(write_file, edit_file, exec)
4. **分析执行结果** - 成功则继续,失败则立即调整并重试
5. 验证最终结果
6. 解释做了什么以及为什么
"""

# ==================== 主程序 ====================

def main():
    # ── Claude Code 风格欢迎页 ──────────────────────────────────────
    SEP_TOP = "…" * 58   # 上分隔线（与参考一致）

    ART = """\
     *                                       █████▓▓░     
                                 *         ███▓░     ░░   
            ░░░░░░                        ███▓░
    ░░░   ░░░░░░░░░░                      ███▓░
   ░░░░░░░░░░░░░░░░░░░    *                ██▓░░      ▓   
   ░░░░░░░░░░░░░░░░░░░    *                ██▓░░      ▓
                                             ░▓▓███▓▓░
 *                                 ░░░░
                                 ░░░░░░░░
                               ░░░░░░░░░░░░░░░░
       █████████                                        *
      ██▄█████▄██                        *
       █████████      *
…………………█ █   █ █………………………………………………………………………………………………………………"""

    # 标题（红色）+ 版本号
    console.print(f"[bold red]Welcome to Mini Claude Code[/bold red] [dim]v1.0.0[/dim]")
    # 上分隔线
    console.print(SEP_TOP, style="cyan")
    console.print()
    # ASCII art 主体（整体 cyan 色）
    console.print(ART, style="cyan")
    console.print()
    # 项目信息
    console.print(f"[white]  基于 DeepSeek + 文件系统工具[/white] [bold cyan]By[/bold cyan] [bold red]程序员Cobyte[/bold red]")
    console.print(f"[grey70]  工作目录:[/grey70] [grey30]{WORKDIR}[/grey30]")
    console.print()
    console.print(
        "  [white]可用工具:[/white] "
        "[bold cyan]ReadFile[/bold cyan] · [bold cyan]WriteFile[/bold cyan] · "
        "[bold cyan]EditFile[/bold cyan] · [bold cyan]ListDir[/bold cyan] · [bold cyan]Bash[/bold cyan]"
    )
    console.print()
    console.print("  [white]输入[/white] [bold cyan]/exit[/bold cyan] 退出，[bold cyan]/help[/bold cyan] [white]查看帮助[/white]")
    console.print()

    # 初始化对话历史
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 设置 prompt_toolkit 快捷键
    # multiline=True 时，prompt_toolkit 内部默认把 c-j（Ctrl+J / Ctrl+Enter）
    # 当换行处理；必须加 eager=True 才能覆盖默认行为。
    bindings = KeyBindings()

    def prompt_continuation(width, line_number, is_soft_wrap):
        """续行不显示任何前缀，直接左对齐"""
        return ' ' * 2  # 与提示符 "❯ " 等宽，保持左对齐

    session = PromptSession(
        key_bindings=bindings,
        multiline=True,
        prompt_continuation=prompt_continuation,
        style=Style.from_dict({
            # 去掉 bottom-toolbar 默认的厚重背景，让它和上边框视觉一致
            "bottom-toolbar": "bg:default noreverse",
        })
    )

    console.print(Panel.fit(
        Text("欢迎使用 Mini Claude Code！\n\n"
             "这是一个基于 DeepSeek 的 AI 编程助手，可以帮您完成各种编程任务。\n\n"
             "您可以输入以下命令来开始使用:\n"
             "1. /help - 查看帮助信息\n"
             "2. /exit - 退出程序\n"
             "3. Enter 或 Ctrl+Enter 换行\n"
             "4. Shift+Enter 提交输入\n"
             "5. 输入您的需求，我将为您完成任务"),
        title="欢迎使用 Mini Claude Code",
        border_style="green"
    ))

    # 初始化对话历史
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 交互式对话循环
    while True:
        try:
            # 上下边框线均由 prompt_toolkit 托管：
            # - 上边框：通过 prompt 参数在输入前渲染，输入过程中始终可见
            # - 下边框：通过 bottom_toolbar 渲染，固定在输入区域底部
            term_width = console.width
            border = "─" * term_width

            # 使用 prompt_toolkit 获取用户输入（Shift+Enter 换行，Enter 提交）
            user_input = session.prompt(
                HTML(f"<ansibrightblack>{border}</ansibrightblack>\n<ansicyan><b>❯</b></ansicyan> "),
                bottom_toolbar=HTML(f"<ansibrightblack>{border}</ansibrightblack>")
            ).strip()

            if not user_input:
                continue

            sep = "─" * console.width
            # 下分割线：移到空输入判断之后，此时 prompt_toolkit 已完全交出控制权
            console.print(sep, style="dim")

            if user_input.lower() in ['exit', 'quit']:
                console.print("[dim]Goodbye![/dim]")
                break

            # 添加用户消息
            history.append({"role": "user", "content": user_input})

            console.print()  # 空行

            # 执行 Agent 循环
            try:
                final_answer = agent_loop(history)

                if final_answer:
                    console.print(Panel(
                        Markdown(final_answer),
                        title="💬 Response",
                        border_style="green",
                    ))
                    console.print()
            except Exception as e:
                console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
                # 从历史记录中移除最后一条用户消息,允许重试
                history.pop()

            # 计算对话成本
            cost = 0.001 * len(history)  # 假设每条消息成本为 $0.001
            console.print(f"\n[bold green]💰 本次对话消耗: [cyan]${cost:.6f}[/cyan][/bold green]")

        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break


if __name__ == "__main__":
    main()