"""FastAPI application for Tradegent Agent UI."""
import sys
import structlog
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add shared module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config import get_settings
from .errors import AgentUIError
from .logging import setup_logging, get_log_file
from .task_manager import get_task_manager
from .dashboard import router as dashboard_router
from .database import close_pool
from .routes import auth_router, admin_router, users_router, settings_router, trades_router, watchlist_router, scanners_router, sessions_router
from .analyses import router as analyses_router
from shared.observability import (
    set_correlation_id,
    extract_from_headers,
    get_correlation_id,
)
from shared.observability.metrics_ui import get_metrics

# Initialize logging before anything else
settings = get_settings()
setup_logging(debug=settings.debug)

log = structlog.get_logger()

# Pydantic models for API
class ChatRequest(BaseModel):
    """Chat request model."""
    session_id: str | None = None
    message: str
    async_mode: bool = False  # If true, returns task_id for polling


class ChatResponse(BaseModel):
    """Chat response model."""
    success: bool
    session_id: str
    text: str | None = None
    a2ui: dict | None = None
    task_id: str | None = None  # For async mode
    error: str | None = None


class TaskStatusResponse(BaseModel):
    """Task status response model."""
    task_id: str
    state: str
    progress: int
    messages: list[str]
    result: dict | None = None
    error: str | None = None


# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Validate required configuration at startup
    try:
        settings.validate_required()
    except ValueError as e:
        log.error("Configuration error - cannot start", error=str(e))
        raise SystemExit(f"Configuration error:\n{e}")

    log.info(
        "Starting Tradegent Agent UI...",
        log_file=str(get_log_file()),
        admin_user=settings.admin_email,
        auth0_configured=settings.auth0_configured,
    )

    # Initialize task manager
    task_manager = await get_task_manager()

    # Initialize coordinator (lazy, on first request)
    # from agent.coordinator import get_coordinator
    # await get_coordinator()

    yield

    # Shutdown
    log.info("Shutting down...")
    await task_manager.stop()
    await close_pool()  # Close database connection pool


# Create FastAPI app (settings already loaded for logging)
app = FastAPI(
    title="Tradegent Agent UI",
    description="Agent-driven trading interface with A2UI components",
    version="0.1.0",
    lifespan=lifespan,
)

# Build CORS origins list
cors_origins = [settings.frontend_url, "http://localhost:3000", "http://localhost:3001", "http://localhost:8081"]
if settings.auth0_domain:
    cors_origins.append(f"https://{settings.auth0_domain}")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(analyses_router)
app.include_router(trades_router)
app.include_router(watchlist_router)
app.include_router(scanners_router)
app.include_router(sessions_router)


# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    "/",
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/auth/sync-user",  # Called during login flow
]


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting for authenticated users."""
    if not settings.rate_limit_enabled:
        return await call_next(request)

    # Skip rate limiting for public endpoints
    if request.url.path in PUBLIC_ENDPOINTS:
        return await call_next(request)

    # Check for user context (set by auth middleware)
    user = getattr(request.state, "user", None)
    if user:
        from .rate_limit import get_rate_limiter
        rate_limiter = get_rate_limiter()
        try:
            await rate_limiter.check(user.sub)
        except HTTPException:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
            )

    return await call_next(request)


# Correlation ID middleware for distributed tracing
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    """Add correlation ID to requests for distributed tracing.

    Extracts B3 headers or generates new correlation ID.
    Binds to structlog context for automatic inclusion in logs.
    """
    import time

    start_time = time.perf_counter()

    # Extract or generate correlation ID
    correlation_id = extract_from_headers(dict(request.headers))
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    # Set in context for logging and downstream propagation
    set_correlation_id(correlation_id)
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # Process request
    response = await call_next(request)

    # Add correlation ID to response headers
    response.headers["X-B3-TraceId"] = correlation_id
    response.headers["X-Correlation-Id"] = correlation_id

    # Record metrics
    duration_ms = (time.perf_counter() - start_time) * 1000
    metrics = get_metrics()
    metrics.record_http_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    return response


# Static files
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    """Serve the main UI page."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Tradegent Agent UI", "docs": "/docs"}


# Error handler
@app.exception_handler(AgentUIError)
async def agent_ui_error_handler(request, exc: AgentUIError):
    """Handle AgentUIError exceptions."""
    return JSONResponse(
        status_code=400 if exc.recoverable else 500,
        content={
            "success": False,
            "error": exc.message,
            "code": exc.code,
            "recoverable": exc.recoverable,
        },
    )


# Health endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from agent.mcp_client import get_mcp_pool

    try:
        pool = await get_mcp_pool()
        mcp_health = await pool.health_check()

        return {
            "status": "healthy" if mcp_health.any_healthy() else "degraded",
            "version": "0.1.0",
            "mcp_servers": {
                "ib_mcp": mcp_health.ib_mcp,
                "trading_rag": mcp_health.trading_rag,
                "trading_graph": mcp_health.trading_graph,
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe."""
    return {"ready": True}


# Required auth dependency
async def get_required_user(request: Request):
    """Get current authenticated user. Authentication is ALWAYS required."""
    from .auth import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=auth_header[7:]  # Remove "Bearer " prefix
    )
    return await get_current_user(credentials)


# Chat endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Process a chat message.

    For quick queries, returns response immediately.
    For async_mode=True, returns task_id for polling.

    Authentication is ALWAYS required.
    """
    from agent.coordinator import get_coordinator

    # Get authenticated user (required)
    user = await get_required_user(req)
    session_id = user.sub

    if request.async_mode:
        # Submit to task queue
        task_manager = await get_task_manager()
        task_id = await task_manager.submit(
            session_id=session_id,
            intent="chat",
            query=request.message,
        )

        return ChatResponse(
            success=True,
            session_id=session_id,
            task_id=task_id,
        )

    # Synchronous processing
    try:
        coordinator = await get_coordinator()
        response = await coordinator.process(session_id, request.message)

        return ChatResponse(
            success=response.success,
            session_id=session_id,
            text=response.text,
            a2ui=response.a2ui,
            error=response.error,
        )

    except AgentUIError as e:
        return ChatResponse(
            success=False,
            session_id=session_id,
            error=e.message,
        )
    except Exception as e:
        log.error("Chat processing failed", error=str(e))
        return ChatResponse(
            success=False,
            session_id=session_id,
            error=str(e),
        )


@app.get("/api/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get task status by ID."""
    task_manager = await get_task_manager()
    task = await task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task.task_id,
        state=task.state.value,
        progress=task.progress,
        messages=task.messages[-10:],
        result=task.result,
        error=task.error,
    )


@app.delete("/api/task/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or running task."""
    task_manager = await get_task_manager()
    cancelled = await task_manager.cancel_task(task_id)

    if not cancelled:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")

    return {"success": True, "task_id": task_id}


@app.get("/api/stats")
async def get_stats(req: Request):
    """Get system statistics. Requires authentication."""
    await get_required_user(req)

    task_manager = await get_task_manager()
    task_stats = task_manager.get_stats()

    from agent.mcp_client import get_mcp_pool
    pool = await get_mcp_pool()
    mcp_health = await pool.health_check()

    return {
        "tasks": task_stats,
        "mcp": {
            "ib_mcp": mcp_health.ib_mcp,
            "trading_rag": mcp_health.trading_rag,
            "trading_graph": mcp_health.trading_graph,
        },
    }


# WebSocket endpoint for real-time communication
class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        log.info("WebSocket connected", session_id=session_id)

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        log.info("WebSocket disconnected", session_id=session_id)

    async def send_message(self, session_id: str, message: dict):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(message)


manager = ConnectionManager()


async def validate_websocket_token(websocket: WebSocket):
    """Validate WebSocket connection token.

    Token can be passed via:
    - Query parameter: ?token=xxx
    - Protocol header (subprotocol)
    """
    from .auth import validate_token, UserClaims

    # Try query parameter first
    token = websocket.query_params.get("token")

    if not token:
        return None

    try:
        user = await validate_token(token)
        return user
    except Exception as e:
        log.warning("WebSocket auth failed", error=str(e))
        return None


@app.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for agent communication.

    Protocol:
    - Client sends: {"type": "message", "content": "..."}
    - Client sends: {"type": "subscribe", "task_id": "..."}
    - Server sends: {"type": "response", "content": {...}}
    - Server sends: {"type": "progress", "task_id": "...", ...}

    Authentication:
    - Pass token via query parameter: ws://host/ws/agent?token=xxx
    - Authentication is ALWAYS required.
    """
    # Validate token - authentication is always required
    user = await validate_websocket_token(websocket)

    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    session_id = user.sub
    await manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                # Process chat message
                content = data.get("content", "")
                async_mode = data.get("async", False)

                if async_mode:
                    # Submit to task queue and stream progress
                    task_manager = await get_task_manager()
                    task_id = await task_manager.submit(
                        session_id=session_id,
                        intent="chat",
                        query=content,
                    )

                    await websocket.send_json({
                        "type": "task_created",
                        "task_id": task_id,
                    })

                    # Stream progress
                    async for progress in task_manager.stream_progress(task_id):
                        await websocket.send_json(progress)

                else:
                    # Synchronous processing
                    from agent.coordinator import get_coordinator

                    try:
                        coordinator = await get_coordinator()
                        response = await coordinator.process(session_id, content)

                        await websocket.send_json({
                            "type": "response",
                            "success": response.success,
                            "text": response.text,
                            "a2ui": response.a2ui,
                            "error": response.error,
                        })

                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "error": str(e),
                        })

            elif msg_type == "subscribe":
                # Subscribe to task progress
                task_id = data.get("task_id")
                if task_id:
                    task_manager = await get_task_manager()
                    async for progress in task_manager.stream_progress(task_id):
                        await websocket.send_json(progress)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        log.error("WebSocket error", session_id=session_id, error=str(e))
        manager.disconnect(session_id)


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "tradegent_ui.server.main:app",
        host=settings.agui_host,
        port=settings.agui_port,
        reload=settings.debug,
    )
