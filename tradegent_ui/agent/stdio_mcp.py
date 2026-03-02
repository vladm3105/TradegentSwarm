"""MCP client using stdio transport (JSON-RPC over subprocess)."""
import asyncio
import json
import structlog
from dataclasses import dataclass
from typing import Any

log = structlog.get_logger()


@dataclass
class MCPResponse:
    """Response from MCP tool call."""

    success: bool
    result: Any | None = None
    error: str | None = None


class StdioMCPClient:
    """MCP client using stdio transport (JSON-RPC over subprocess).

    Communicates with MCP servers via stdin/stdout using JSON-RPC 2.0 protocol.
    Handles MCP initialization handshake before tool calls.
    """

    def __init__(self, name: str, command: str, cwd: str, env: dict[str, str] | None = None):
        """Initialize stdio MCP client.

        Args:
            name: Server name for logging
            command: Shell command to start the MCP server
            cwd: Working directory for the subprocess
            env: Additional environment variables
        """
        self.name = name
        self.command = command
        self.cwd = cwd
        self.env = env or {}
        self._proc: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._started = False
        self._initialized = False  # MCP handshake completed

    async def start(self) -> bool:
        """Start the MCP subprocess and perform initialization handshake.

        Returns:
            True if started and initialized successfully, False otherwise.
        """
        if self._started and self._initialized:
            return True

        try:
            import os
            env = {**os.environ, **self.env}

            self._proc = await asyncio.create_subprocess_shell(
                self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                env=env,
            )

            # Start response reader task
            self._reader_task = asyncio.create_task(self._read_responses())
            self._started = True

            log.info("MCP server started", server=self.name, pid=self._proc.pid)

            # Perform MCP initialization handshake
            init_success = await self._initialize_handshake()
            if not init_success:
                log.error("MCP initialization handshake failed", server=self.name)
                return False

            return True

        except Exception as e:
            log.error("Failed to start MCP server", server=self.name, error=str(e))
            return False

    async def _initialize_handshake(self) -> bool:
        """Perform MCP initialization handshake.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        try:
            # Step 1: Send initialize request
            init_request = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "clientInfo": {
                    "name": "tradegent-ui",
                    "version": "1.0.0",
                },
            }

            response = await self._send_request("initialize", init_request, timeout=30.0)
            if response is None:
                log.error("MCP initialize request failed", server=self.name)
                return False

            log.debug("MCP initialize response", server=self.name, response=response)

            # Step 2: Send initialized notification (no response expected)
            await self._send_notification("notifications/initialized", {})

            self._initialized = True
            log.info("MCP initialization complete", server=self.name)
            return True

        except Exception as e:
            log.error("MCP initialization failed", server=self.name, error=str(e))
            return False

    async def _send_notification(self, method: str, params: dict):
        """Send a JSON-RPC notification (no response expected).

        Args:
            method: Method name
            params: Parameters
        """
        if not self._proc or not self._proc.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        try:
            notification_line = json.dumps(notification) + "\n"
            self._proc.stdin.write(notification_line.encode())
            await self._proc.stdin.drain()
            log.debug("MCP notification sent", server=self.name, method=method)
        except Exception as e:
            log.error("Failed to send notification", server=self.name, method=method, error=str(e))

    async def _send_request(self, method: str, params: dict, timeout: float = 60.0) -> Any | None:
        """Send a JSON-RPC request and wait for response.

        Args:
            method: Method name
            params: Parameters
            timeout: Timeout in seconds

        Returns:
            Response result or None on error
        """
        if not self._proc or not self._proc.stdin:
            return None

        async with self._lock:
            self._request_id += 1
            request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # Create future for response
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future

        try:
            request_line = json.dumps(request) + "\n"
            self._proc.stdin.write(request_line.encode())
            await self._proc.stdin.drain()

            log.debug("MCP request sent", server=self.name, method=method, id=request_id)

            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            log.warning("MCP request timeout", server=self.name, method=method)
            return None

        except Exception as e:
            self._pending.pop(request_id, None)
            log.error("MCP request failed", server=self.name, method=method, error=str(e))
            return None

    async def call(self, method: str, params: dict | None = None, timeout: float = 60.0) -> MCPResponse:
        """Call an MCP tool via JSON-RPC.

        Args:
            method: Tool/method name to call
            params: Parameters for the tool
            timeout: Timeout in seconds

        Returns:
            MCPResponse with result or error
        """
        # Ensure server is started and initialized
        if not self._started or not self._initialized:
            started = await self.start()
            if not started:
                return MCPResponse(success=False, error="Failed to start/initialize MCP server")

        try:
            result = await self._send_request(method, params or {}, timeout=timeout)
            if result is None:
                return MCPResponse(success=False, error="Request failed or timed out")

            # Handle MCP tool call result format
            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    # Extract text from TextContent
                    text_content = content[0]
                    if isinstance(text_content, dict) and "text" in text_content:
                        try:
                            # Parse JSON from text response
                            return MCPResponse(success=True, result=json.loads(text_content["text"]))
                        except json.JSONDecodeError:
                            return MCPResponse(success=True, result=text_content["text"])
                    return MCPResponse(success=True, result=text_content)
                return MCPResponse(success=True, result=content)

            return MCPResponse(success=True, result=result)

        except Exception as e:
            log.error("MCP call failed", server=self.name, method=method, error=str(e))
            return MCPResponse(success=False, error=str(e))

    async def _read_responses(self):
        """Read JSON-RPC responses from subprocess stdout."""
        if not self._proc or not self._proc.stdout:
            return

        while not self._proc.stdout.at_eof():
            try:
                line = await self._proc.stdout.readline()
                if not line:
                    break

                line_str = line.decode().strip()
                if not line_str:
                    continue

                try:
                    response = json.loads(line_str)
                except json.JSONDecodeError:
                    # May be log output, skip
                    continue

                req_id = response.get("id")
                if req_id is None:
                    # Notification, no response expected
                    continue

                if req_id in self._pending:
                    future = self._pending.pop(req_id)
                    if "error" in response:
                        error = response["error"]
                        error_msg = error.get("message", str(error))
                        future.set_exception(Exception(error_msg))
                    else:
                        future.set_result(response.get("result"))

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Error reading MCP response", server=self.name, error=str(e))

        log.info("MCP reader task ended", server=self.name)

    async def stop(self):
        """Stop the MCP subprocess."""
        self._started = False
        self._initialized = False

        # Cancel pending requests
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

        # Cancel reader task
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        # Terminate subprocess
        if self._proc:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
            except Exception:
                pass

        log.info("MCP server stopped", server=self.name)

    async def health_check(self) -> bool:
        """Check if MCP server is healthy.

        Returns:
            True if process is running and initialized, False otherwise.
        """
        if not self._started or not self._proc:
            return False

        # Check if process is still running
        if self._proc.returncode is not None:
            return False

        # Check if initialized
        return self._initialized

    def __del__(self):
        """Cleanup on deletion."""
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
