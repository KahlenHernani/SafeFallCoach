"""Tests for process_frame error isolation — ML failures shouldn't crash the stream.

These tests mock heavy dependencies (torch, cv2, gradio) at the module level
so they can run on any machine without GPU or ML packages installed.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional

import numpy as np

# ── Mock heavy modules before importing app ──
# torch, gradio, and the ML model modules are not available on all dev machines
_mock_torch = MagicMock()
_mock_torch.cuda.is_available.return_value = False

_mock_cv2 = MagicMock()
# cv2.cvtColor: just return input (identity) for testing
_mock_cv2.cvtColor.side_effect = lambda img, code: img
_mock_cv2.putText.return_value = None
_mock_cv2.resize.side_effect = lambda img, size, **kw: img
_mock_cv2.COLOR_BGR2RGB = 4

# Patch at the sys.modules level before any imports
sys.modules.setdefault('torch', _mock_torch)
sys.modules.setdefault('torch.nn', MagicMock())
sys.modules.setdefault('torch.nn.functional', MagicMock())
sys.modules.setdefault('torchvision', MagicMock())
sys.modules.setdefault('torchvision.transforms', MagicMock())
sys.modules.setdefault('torchvision.transforms.v2', MagicMock())
sys.modules.setdefault('gradio', MagicMock())
sys.modules['cv2'] = _mock_cv2

# Now we can safely set the path and import
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import ActiveLearningWizard


@dataclass
class FakePoseResult:
    num_people: int = 0
    keypoints: Optional[np.ndarray] = None


@dataclass
class FakeFallResult:
    detected: bool = False
    confidence: float = 0.0
    timestamp: float = 0.0
    technique_score: Optional[int] = None
    action: Optional[str] = None
    detected_actions: list = None

    def __post_init__(self):
        if self.detected_actions is None:
            self.detected_actions = []


class TestProcessFrameErrors(unittest.TestCase):
    """Test that process_frame degrades gracefully when ML components fail."""

    def _make_wizard(self):
        """Create a wizard with mocked ML components (no GPU needed)."""
        wizard = ActiveLearningWizard()

        # Mock all ML components
        wizard.pose_estimator = MagicMock()
        wizard.sia_detector = MagicMock()
        wizard.feedback_generator = MagicMock()
        wizard.ws_server = MagicMock()
        wizard.ws_server.client_count = 0
        wizard.data_exporter = MagicMock()
        wizard.data_exporter.is_active = False

        return wizard

    def test_pose_estimator_exception_doesnt_crash(self):
        """If pose estimation throws, frame should still be returned."""
        wizard = self._make_wizard()
        wizard.pose_estimator.estimate.side_effect = RuntimeError("CUDA OOM")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result_frame, pose_info, feedback = wizard.process_frame(frame)

        self.assertEqual(result_frame.shape, (480, 640, 3))
        self.assertIn("error", wizard._component_health["pose_estimator"])

    def test_fall_detector_exception_doesnt_crash(self):
        """If fall detection throws, feedback still works."""
        wizard = self._make_wizard()
        wizard.pose_estimator.estimate.return_value = FakePoseResult()
        wizard.pose_estimator.draw_pose.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
        wizard.pose_estimator.calculate_angles.return_value = {}
        wizard.sia_detector.detect.side_effect = RuntimeError("Model corrupted")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result_frame, pose_info, feedback = wizard.process_frame(frame)

        self.assertEqual(result_frame.shape, (480, 640, 3))
        self.assertIn("error", wizard._component_health["fall_detector"])

    def test_all_ml_fails_returns_raw_frame(self):
        """If everything fails, we still get back the raw frame."""
        wizard = self._make_wizard()
        wizard.pose_estimator.estimate.side_effect = Exception("fail1")
        wizard.sia_detector.detect.side_effect = Exception("fail2")

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result_frame, pose_info, feedback = wizard.process_frame(frame)

        self.assertEqual(result_frame.shape, (480, 640, 3))

    def test_paused_frame_returned_when_paused(self):
        """process_and_get_frame should return a PAUSED overlay when paused."""
        wizard = self._make_wizard()
        wizard._paused = True

        result_frame, pose_info, feedback = wizard.process_and_get_frame()

        self.assertEqual(result_frame.shape, (480, 640, 3))
        self.assertEqual(pose_info, "Session paused")

    def test_component_health_tracks_errors(self):
        """Component health dict should reflect errors from each stage."""
        wizard = self._make_wizard()
        wizard.pose_estimator.estimate.side_effect = ValueError("bad input")
        wizard.sia_detector.detect.side_effect = OSError("device lost")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        wizard.process_frame(frame)

        self.assertTrue(
            wizard._component_health["pose_estimator"].startswith("error")
        )
        self.assertTrue(
            wizard._component_health["fall_detector"].startswith("error")
        )


if __name__ == "__main__":
    unittest.main()
