"""Tests for CameraCapture disconnect detection."""

import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

from camera import CameraCapture


class TestCameraDisconnect(unittest.TestCase):
    def test_disconnect_callback_fires_after_consecutive_failures(self):
        """After max_failures consecutive read failures, on_disconnect should fire."""
        callback = MagicMock()
        cam = CameraCapture(camera_index=99, on_disconnect=callback)

        # Simulate: camera "starts" but every read fails
        cam._max_failures = 5  # lower threshold for faster test
        cam._running = True
        cam._frame = None

        # Mock cv2.VideoCapture that always fails
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        cam._cap = mock_cap

        # Run capture loop in thread for a short time
        t = threading.Thread(target=cam._capture_loop, daemon=True)
        t.start()
        time.sleep(0.3)  # Let it run ~10 iterations
        cam._running = False
        t.join(timeout=1.0)

        callback.assert_called_once()
        self.assertTrue(cam.is_disconnected)

    def test_get_frame_returns_none_for_stale_frame(self):
        """get_frame() should return None if last frame is older than threshold."""
        cam = CameraCapture()
        cam._stale_threshold = 0.1  # 100ms for faster test

        import numpy as np
        cam._frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cam._last_frame_time = time.time() - 1.0  # 1s ago (stale)

        result = cam.get_frame()
        self.assertIsNone(result)

    def test_get_frame_returns_frame_when_fresh(self):
        """get_frame() should return frame if it's fresh."""
        cam = CameraCapture()
        cam._stale_threshold = 2.0

        import numpy as np
        cam._frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cam._last_frame_time = time.time()  # just now

        result = cam.get_frame()
        self.assertIsNotNone(result)

    def test_disconnect_state_resets_on_successful_read(self):
        """If camera reconnects (successful read), disconnected flag should reset."""
        import numpy as np

        cam = CameraCapture()
        cam._disconnected = True
        cam._consecutive_failures = 50
        cam._running = True
        cam._start_time = time.time()

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        # Return success repeatedly (loop stops via _running flag)
        mock_cap.read.return_value = (True, fake_frame)
        cam._cap = mock_cap

        t = threading.Thread(target=cam._capture_loop, daemon=True)
        t.start()
        time.sleep(0.15)
        cam._running = False
        t.join(timeout=1.0)

        self.assertFalse(cam.is_disconnected)
        self.assertEqual(cam._consecutive_failures, 0)


if __name__ == "__main__":
    unittest.main()
