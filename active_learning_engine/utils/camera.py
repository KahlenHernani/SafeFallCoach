"""
Camera Capture Utilities

This module provides camera capture functionality for the desktop wizard.
"""

import threading
import time
from typing import Optional, Tuple, Callable
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class CameraCapture:
    """
    Manages camera capture for real-time video processing.

    Provides:
    - Continuous frame capture in background thread
    - Frame rate control
    - Resolution settings
    - Thread-safe frame access
    - Disconnect detection after consecutive read failures
    """

    def __init__(self,
                 camera_index: int = 0,
                 width: int = 640,
                 height: int = 480,
                 fps: int = 30,
                 on_disconnect: Optional[Callable[[], None]] = None):
        """
        Initialize the camera capture.

        Args:
            camera_index: Camera device index (usually 0 for default)
            width: Desired frame width
            height: Desired frame height
            fps: Target frames per second
            on_disconnect: Callback fired when camera disconnects
        """
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.target_fps = fps

        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Callbacks
        self._on_frame: Optional[Callable[[np.ndarray], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = on_disconnect

        # Stats
        self._frame_count = 0
        self._start_time = 0.0
        self._actual_fps = 0.0

        # Disconnect detection
        self._last_frame_time: float = 0.0
        self._disconnected: bool = False
        self._consecutive_failures: int = 0
        self._max_failures: int = 30  # ~1s at 30fps
        self._stale_threshold: float = 2.0  # seconds before frame considered stale

    def start(self) -> bool:
        """
        Start camera capture.

        Returns:
            True if camera started successfully
        """
        if not HAS_CV2:
            print("[Camera] OpenCV not installed")
            return False

        if self._running:
            return True

        # Open camera
        self._cap = cv2.VideoCapture(self.camera_index)

        if not self._cap.isOpened():
            print(f"[Camera] Failed to open camera {self.camera_index}")
            return False

        # Set resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.target_fps)

        # Start capture thread
        self._running = True
        self._start_time = time.time()
        self._frame_count = 0
        self._disconnected = False
        self._consecutive_failures = 0
        self._last_frame_time = 0.0
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        print(f"[Camera] Started capture: {self.width}x{self.height} @ {self.target_fps}fps")
        return True

    def stop(self):
        """Stop camera capture."""
        self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)

        if self._cap:
            self._cap.release()
            self._cap = None

        print("[Camera] Stopped capture")

    def _capture_loop(self):
        """Main capture loop running in background thread."""
        frame_time = 1.0 / self.target_fps

        while self._running and self._cap and self._cap.isOpened():
            loop_start = time.time()

            ret, frame = self._cap.read()

            if ret and frame is not None:
                with self._frame_lock:
                    self._frame = frame
                    self._frame_count += 1
                    self._last_frame_time = time.time()
                    self._consecutive_failures = 0
                    if self._disconnected:
                        self._disconnected = False
                        print("[Camera] Reconnected")

                # Call frame callback if set
                if self._on_frame:
                    try:
                        self._on_frame(frame)
                    except Exception as e:
                        print(f"[Camera] Frame callback error: {e}")

                # Update FPS calculation
                elapsed = time.time() - self._start_time
                if elapsed > 0:
                    self._actual_fps = self._frame_count / elapsed
            else:
                self._consecutive_failures += 1
                if (self._consecutive_failures >= self._max_failures
                        and not self._disconnected):
                    self._disconnected = True
                    print(f"[Camera] Disconnected after {self._consecutive_failures} consecutive failures")
                    if self._on_disconnect:
                        try:
                            self._on_disconnect()
                        except Exception as e:
                            print(f"[Camera] Disconnect callback error: {e}")

            # Frame rate limiting
            elapsed = time.time() - loop_start
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get the most recent frame.

        Returns None if no frame available or if the last frame is stale
        (older than stale_threshold seconds), which prevents returning a
        frozen frame forever after a camera disconnect.

        Returns:
            BGR image as numpy array, or None if no frame available
        """
        with self._frame_lock:
            if self._frame is None:
                return None
            # Return None if frame is stale (camera likely disconnected)
            if (self._last_frame_time > 0
                    and time.time() - self._last_frame_time > self._stale_threshold):
                return None
            return self._frame.copy()

    def get_frame_rgb(self) -> Optional[np.ndarray]:
        """
        Get the most recent frame in RGB format.

        Returns:
            RGB image as numpy array, or None if no frame available
        """
        frame = self.get_frame()
        if frame is None:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def set_frame_callback(self, callback: Optional[Callable[[np.ndarray], None]]):
        """
        Set a callback to be called for each new frame.

        Args:
            callback: Function that takes a BGR frame as input
        """
        self._on_frame = callback

    @property
    def is_running(self) -> bool:
        """Check if camera is running."""
        return self._running

    @property
    def is_disconnected(self) -> bool:
        """Check if camera has disconnected."""
        return self._disconnected

    @property
    def actual_fps(self) -> float:
        """Get actual achieved FPS."""
        return self._actual_fps

    @property
    def frame_count(self) -> int:
        """Get total frames captured."""
        return self._frame_count

    def get_resolution(self) -> Tuple[int, int]:
        """
        Get actual camera resolution.

        Returns:
            Tuple of (width, height)
        """
        if self._cap and self._cap.isOpened():
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (w, h)
        return (self.width, self.height)

    @staticmethod
    def list_cameras(max_index: int = 5) -> list:
        """
        List available camera indices.

        Args:
            max_index: Maximum camera index to check

        Returns:
            List of available camera indices
        """
        if not HAS_CV2:
            return []

        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()

        return available
