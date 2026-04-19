#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { tools, ReadFileTool, fileTool } = require('./read-file.js');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

function sendResponse(id, result) {
    const response = {
        jsonrpc: '2.0',
        id: id,
        result: result
    };
    process.stdout.write(JSON.stringify(response) + '\n');
}

rl.on('line', (line) => {
    try {
        const request = JSON.parse(line.trim());
        
        if (request.method === 'initialize') {
            sendResponse(request.id, {
                protocolVersion: '2024-11-05',
                capabilities: { tools: {} },
                serverInfo: { name: 'read-file-server', version: '1.0.0' }
            });
        } else if (request.method === 'tools/list') {
            sendResponse(request.id, {
                tools: tools
            });
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
                        content: [{ type: 'text', text: 'Read failed: ' + e.message }],
                        isError: true
                    });
                }
            }
        }
    } catch (e) {
        // Ignore
    }
});
