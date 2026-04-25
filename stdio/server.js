#!/usr/bin/env node
'use strict';

const readline = require('readline');

/**
 * 从 stdin 按行读取 JSON 请求，处理后向 stdout 返回 JSON 响应
 */
function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false,
  });

  rl.on('line', (line) => {
    line = line.trim();
    if (!line) return;

    let resp;
    try {
      const req = JSON.parse(line);
      // 请求格式: {"text": "hello"}
      const text = req.text ?? '';
      resp = { result: `Echo: ${text}` };
    } catch (e) {
      resp = { error: e.message };
    }

    // 将响应写入 stdout，必须带换行符
    process.stdout.write(JSON.stringify(resp) + '\n');
  });
}

main();