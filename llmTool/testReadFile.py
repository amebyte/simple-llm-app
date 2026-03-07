from pathlib import Path

class ReadFileTool:
    """读取文件内容"""
    def execute(self, path: str, encoding: str = "utf-8") -> str:
        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return f"❌ 文件不存在: {path}"
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ 读取失败: {str(e)}"
        
# 初始化工具实例
file_tool = ReadFileTool()
result = file_tool.execute('file.txt')
            
print(f"✅ 工具执行结果:\n{result}\n")