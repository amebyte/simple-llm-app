#!/usr/bin/env node
const readline = require('readline');
const { tools, fileTool } = require('./read-file.js');
// 声明服务端支持的能力
const SERVER_CAPABILITIES = {
    tools: {
        listChanged: true   // 工具列表可动态变化，变更时会推通知
    },
};

// -------- 消息发送工具函数 --------
function sendResponse(id, result) {
    const response = {
        jsonrpc: '2.0',
        id: id,
        result: result
    };
    process.stdout.write(JSON.stringify(response) + '\n');
}

function sendError(id, code, message, data) {
    const response = {
        jsonrpc: '2.0',
        id: id,
        error: { code, message, ...(data !== undefined ? { data } : {}) }
    };
    process.stdout.write(JSON.stringify(response) + '\n');
}

const serverProtocolVersion = '2025-12-25'

// -------- 请求路由 --------
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

rl.on('line', (line) => {
    try {
        const request = JSON.parse(line.trim());
        // 根据 method 进行分发处理
        if (request.method === 'initialize') {
            const clientVersions = request.params?.protocolVersion;
            if (clientVersions !== serverProtocolVersion) {
                sendError(request.id, -32600, `版本协议不支持`, {
                        clientVersions,
                        serverSupportedVersions: serverProtocolVersion 
                    });
                setTimeout(() => process.exit(1), 100);
                return;
            }
            // 保存客户端声明的 capabilities，供后续调用时做能力检查
            clientCapabilities = request.params?.capabilities ?? {};

            console.error(`[MCP 服务器] 协议版本已协商`);
            console.error(`[MCP 服务器] 客户端能力: ${JSON.stringify(clientCapabilities)}`);

            sendResponse(request.id, {
                protocolVersion: serverProtocolVersion,
                // 告知客户端：本服务器具备哪些 capabilities
                capabilities: SERVER_CAPABILITIES,
                serverInfo: { name: 'read-file-server', version: '1.0.0' }
            });
        } else if (request.method === 'tools/list') {
            // 返回服务端的工具列表
            sendResponse(request.id, { tools });
        } else if (request.method === 'tools/call') {
            const { name, arguments: args } = request.params;
            if (name === 'read_file') {
                try {
                    const filePath = args.path;
                    const encoding = args.encoding || 'utf-8';
                    const content = fileTool.execute(filePath, encoding);
                    sendResponse(request.id, {
                        content: [{ type: 'text', text: content }]
                    });
                } catch (e) {
                    sendResponse(request.id, {
                        content: [{ type: 'text', text: '读取失败: ' + e.message }],
                        isError: true
                    });
                }
            } else {
                sendError(request.id, -32601, `未知工具: ${name}`);
            }
        // 未知方法
        } else {
            sendError(request.id, -32601, `方法不存在: ${request.method}`);
        }
    } catch (e) {
        // JSON 解析失败
        sendError('error', -32700, `JSON 解析失败：${e}`);
    }
});