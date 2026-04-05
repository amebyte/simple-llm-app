const WebSocket = require('ws');

function run_ws() {
  const ws = new WebSocket('ws://example.com/socket');

  ws.on('open', () => {
    console.log('[Worker] WebSocket connected');
  });

  ws.on('message', (data) => {
    console.log('[Worker] Received:', data.toString());
  });
}

// 同步执行
run_ws();
console.log('主线程没有被阻塞');