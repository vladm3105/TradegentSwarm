import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

function buildBackendCandidates(path: string): string[] {
  // Split path from query string before building the URL so that '?' is not
  // percent-encoded into the pathname (which causes FastAPI to return 404).
  const questionIdx = path.indexOf('?');
  const pathPart = questionIdx === -1 ? path : path.slice(0, questionIdx);
  const queryString = questionIdx === -1 ? '' : path.slice(questionIdx + 1);
  const normalizedPath = pathPart.startsWith('/') ? pathPart : `/${pathPart}`;

  try {
    const primary = new URL(BACKEND_URL);
    primary.pathname = normalizedPath;
    primary.search = queryString ? `?${queryString}` : '';

    const candidates = [primary.toString()];

    // Node's fetch may resolve localhost to ::1 while backend listens on IPv4 only.
    if (primary.hostname === 'localhost') {
      const ipv4Fallback = new URL(primary.toString());
      ipv4Fallback.hostname = '127.0.0.1';
      candidates.push(ipv4Fallback.toString());
    }

    return candidates;
  } catch {
    const qs = queryString ? `?${queryString}` : '';
    return [`http://127.0.0.1:8081${normalizedPath}${qs}`];
  }
}

function createRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function logProxyEvent(level: 'info' | 'warn' | 'error', message: string, context: Record<string, unknown>): void {
  const line = JSON.stringify({
    source: 'frontend.orchestrator.proxy',
    level,
    message,
    timestamp: new Date().toISOString(),
    ...context,
  });
  if (level === 'error') {
    console.error(line);
    return;
  }
  if (level === 'warn') {
    console.warn(line);
    return;
  }
  console.info(line);
}

async function proxyRequest(request: NextRequest, method: 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH') {
  const startedAt = Date.now();
  const { searchParams } = new URL(request.url);
  const path = searchParams.get('path') || '';
  const requestId = request.headers.get('x-client-request-id') || createRequestId();
  const authHeader = request.headers.get('Authorization');

  logProxyEvent('info', 'proxy.request.start', {
    requestId,
    method,
    path,
    hasAuthHeader: !!authHeader,
  });

  let body: unknown = undefined;
  if (method !== 'GET' && method !== 'DELETE') {
    body = await request.json().catch(() => undefined);
  }

  const backendCandidates = buildBackendCandidates(path);
  let lastError: unknown = null;

  for (let i = 0; i < backendCandidates.length; i += 1) {
    const targetUrl = backendCandidates[i];

    try {
      const response = await fetch(targetUrl, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': requestId,
          ...(authHeader ? { Authorization: authHeader } : {}),
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });

      const durationMs = Date.now() - startedAt;
      logProxyEvent('info', 'proxy.request.end', {
        requestId,
        method,
        path,
        targetUrl,
        status: response.status,
        durationMs,
        fallbackUsed: i > 0,
      });

      if (response.status === 204) {
        return new NextResponse(null, { status: 204 });
      }

      const data = await response.json().catch(() => ({}));
      return NextResponse.json(data, { status: response.status });
    } catch (error) {
      lastError = error;
      logProxyEvent('warn', 'proxy.request.attempt_failed', {
        requestId,
        method,
        path,
        targetUrl,
        attempt: i + 1,
        maxAttempts: backendCandidates.length,
        error: String(error),
      });
    }
  }

  const durationMs = Date.now() - startedAt;
  logProxyEvent('error', 'proxy.request.failed', {
    requestId,
    method,
    path,
    durationMs,
    error: String(lastError),
  });
  return NextResponse.json(
    { error: 'Failed to connect to backend', requestId },
    { status: 502 }
  );
}

/**
 * Proxy requests to the FastAPI backend.
 * This allows the frontend to make requests without CORS issues
 * and provides a central point for authentication if needed.
 */
export async function GET(request: NextRequest) {
  return proxyRequest(request, 'GET');
}

export async function POST(request: NextRequest) {
  return proxyRequest(request, 'POST');
}

export async function DELETE(request: NextRequest) {
  return proxyRequest(request, 'DELETE');
}

export async function PUT(request: NextRequest) {
  return proxyRequest(request, 'PUT');
}

export async function PATCH(request: NextRequest) {
  return proxyRequest(request, 'PATCH');
}
