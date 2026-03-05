"""文件系统工具 - 为 LLM 提供基础文件操作能力"""

from pathlib import Path
from typing import Any


class ReadFileTool:
    """读取文件内容"""
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "读取指定路径的文件内容"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return f"❌ 文件不存在: {path}"
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ 读取失败: {str(e)}"


class WriteFileTool:
    """写入文件内容"""

    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "将内容写入文件，自动创建父目录"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = Path(path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"✅ 成功写入 {len(content)} 字节到 {path}"
        except Exception as e:
            return f"❌ 写入失败: {str(e)}"


class EditFileTool:
    """编辑文件（文本替换）"""
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "通过替换指定文本来编辑文件"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "old_text": {"type": "string", "description": "要替换的文本"},
                "new_text": {"type": "string", "description": "替换后的文本"}
            },
            "required": ["path", "old_text", "new_text"]
        }
    
    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return f"❌ 文件不存在: {path}"
            
            content = file_path.read_text(encoding="utf-8")
            
            if old_text not in content:
                return f"❌ 未找到要替换的文本"
            
            # 简化：只替换第一次出现的文本
            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")
            
            return f"✅ 成功编辑 {path}"
        except Exception as e:
            return f"❌ 编辑失败: {str(e)}"


class ListDirTool:
    """列出目录内容"""
    
    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "列出指定目录的所有文件和文件夹"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"}
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = Path(path).expanduser()
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