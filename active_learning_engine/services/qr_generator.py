"""
QR Code Generator for Session Connection

This module generates QR codes that mobile clients scan
to connect to the WebSocket server.
"""

import json
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from io import BytesIO


def _resolve_public_ws_url() -> Optional[str]:
    """Return QR_PUBLIC_WS_URL env override, normalized to ws:// or wss://.

    Set this env var to a public URL (e.g. from `cloudflared tunnel`) when the
    mobile client cannot reach the LAN IP — the QR will embed it verbatim
    instead of the auto-detected local IP. https/http prefixes are auto-converted.
    """
    raw = os.environ.get("QR_PUBLIC_WS_URL", "").strip().rstrip("/")
    if not raw:
        return None
    if raw.startswith("https://"):
        return "wss://" + raw[len("https://"):]
    if raw.startswith("http://"):
        return "ws://" + raw[len("http://"):]
    return raw  # assume already ws:// or wss://

try:
    import qrcode
    from PIL import Image
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    # Stub so type annotations (Image.Image) don't break at class-definition time
    import types
    Image = types.SimpleNamespace(Image=type(None))


class QRGenerator:
    """
    Generates QR codes for mobile app connection.

    The QR code contains a JSON payload with:
    - WebSocket URL
    - Session ID
    - Timestamp
    """

    QR_TYPE = "safefall_active_session"
    VERSION = 1

    def __init__(self, ws_port: int = 8765):
        """
        Initialize the QR generator.

        Args:
            ws_port: WebSocket server port
        """
        self.ws_port = ws_port
        self._current_session_id: Optional[str] = None

    def generate(self,
                 custom_ip: Optional[str] = None,
                 session_id: Optional[str] = None) -> Tuple[Optional[Image.Image], dict]:
        """
        Generate a QR code for the current session.

        Args:
            custom_ip: Override the auto-detected IP address
            session_id: Custom session ID (auto-generated if None)

        Returns:
            Tuple of (PIL Image of QR code, session data dict)
        """
        if not HAS_QRCODE:
            print("[QR] qrcode library not installed")
            return None, {}

        # Get local IP
        ip_address = custom_ip or self._get_local_ip()

        # Generate session ID
        if session_id:
            self._current_session_id = session_id
        else:
            self._current_session_id = self._generate_session_id()

        # Build session data — public override takes precedence over LAN IP
        session_data = {
            "type": self.QR_TYPE,
            "version": self.VERSION,
            "ws_url": _resolve_public_ws_url() or f"ws://{ip_address}:{self.ws_port}",
            "session_id": self._current_session_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )

        qr.add_data(json.dumps(session_data))
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to PIL Image if needed
        if not isinstance(img, Image.Image):
            img = img.get_image()

        return img, session_data

    def generate_with_info(self,
                          custom_ip: Optional[str] = None) -> Tuple[Optional[Image.Image], str]:
        """
        Generate QR code and return with formatted info string.

        Args:
            custom_ip: Override the auto-detected IP address

        Returns:
            Tuple of (PIL Image, info string for display)
        """
        img, data = self.generate(custom_ip)

        if not data:
            return None, "Failed to generate QR code"

        info = f"""
Session Information
-------------------
Session ID: {data['session_id']}
WebSocket URL: {data['ws_url']}
Created: {data['created_at']}

Scan this QR code with the SafeFall Coach app
to connect and receive real-time feedback.
"""
        return img, info

    def _get_local_ip(self) -> str:
        """
        Get the local IP address of this machine.

        Returns:
            Local IP address string
        """
        try:
            # Create a socket to determine the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)

            # Connect to a public IP (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()

            return ip
        except Exception:
            # Fallback to localhost
            return "127.0.0.1"

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return uuid.uuid4().hex[:8]

    @property
    def current_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._current_session_id

    def get_connection_url(self, custom_ip: Optional[str] = None) -> str:
        """
        Get the WebSocket connection URL.

        Args:
            custom_ip: Override the auto-detected IP address

        Returns:
            WebSocket URL string
        """
        override = _resolve_public_ws_url()
        if override:
            return override
        ip = custom_ip or self._get_local_ip()
        return f"ws://{ip}:{self.ws_port}"
