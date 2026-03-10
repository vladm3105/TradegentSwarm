/**
 * Resolve websocket endpoints from NEXT_PUBLIC_WS_URL and construct
 * authenticated sockets using the backend-required bearer subprotocol.
 *
 * Resolution strategy (in order):
 * 1. If running in a browser, derive the WS URL from window.location so the
 *    connection always uses the same host/port as the page — critical for
 *    remote-dev environments (VS Code Remote, SSH tunnels) where only the
 *    frontend port is forwarded and the custom server.js proxies /ws/* to the
 *    backend.
 * 2. Fall back to NEXT_PUBLIC_WS_URL (used during SSR / server-side init).
 * 3. Fall back to hardcoded local address.
 */

export function resolveWebSocketEndpoint(
  configuredUrl: string | undefined,
  endpointPath: '/ws/agent' | '/ws/stream',
  fallbackOrigin: string = 'ws://localhost:8081'
): string {
  // Browser: always derive from current page origin so tunnels/remote hosts work
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}${endpointPath}`;
  }

  // Server-side (SSR): use env var or fallback
  const raw = configuredUrl || fallbackOrigin;

  try {
    const parsed = new URL(raw);
    parsed.pathname = endpointPath;
    parsed.search = '';
    return parsed.toString();
  } catch {
    // Fallback for malformed env values.
    const fallback = new URL(fallbackOrigin);
    fallback.pathname = endpointPath;
    fallback.search = '';
    return fallback.toString();
  }
}

export function createAuthenticatedWebSocket(
  url: string,
  token: string | null
): WebSocket {
  if (token) {
    return new WebSocket(url, ['bearer', token]);
  }
  return new WebSocket(url);
}
