const fs = require('fs');
const path = require('path');

const tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要读取的文件路径"},
                    "encoding": {"type": "string", "enum": ["utf-8", "gbk"], "description": "文件编码格式"}
                },
                "required": ["path"]
            }
        }
    }
];

class ReadFileTool {
    execute(filePath, encoding = "utf-8") {
        try {
            const resolvedPath = path.resolve(filePath.replace(/^~/, process.env.HOME || process.env.USERPROFILE));
            if (!fs.existsSync(resolvedPath)) {
                return `❌ 文件不存在: ${filePath}`;
            }
            return fs.readFileSync(resolvedPath, encoding);
        } catch (e) {
            return `❌ 读取失败: ${e.message}`;
        }
    }
}

const fileTool = new ReadFileTool();

module.exports = {
    tools,
    ReadFileTool,
    fileTool
};
