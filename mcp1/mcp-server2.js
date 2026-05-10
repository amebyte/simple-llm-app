#!/usr/bin/env node
const readline = require('readline');
const { tools, fileTool, listDirTool } = require('./read-file.js');

// -------- 协议版本协商 --------
// 服务器支持的所有协议版本，按优先级从高到低排列
const SUPPORTED_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];

/**
 * 与客户端协商协议版本。
 * 规则：优先选择服务器与客户端都支持的最高版本。
 * @param {string | string[]} clientVersions - 客户端声明支持的版本（单个字符串或数组）
 * @returns {string | null} 协商出的版本，若无法兼容则返回 null
 */
function negotiateVersion(clientVersions) {
    // 兼容旧客户端：允许客户端只传单个字符串
    const clientSet = new Set(
        Array.isArray(clientVersions) ? clientVersions : [clientVersions]
    );
    // 按服务器优先级顺序查找第一个双方都支持的版本
    for (const version of SUPPORTED_VERSIONS) {
        if (clientSet.has(version)) {
            return version;
        }
    }
    return null;
}

// -------- 能力发现 --------
/**
 * 服务器自身支持的 capabilities：
 *   tools.listChanged  - 当工具列表变化时可主动推送通知
 *   logging            - 支持日志级别设置（setLevel）
 *   notifications      - 支持向客户端发送异步通知
 */
const SERVER_CAPABILITIES = {
    tools: {
        listChanged: true   // 工具列表可动态变化，变更时会推通知
    },
    logging: {},            // 支持 logging/setLevel 请求
    notifications: {
        tools: {
            listChanged: true   // 支持 notifications/tools/list_changed 通知
        }
    }
};

/**
 * 检查服务器是否具备某项 capability。
 * @param {string} path  以 '.' 分隔的能力路径，例如 'tools.listChanged'
 * @returns {boolean}
 */
function serverHas(path) {
    return path.split('.').reduce((obj, key) => obj?.[key], SERVER_CAPABILITIES) !== undefined;
}

// 运行时保存客户端声明的 capabilities（握手后填入）
let clientCapabilities = {};

/**
 * 检查客户端是否声明了某项 capability。
 * @param {string} path  以 '.' 分隔的能力路径
 * @returns {boolean}
 */
function clientHas(path) {
    return path.split('.').reduce((obj, key) => obj?.[key], clientCapabilities) !== undefined;
}

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

/**
 * 向客户端发送异步通知（无需 id，无需响应）。
 * 仅在服务端和客户端都声明了 notifications 能力时才应调用。
 * @param {string} method  通知方法名
 * @param {object} [params] 通知参数
 */
function sendNotification(method, params) {
    const notification = {
        jsonrpc: '2.0',
        method: method,
        ...(params !== undefined ? { params } : {})
    };
    process.stdout.write(JSON.stringify(notification) + '\n');
}

// -------- 请求路由 --------
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

rl.on('line', (line) => {
    try {
        const request = JSON.parse(line.trim());

        // ── initialize ──────────────────────────────────────────────────────
        if (request.method === 'initialize') {
            const clientVersions = request.params?.protocolVersion ?? [];
            const negotiated = negotiateVersion(clientVersions);

            if (!negotiated) {
                sendError(
                    request.id,
                    -32600,
                    'Protocol version negotiation failed',
                    {
                        clientVersions: Array.isArray(clientVersions)
                            ? clientVersions
                            : [clientVersions],
                        serverSupportedVersions: SUPPORTED_VERSIONS
                    }
                );
                setTimeout(() => process.exit(1), 100);
                return;
            }

            // 保存客户端声明的 capabilities，供后续调用时做能力检查
            clientCapabilities = request.params?.capabilities ?? {};

            console.error(`[MCP Server] Protocol version negotiated: ${negotiated}`);
            console.error(`[MCP Server] Client capabilities: ${JSON.stringify(clientCapabilities)}`);

            sendResponse(request.id, {
                protocolVersion: negotiated,
                // 告知客户端：本服务器具备哪些 capabilities
                capabilities: SERVER_CAPABILITIES,
                serverInfo: { name: 'read-file-server', version: '1.0.0' }
            });

        // ── tools/list ──────────────────────────────────────────────────────
        } else if (request.method === 'tools/list') {
            // 检查服务器是否声明了 tools capability（本服务器一定有，此处作保险校验）
            if (!serverHas('tools')) {
                sendError(request.id, -32601, 'Server does not support tools');
                return;
            }

            sendResponse(request.id, { tools });

            // 如果双方都支持工具列表变更通知，在首次返回后立即发一条通知
            // 真实场景中应在工具列表实际发生变化时再推送
            if (serverHas('tools.listChanged') && clientHas('tools.listChanged')) {
                console.error('[MCP Server] Sending tools list_changed notification');
                sendNotification('notifications/tools/list_changed');
            }

        // ── tools/call ──────────────────────────────────────────────────────
        } else if (request.method === 'tools/call') {
            // 服务端必须声明 tools capability 才允许调用
            if (!serverHas('tools')) {
                sendError(request.id, -32601, 'Server does not support tools');
                return;
            }

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
                        content: [{ type: 'text', text: 'Read failed: ' + e.message }],
                        isError: true
                    });
                }
            } else {
                sendError(request.id, -32601, `Unknown tool: ${name}`);
            }

        // ── logging/setLevel ────────────────────────────────────────────────
        } else if (request.method === 'logging/setLevel') {
            // 仅当服务器声明了 logging capability 才处理
            if (!serverHas('logging')) {
                sendError(request.id, -32601, 'Server does not support logging');
                return;
            }
            const level = request.params?.level ?? 'info';
            console.error(`[MCP Server] Log level set to: ${level}`);
            sendResponse(request.id, {});

        // ── 未知方法 ────────────────────────────────────────────────────────
        } else {
            sendError(request.id, -32601, `Method not found: ${request.method}`);
        }

    } catch (e) {
        // Ignore malformed JSON
    }
});