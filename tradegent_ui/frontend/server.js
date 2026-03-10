/**
 * Custom Next.js server with WebSocket proxy.
 *
 * Routes all /ws/* upgrade requests to the backend (NEXT_PUBLIC_API_URL or
 * localhost:8081), so the browser only needs one port open (the frontend port).
 * This is essential in remote-dev environments (VS Code Remote, SSH tunnels)
 * where only the frontend port is forwarded.
 *
 * Usage:
 *   node server.js --dev    # development (HMR enabled)
 *   node server.js          # production
 */

const { createServer } = require('http');
const { parse } = require('url');
const { WebSocket: WsClient, WebSocketServer } = require('ws');
const next = require('next');
const fs = require('fs');
const path = require('path');

// Tee stdout + stderr to tradegent_ui/logs/frontend.log (persistent, rotation-safe)
const LOG_FILE = path.join(__dirname, '..', 'logs', 'frontend.log');
const logStream = fs.createWriteStream(LOG_FILE, { flags: 'a' });
const _write = (fd, chunk) => {
  fd.write(chunk);
  logStream.write(typeof chunk === 'string' ? chunk : chunk.toString());
};
process.stdout.write = (chunk, enc, cb) => { _write(process.stdout._orig || process.stdout, chunk); if (cb) cb(); return true; };
process.stderr.write = (chunk, enc, cb) => { _write(process.stderr._orig || process.stderr, chunk); if (cb) cb(); return true; };
// Preserve originals for the tee
process.stdout._orig = fs.createWriteStream(null, { fd: 1, autoClose: false });
process.stderr._orig = fs.createWriteStream(null, { fd: 2, autoClose: false });
logStream.write(`\n--- server started ${new Date().toISOString()} ---\n`);

const dev = process.argv.includes('--dev');
const port = parseInt(process.env.PORT || '3001', 10);
const hostname = process.env.HOST || 'localhost';

// Parse backend host/port from API URL
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';
const parsedBackend = new URL(apiUrl);
const backendHost = parsedBackend.hostname;
const backendPort = parseInt(parsedBackend.port || '8081', 10);

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

/**
 * WebSocket proxy using the `ws` package.
 *
 * wss.handleUpgrade() sends the 101 Switching Protocols response to the
 * browser immediately (including Sec-WebSocket-Protocol: bearer), completing
 * the browser's handshake first. Then we open a connection to the backend and
 * bridge the two WebSocket streams. This avoids the race condition where the
 * raw-TCP approach forwarded the 101 response too slowly.
 */

// Accept 'bearer' protocol from browsers; fall back to first offered protocol.
const wss = new WebSocketServer({
  noServer: true,
  perMessageDeflate: false,  // Chrome's permessage-deflate + our proxy = mismatched compression
  handleProtocols: (protocols) => {
    if (protocols.has('bearer')) return 'bearer';
    return [...protocols][0] ?? false;
  },
});

function proxyWebSocket(req, socket, head) {
  wss.handleUpgrade(req, socket, head, (browserWs) => {

    // Build the backend WS URL: same path/query as browser's request.
    const backendWsUrl = `ws://${backendHost}:${backendPort}${req.url}`;

    // Forward the original Sec-WebSocket-Protocol so the backend can read the
    // bearer token embedded there.
    const proto = req.headers['sec-websocket-protocol'];
    const backendWs = proto
      ? new WsClient(backendWsUrl, proto.split(/,\s*/), { perMessageDeflate: false })
      : new WsClient(backendWsUrl, { perMessageDeflate: false });

    backendWs.on('open', () => {
      console.log('[ws-proxy] backend connected, bridging', req.url);
      // Bridge: browser → backend
      browserWs.on('message', (data, isBinary) => {
        if (backendWs.readyState === WsClient.OPEN) {
          backendWs.send(data, { binary: isBinary });
        }
      });
      // Bridge: backend → browser
      backendWs.on('message', (data, isBinary) => {
        if (browserWs.readyState === WsClient.OPEN) {
          browserWs.send(data, { binary: isBinary });
        }
      });
    });

    backendWs.on('close', (code, reason) => {
      if (browserWs.readyState === WsClient.OPEN ||
          browserWs.readyState === WsClient.CONNECTING) {
        browserWs.close(code);
      }
    });

    browserWs.on('close', (code, reason) => {
      console.log('[ws-proxy] browser WS closed, code:', code, 'reason:', reason.toString().slice(0, 50));
      if (backendWs.readyState === WsClient.OPEN ||
          backendWs.readyState === WsClient.CONNECTING) {
        backendWs.close();
      }
    });

    backendWs.on('error', (err) => {
      console.error('[ws-proxy] backend error:', err.message);
      if (browserWs.readyState === WsClient.OPEN) {
        browserWs.close(1011, 'Backend error');
      }
    });

    browserWs.on('error', () => {
      backendWs.terminate();
    });
  });
}

app.prepare().then(() => {
  const server = createServer((req, res) => {
    const parsedUrl = parse(req.url || '/', true);
    handle(req, res, parsedUrl);
  });

  // Override server.emit to intercept 'upgrade' events before ANY listener
  // (including Next.js's lazily-registered internal ones) can run.
  // For /ws/* paths we handle it exclusively and return without emitting.
  // All other upgrades (HMR etc.) pass through to normal listeners.
  const _emit = server.emit.bind(server);
  server.emit = function (event, ...args) {
    if (event === 'upgrade') {
      const [req, socket, head] = args;
      const { pathname } = parse(req.url || '/');
      if (pathname && pathname.startsWith('/ws/')) {
        proxyWebSocket(req, socket, head);
        return true; // consumed — no listeners called
      }
    }
    return _emit(event, ...args);
  };

  server.listen(port, () => {
    console.log(
      `> Ready on http://${hostname}:${port} (${dev ? 'dev' : 'production'})`
    );
    console.log(`> WebSocket /ws/* → ${backendHost}:${backendPort}`);
    console.log(`> upgrade intercepted via server.emit override`);
  });
});
