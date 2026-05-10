#!/usr/bin/env node
const readline = require('readline');

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

const serverProtocolVersion = '2025-12-26'

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
            sendResponse(request.id, {
                protocolVersion: serverProtocolVersion
            });
        // 未知方法
        } else {
            sendError(request.id, -32601, `方法不存在: ${request.method}`);
        }

    } catch (e) {
        // JSON 解析失败
        sendError(request.id, -32700, `JSON 解析失败：${e}`);
    }
});