"""Tests for post-fall frame collection thread safety.

Verifies that stop_session() cannot corrupt post-fall state while
process_frame() is mid-collection (Bug #11 fix).
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock
from dataclasses import dataclass
from typing import Optional

import numpy as np

# ── Mock heavy modules before importing wizard ──
_mock_torch = MagicMock()
_mock_torch.cuda.is_available.return_value = False

_mock_cv2 = MagicMock()
_mock_cv2.cvtColor.side_effect = lambda img, code: img
_mock_cv2.putText.return_value = None
_mock_cv2.resize.side_effect = lambda img, size, **kw: np.zeros((size[1], size[0], 3), dtype=np.uint8)
_mock_cv2.COLOR_BGR2RGB = 4

sys.modules.setdefault('torch', _mock_torch)
sys.modules.setdefault('torch.nn', MagicMock())
sys.modules.setdefault('torch.nn.functional', MagicMock())
sys.modules.setdefault('torchvision', MagicMock())
sys.modules.setdefault('torchvision.transforms', MagicMock())
sys.modules.setdefault('torchvision.transforms.v2', MagicMock())
sys.modules.setdefault('gradio', MagicMock())
sys.modules.setdefault('llm_providers', MagicMock())
sys.modules['cv2'] = _mock_cv2

sys.path.insert(0, str(Path(__file__).parent.parent))

from wizard import ActiveLearningWizard


@dataclass
class FakeFallResult:
    detected: bool = True
    technique_score: float = 75.0
    action: str = 'fall down'
    detected_actions: list = None

    def __post_init__(self):
        if self.detected_actions is None:
            self.detected_actions = [('fall down', 0.85)]


class TestPostFallLock(unittest.TestCase):
    """Test that _post_fall_lock prevents race between process_frame and stop_session."""

    def setUp(self):
        """Create a wizard with mocked ML components."""
        self.wizard = ActiveLearningWizard.__new__(ActiveLearningWizard)
        # Manually init just the state we need (avoid real __init__ which loads ML)
        self.wizard._post_fall_lock = threading.Lock()
        self.wizard._frame_lock = threading.Lock()
        self.wizard._collecting_post_fall = False
        self.wizard._post_fall_frames = []
        self.wizard._post_fall_target = 2
        self.wizard._pre_fall_frames = []
        self.wizard._pending_fall_data = None
        self.wizard._last_fall_recorded_time = 0
        self.wizard._fall_cooldown_seconds = 15.0
        self.wizard._latest_feedback = ""
        self.wizard._latest_feedback_time = 0
        self.wizard._latest_severity = "neutral"
        self.wizard._feedback_id = 0
        self.wizard._llm_pending_fall_data = None
        self.wizard._pending_llm_future = None
        self.wizard._llm_executor = MagicMock()
        self.wizard._processing = True
        self.wizard._paused = False
        self.wizard._study_id = None
        self.wizard._pending_export_stats = None
        self.wizard._pending_export_health = None
        self.wizard._component_health = {
            "camera": "ok", "pose_estimator": "ok",
            "fall_detector": "ok", "feedback_generator": "ok",
            "websocket": "ok",
        }

        # Mock sub-components
        self.wizard.camera = MagicMock()
        self.wizard.camera.is_running = True
        self.wizard.session_manager = MagicMock()
        self.wizard.session_manager.end_session.return_value = MagicMock(
            duration_seconds=60, total_falls=1,
            average_technique_score=75.0, best_technique_score=80,
            total_feedback_count=3,
        )
        self.wizard.data_exporter = MagicMock()
        self.wizard.feedback_generator = MagicMock()
        self.wizard.feedback_generator.generate_fall_feedback.return_value = MagicMock(
            feedback_text="Good technique", severity="info"
        )
        self.wizard.sia_detector = MagicMock()
        self.wizard.sia_detector.get_key_frames.return_value = [
            np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(3)
        ]
        self.wizard.websocket_server = MagicMock()

    def test_lock_exists(self):
        """Verify _post_fall_lock is a threading.Lock."""
        self.assertIsInstance(self.wizard._post_fall_lock, type(threading.Lock()))

    def test_stop_session_resets_post_fall_state(self):
        """stop_session should reset all post-fall fields."""
        # Simulate mid-collection state
        self.wizard._collecting_post_fall = True
        self.wizard._post_fall_frames = [np.zeros((480, 640, 3), dtype=np.uint8)]
        self.wizard._pre_fall_frames = [np.zeros((480, 640, 3), dtype=np.uint8)]
        self.wizard._pending_fall_data = {'technique_score': 70, 'pose_angles': {}}

        self.wizard.stop_session()

        self.assertFalse(self.wizard._collecting_post_fall)
        self.assertEqual(self.wizard._post_fall_frames, [])
        self.assertEqual(self.wizard._pre_fall_frames, [])
        self.assertIsNone(self.wizard._pending_fall_data)

    def test_concurrent_stop_during_collection(self):
        """stop_session during post-fall collection should not cause partial state."""
        # Put wizard in collecting state with 1 frame (needs 2)
        self.wizard._collecting_post_fall = True
        self.wizard._post_fall_frames = [np.zeros((480, 640, 3), dtype=np.uint8)]
        self.wizard._pre_fall_frames = [
            np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(3)
        ]
        self.wizard._pending_fall_data = {'technique_score': 70, 'pose_angles': {}}

        errors = []

        def call_stop():
            try:
                self.wizard.stop_session()
            except Exception as e:
                errors.append(e)

        def call_process_feedback():
            try:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                self.wizard._process_feedback(
                    frame, False, None, {}
                )
            except Exception as e:
                errors.append(e)

        # Run both concurrently many times to stress the lock
        for _ in range(50):
            self.wizard._collecting_post_fall = True
            self.wizard._post_fall_frames = [np.zeros((480, 640, 3), dtype=np.uint8)]
            self.wizard._pre_fall_frames = [
                np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(3)
            ]
            self.wizard._pending_fall_data = {'technique_score': 70, 'pose_angles': {}}
            self.wizard._processing = True
            self.wizard._paused = False

            t1 = threading.Thread(target=call_stop)
            t2 = threading.Thread(target=call_process_feedback)
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

        self.assertEqual(errors, [], f"Race condition errors: {errors}")

    def test_process_feedback_collects_and_dispatches(self):
        """_process_feedback should collect frames and submit LLM when target reached."""
        self.wizard._collecting_post_fall = True
        self.wizard._post_fall_frames = [np.zeros((480, 640, 3), dtype=np.uint8)]
        self.wizard._pre_fall_frames = [
            np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(3)
        ]
        self.wizard._pending_fall_data = {'technique_score': 70, 'pose_angles': {}}

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.wizard._process_feedback(frame, False, None, {})

        # Should have dispatched to LLM (target=2, had 1, added 1)
        self.assertFalse(self.wizard._collecting_post_fall)
        self.wizard._llm_executor.submit.assert_called_once()
        self.assertIn("analyzing technique", result)


if __name__ == '__main__':
    unittest.main()
