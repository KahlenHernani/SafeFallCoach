"""
WebSocket Server for Mobile Communication

This module provides a WebSocket server that broadcasts
feedback messages to connected mobile clients.
"""

import asyncio
import json
import time
from typing import Set, Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict
import threading


@dataclass
class FeedbackMessage:
    """Feedback message to send to mobile clients."""
    type: str = "feedback"
    timestamp: str = ""
    message: str = ""
    severity: str = "info"
    pose_score: int = 0


@dataclass
class FallEventMessage:
    """Fall event message to send to mobile clients."""
    type: str = "fall_event"
    timestamp: str = ""
    technique_score: int = 0
    feedback: str = ""


@dataclass
class SessionStatusMessage:
    """Session status message to send to mobile clients."""
    type: str = "session_status"
    status: str = "active"
    duration_seconds: int = 0
    falls_practiced: int = 0


class WebSocketServer:
    """
    AsyncIO WebSocket server for broadcasting to mobile clients.

    Runs in a separate thread to avoid blocking the main Gradio thread.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        """
        Initialize the WebSocket server.

        Args:
            host: Host address to bind to
            port: Port number to listen on
        """
        self.host = host
        self.port = port
        self._clients: Set = set()
        self._server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._session_start_time: Optional[float] = None  # deprecated: use SessionManager
        self._start_event = threading.Event()
        self._start_error: Optional[str] = None
        self._status_provider: Optional[Callable[[], Optional[SessionStatusMessage]]] = None

    def start(self) -> bool:
        """
        Start the WebSocket server in a background thread.

        Returns:
            True if server started successfully, False if port in use or error.
        """
        if self._running:
            return True

        self._start_event.clear()
        self._start_error = None
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        # Wait for server to confirm startup (up to 3s)
        if not self._start_event.wait(timeout=3.0):
            self._running = False
            self._start_error = "Server startup timed out"
            print(f"[WebSocket] {self._start_error}")
            return False

        if self._start_error:
            self._running = False
            print(f"[WebSocket] Failed to start: {self._start_error}")
            return False

        print(f"[WebSocket] Server started on ws://{self.host}:{self.port}")
        return True

    def set_status_provider(self, provider: Callable[[], Optional['SessionStatusMessage']]):
        """
        Set a callback that returns the current SessionStatusMessage.

        This enables periodic status broadcasting (every 1s) so mobile
        clients stay in sync with the server's authoritative session timer.

        Args:
            provider: Callable returning SessionStatusMessage or None if no session.
        """
        self._status_provider = provider

    def stop(self):
        """Stop the WebSocket server."""
        self._running = False

        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=2.0)

        print("[WebSocket] Server stopped")

    def _run_server(self):
        """Run the server in the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            self._start_error = str(e)
            self._start_event.set()
            print(f"[WebSocket] Server error: {e}")
        finally:
            self._loop.close()

    async def _serve(self):
        """Main server coroutine."""
        try:
            import websockets
        except ImportError:
            print("[WebSocket] websockets library not installed")
            return

        async def handler(websocket):
            """Handle a new WebSocket connection."""
            self._clients.add(websocket)
            client_addr = websocket.remote_address
            print(f"[WebSocket] Client connected: {client_addr}")

            # Start session timing if first client
            if self._session_start_time is None:
                self._session_start_time = time.time()

            try:
                # Send initial session status
                await self._send_to_client(websocket, self._get_session_status())

                # Keep connection alive and handle incoming messages
                async for message in websocket:
                    # Handle any incoming messages from mobile (future use)
                    try:
                        data = json.loads(message)
                        await self._handle_client_message(websocket, data)
                    except json.JSONDecodeError:
                        pass

            except Exception as e:
                print(f"[WebSocket] Client error: {e}")
            finally:
                self._clients.discard(websocket)
                print(f"[WebSocket] Client disconnected: {client_addr}")

        try:
            self._server = await websockets.serve(handler, self.host, self.port)
        except OSError as e:
            self._start_error = f"Port {self.port} in use: {e}"
            self._start_event.set()
            return

        # Signal successful startup
        self._start_event.set()

        # Run until stopped; broadcast session status every ~1s
        tick = 0
        while self._running:
            await asyncio.sleep(0.1)
            tick += 1
            if tick >= 10 and self._clients and self._status_provider:
                tick = 0
                try:
                    status_msg = self._status_provider()
                    if status_msg is not None:
                        await self._broadcast_async(status_msg)
                except Exception:
                    pass

        self._server.close()
        await self._server.wait_closed()

    async def _handle_client_message(self, websocket, data: Dict[str, Any]):
        """Handle incoming message from a mobile client."""
        msg_type = data.get('type')

        if msg_type == 'ping':
            await self._send_to_client(websocket, {'type': 'pong'})

    async def _send_to_client(self, websocket, message: Any):
        """Send a message to a specific client."""
        try:
            if hasattr(message, '__dataclass_fields__'):
                data = asdict(message)
            else:
                data = message
            await websocket.send(json.dumps(data))
        except Exception as e:
            print(f"[WebSocket] Send error: {e}")

    def broadcast(self, message: Any):
        """
        Broadcast a message to all connected clients.

        Args:
            message: Message to broadcast (dataclass or dict)
        """
        if not self._loop or not self._clients:
            return

        asyncio.run_coroutine_threadsafe(
            self._broadcast_async(message),
            self._loop
        )

    async def _broadcast_async(self, message: Any):
        """Async broadcast implementation."""
        if not self._clients:
            return

        if hasattr(message, '__dataclass_fields__'):
            data = json.dumps(asdict(message))
        else:
            data = json.dumps(message)

        # Send to all clients
        disconnected = set()
        for client in self._clients:
            try:
                await client.send(data)
            except Exception:
                disconnected.add(client)

        # Remove disconnected clients
        self._clients -= disconnected

    def send_feedback(self, message: str, severity: str = "info", pose_score: int = 0):
        """
        Send a feedback message to all clients.

        Args:
            message: The feedback text
            severity: 'info', 'warning', or 'success'
            pose_score: Current pose score (0-100)
        """
        feedback = FeedbackMessage(
            timestamp=self._get_timestamp(),
            message=message,
            severity=severity,
            pose_score=pose_score
        )
        self.broadcast(feedback)

    def send_fall_event(self, technique_score: int, feedback: str,
                        total_falls: int = 0, duration_seconds: int = 0):
        """
        Send a fall detection event to all clients.

        Args:
            technique_score: Score for the fall technique (0-100)
            feedback: Feedback text about the fall
            total_falls: Total falls from SessionManager (single source of truth)
            duration_seconds: Session duration from SessionManager (single source of truth)
        """
        event = FallEventMessage(
            timestamp=self._get_timestamp(),
            technique_score=technique_score,
            feedback=feedback
        )
        self.broadcast(event)

        # Also send updated session status
        self.send_session_status(total_falls=total_falls, duration_seconds=duration_seconds)

    def send_session_status(self, status: str = "active", total_falls: int = 0,
                            duration_seconds: int = 0):
        """
        Send session status update to all clients.

        Args:
            status: 'active', 'paused', or 'ended'
            total_falls: Total falls from SessionManager (single source of truth)
            duration_seconds: Session duration from SessionManager (single source of truth)
        """
        self.broadcast(self._get_session_status(status, total_falls, duration_seconds))

    def _get_session_status(self, status: str = "active",
                            total_falls: int = 0,
                            duration_seconds: int = 0) -> SessionStatusMessage:
        """Get current session status message."""
        return SessionStatusMessage(
            status=status,
            duration_seconds=duration_seconds,
            falls_practiced=total_falls
        )

    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def reset_session(self):
        """Reset session statistics."""
        self._session_start_time = None

    @property
    def client_count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    @property
    def url(self) -> str:
        """Get the WebSocket URL for clients."""
        return f"ws://{self.host}:{self.port}"
