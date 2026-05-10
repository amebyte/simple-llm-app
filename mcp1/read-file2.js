const fs = require('fs');
const path = require('path');

// ────────────────────────────────────────────────────────────────────────────
// MCP tools/list 响应格式
// 每个工具对象必须包含以下字段：
//   name        - 工具的唯一标识符（客户端调用 tools/call 时使用此名称）
//   title       - 人类可读的显示名称（客户端 UI 可直接展示）
//   description - 详细说明工具的作用及使用时机，帮助 LLM 理解何时调用
//   inputSchema - JSON Schema，定义期望的输入参数（类型、必填项、可选项）
// ────────────────────────────────────────────────────────────────────────────
const tools = [
    {
        name: "read_file",
        title: "读取文件",
        description: "读取文本文件内容。",
        inputSchema: {
            type: "object",
            properties: {
                path: {
                    type: "string",
                    description: "要读取的文件路径"
                },
                encoding: {
                    type: "string",
                    enum: ["utf-8", "gbk"],
                    description: "文件的字符编码格式"
                }
            },
            required: ["path"]
        }
    },
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