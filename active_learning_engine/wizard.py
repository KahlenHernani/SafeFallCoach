#!/usr/bin/env python3
"""
ActiveLearningWizard — framework-agnostic ML pipeline orchestrator.

Coordinates camera capture, pose estimation, fall detection, LLM feedback,
mobile WebSocket communication, and session data export for IRB research.

Used by both server.py (FastAPI) and app_gradio.py (legacy Gradio UI).
"""

import re
import time
import threading
import os
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional, List, Dict
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from active_learning_engine.models import SiADetector, PoseEstimator, FeedbackGenerator
from active_learning_engine.services import WebSocketServer, QRGenerator, SessionManager
from active_learning_engine.services.session_manager import SessionState
from active_learning_engine.services.session_data_exporter import SessionDataExporter
from active_learning_engine.utils import CameraCapture


class ActiveLearningWizard:
    """
    Main application class for the Active Learning Wizard.

    Coordinates:
    - Camera capture and display
    - ML model inference (pose estimation, fall detection)
    - Feedback generation
    - Mobile client communication via WebSocket
    - Session data export for IRB research
    """

    def __init__(self):
        """Initialize the wizard."""
        # Services
        self.ws_server = WebSocketServer(port=8765)
        self.qr_generator = QRGenerator(ws_port=8765)
        self.session_manager = SessionManager()
        self.data_exporter = SessionDataExporter()

        # ML Models
        self.pose_estimator = PoseEstimator()
        self.sia_detector = SiADetector()
        self.feedback_generator = FeedbackGenerator(use_llm=True)

        # Camera (disconnect callback wired in initialize)
        self.camera = CameraCapture(
            camera_index=0, width=640, height=480, fps=30,
            on_disconnect=self._on_camera_disconnect,
        )

        # State
        self._initialized = False
        self._processing = False
        self._paused = False

        # Component health tracking
        self._component_health: Dict[str, str] = {
            "pose_estimator": "not_initialized",
            "fall_detector": "not_initialized",
            "feedback_generator": "not_initialized",
            "websocket": "not_initialized",
            "camera": "not_initialized",
        }

        # Set up session callbacks
        self.session_manager.set_callbacks(
            on_state_change=self._on_session_state_change,
            on_fall_detected=self._on_fall_detected,
            on_feedback=self._on_feedback_sent
        )

        # Wire periodic status broadcast so mobile timer stays in sync
        self.ws_server.set_status_provider(self._get_mobile_session_status)

        # Post-fall frame collection (protected by _post_fall_lock)
        self._post_fall_lock = threading.Lock()
        self._collecting_post_fall = False
        self._post_fall_frames: List[np.ndarray] = []
        self._post_fall_target = 2  # Collect 2 frames after fall
        self._pre_fall_frames: List[np.ndarray] = []
        self._pending_fall_data: Optional[dict] = None

        # Fall cooldown — ignore new falls for N seconds after recording one
        self._last_fall_recorded_time: float = 0
        self._fall_cooldown_seconds: float = 15.0  # seconds to wait between falls

        # Non-blocking LLM inference
        self._llm_executor = ThreadPoolExecutor(max_workers=1)
        self._pending_llm_future: Optional[Future] = None
        self._llm_pending_fall_data: Optional[dict] = None
        self._llm_submit_time: float = 0  # When the LLM future was submitted
        self._llm_timeout_seconds: float = float(
            os.getenv("SAFEFALL_LLM_TIMEOUT_SECONDS", "240")
        )  # Max time to wait for Ovis before rule-based fallback

        # Shared state for UI updates
        self._latest_pose_info: str = ""
        self._latest_body_landmarks: dict = {
            "frame_width": 0,
            "frame_height": 0,
            "people": [],
        }
        self._latest_feedback: str = ""
        self._latest_feedback_time: float = 0
        self._latest_severity: str = "neutral"
        self._feedback_id: int = 0  # monotonic counter, incremented on each new feedback
        self._frame_lock = threading.Lock()

        # Study ID for IRB
        self._study_id: Optional[str] = None

        # Pending export data (set on stop, cleared after export or discard)
        self._pending_export_stats = None
        self._pending_export_health: Optional[Dict[str, str]] = None

    # ── Initialization ──────────────────────────────────────────

    def initialize(self) -> str:
        """Initialize all components. Returns status message."""
        messages = []

        # Initialize ML models
        if self.pose_estimator.initialize():
            self._component_health["pose_estimator"] = "ready"
            messages.append("Pose estimator ready")
        else:
            self._component_health["pose_estimator"] = "placeholder"
            messages.append("Pose estimator failed (placeholder mode)")

        if self.sia_detector.initialize():
            self._component_health["fall_detector"] = (
                "ready" if self.sia_detector.model is not None else "placeholder"
            )
            messages.append("Fall detector ready")
        else:
            self._component_health["fall_detector"] = "placeholder"
            messages.append("Fall detector failed (placeholder mode)")

        if self.feedback_generator.initialize():
            self._component_health["feedback_generator"] = "ready"
            messages.append("Feedback generator ready")
        else:
            self._component_health["feedback_generator"] = "error"
            messages.append("Feedback generator failed")

        # Start WebSocket server
        if self.ws_server.start():
            self._component_health["websocket"] = "ready"
            messages.append("WebSocket server started on port 8765")
        else:
            self._component_health["websocket"] = "error"
            messages.append(
                f"WebSocket server FAILED: {self.ws_server._start_error or 'unknown'}"
            )

        self._component_health["camera"] = self._get_camera_health()
        self._initialized = True
        return "\n".join(messages)

    # ── Session lifecycle ───────────────────────────────────────

    def start_session(self, study_id: str = "", start_camera: bool = True) -> tuple:
        """
        Start a new active learning session.

        Args:
            study_id: De-identified participant study ID for data export.
            start_camera: Open the local (server-side) camera. Set False when
                frames are supplied externally (e.g. a web browser POSTing to
                /frame), so the engine doesn't try to grab a camera it doesn't
                have.

        Returns:
            Tuple of (QR image, session info, status)
        """
        if not self._initialized:
            self.initialize()

        self._study_id = study_id or "anonymous"

        # Generate QR code
        qr_image, session_data = self.qr_generator.generate()

        # Start session
        session_id = session_data.get('session_id', 'unknown')
        self.session_manager.start_session(session_id)
        self.ws_server.reset_session()

        # Reset SiA buffer and post-fall state for clean session
        self.sia_detector.reset_buffer()
        self._collecting_post_fall = False
        self._post_fall_frames = []
        self._pre_fall_frames = []
        self._pending_fall_data = None
        self._last_fall_recorded_time = 0
        self._cancel_pending_llm()

        # Start data exporter
        self.data_exporter.start_session(
            study_id=self._study_id,
            session_id=session_id,
        )

        # Start camera (skipped when frames come from an external source)
        if start_camera:
            self.camera.start()
        self._component_health["camera"] = self._get_camera_health()
        self._processing = True
        self._paused = False

        info = f"""
                Session Started
                ---------------
                Session ID: {session_id}
                Study ID: {self._study_id}
                WebSocket: {session_data.get('ws_url', 'N/A')}

                Scan the QR code with the SafeFall Coach
                mobile app to connect.
                """
        return qr_image, info, "Session active - waiting for mobile connection"

    def stop_session(self) -> tuple:
        """
        Stop the current session.

        Data collection is frozen; call export_pending_data() or
        discard_pending_data() to finalize.

        Returns:
            Tuple of (summary_text, has_pending_data)
        """
        self._processing = False
        self._paused = False
        self.camera.stop()
        self._component_health["camera"] = self._get_camera_health()
        self._cancel_pending_llm(wait=True)

        # Reset post-fall collection state so stale data doesn't linger
        with self._post_fall_lock:
            self._collecting_post_fall = False
            self._post_fall_frames = []
            self._pre_fall_frames = []
            self._pending_fall_data = None

        stats = self.session_manager.end_session()
        # Note: _on_session_state_change callback already sends status to mobile

        # Freeze data collection without writing files yet
        self.data_exporter.stop_recording()
        self._pending_export_stats = stats
        self._pending_export_health = dict(self._component_health)

        summary = f"""
                    Session Ended
                    -------------
                    Duration: {stats.duration_seconds // 60}m {stats.duration_seconds % 60}s
                    Falls Practiced: {stats.total_falls}
                    Average Score: {stats.average_technique_score:.1f}
                    Best Score: {stats.best_technique_score}
                    Feedback Count: {stats.total_feedback_count}
                    """
        return summary, True

    def export_pending_data(self) -> Dict[str, str]:
        """Write collected session data to disk and clear pending state."""
        if self._pending_export_stats is None:
            return {}
        paths = self.data_exporter.export_session(
            stats=self._pending_export_stats,
            component_health=self._pending_export_health or {},
        )
        self._pending_export_stats = None
        self._pending_export_health = None
        return paths

    def discard_pending_data(self):
        """Discard collected session data without writing files."""
        self.data_exporter.discard()
        self._pending_export_stats = None
        self._pending_export_health = None

    def pause(self):
        """Pause the session. Idempotent — safe to call if already paused."""
        if self._paused:
            return
        self._paused = True
        self.session_manager.pause_session()

    def resume(self):
        """Resume the session. Idempotent — safe to call if already active."""
        if not self._paused:
            return
        self._paused = False
        self.session_manager.resume_session()

    # ── Frame-agnostic processing (no Gradio dependency) ────────

    def process_and_get_frame(self) -> tuple:
        """
        Grab a camera frame and process it through the ML pipeline.

        Framework-agnostic — returns raw data, no gr.update() calls.

        Returns:
            Tuple of (annotated_rgb_frame, pose_info_str, feedback_str)
        """
        if self._paused:
            return self._paused_frame(), "Session paused", ""

        frame = self.camera.get_frame()
        if frame is None:
            return self._no_camera_frame(), "No camera", ""

        return self.process_frame(frame)

    def _get_camera_health(self) -> str:
        """Derive camera health from actual camera state."""
        if not self.camera.is_running:
            return "idle"
        if self.camera.is_disconnected:
            return "disconnected"
        return "ready"

    def get_session_ui_state(self) -> dict:
        """
        Get current session state for UI rendering (framework-agnostic).

        Returns dict with keys: duration_str, fall_count, component_health
        """
        stats = self.session_manager.get_stats()
        elapsed = stats.duration_seconds
        self._component_health["camera"] = self._get_camera_health()
        return {
            "duration_str": f"{elapsed // 60:02d}:{elapsed % 60:02d}",
            "fall_count": stats.total_falls,
            "component_health": dict(self._component_health),
        }

    def process_frame(self, frame: np.ndarray) -> tuple:
        """
        Process a single frame through the ML pipeline with error isolation.

        Each ML stage (pose → fall → feedback) is wrapped independently so
        a failure in one does not crash the video stream.

        Returns:
            Tuple of (annotated_rgb frame, pose_info str, feedback str)
        """
        annotated = frame
        pose_result = None
        angles = {}
        feedback_text = ""

        # ── Stage 1: Pose estimation ──
        try:
            pose_result = self.pose_estimator.estimate(frame)
            annotated = self.pose_estimator.draw_pose(frame, pose_result)
            angles = self.pose_estimator.calculate_angles(pose_result)
        except Exception as e:
            self._component_health["pose_estimator"] = f"error: {e}"

        # ── Stage 2: Fall detection ──
        fall_detected = False
        fall_result = None
        try:
            keypoints = pose_result.keypoints if pose_result else None
            fall_result = self.sia_detector.detect(frame, keypoints)
            fall_detected = fall_result.detected if fall_result else False
        except Exception as e:
            self._component_health["fall_detector"] = f"error: {e}"

        # ── Stage 3: Feedback / LLM ──
        try:
            feedback_text = self._process_feedback(
                frame, fall_detected, fall_result, angles
            )
        except Exception as e:
            self._component_health["feedback_generator"] = f"error: {e}"

        # ── Build pose info string ──
        pose_info = ""
        if pose_result:
            pose_info = f"People detected: {pose_result.num_people}\n"
            if angles:
                pose_info += "Angles:\n"
                for name, angle in angles.items():
                    pose_info += f"  {name}: {angle:.1f}\n"
        pose_info += f"\nConnected clients: {self.ws_server.client_count}"

        # Store for UI stream (only update feedback when non-empty — the WebSocket
        # broadcasts at 10Hz while frames arrive at 30fps, so clearing on every
        # empty frame would cause the desktop app to miss most messages)
        with self._frame_lock:
            self._latest_pose_info = pose_info
            self._latest_body_landmarks = self._serialize_body_landmarks(
                pose_result, frame
            )
            if feedback_text:
                self._latest_feedback = feedback_text
                self._latest_feedback_time = time.time()
                self._feedback_id += 1

        # Convert BGR → RGB for display
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        return annotated_rgb, pose_info, feedback_text

    def _serialize_body_landmarks(self, pose_result, frame: np.ndarray) -> dict:
        """Return lightweight body landmark data for the web overlay."""
        frame_height, frame_width = frame.shape[:2]
        payload = {
            "frame_width": int(frame_width),
            "frame_height": int(frame_height),
            "people": [],
        }
        if pose_result is None or pose_result.num_people == 0:
            return payload

        for person in pose_result.keypoints:
            landmarks = []
            for index, point in enumerate(person):
                if len(point) < 3:
                    continue
                x, y, score = point[:3]
                landmarks.append({
                    "index": int(index),
                    "x": float(x),
                    "y": float(y),
                    "score": float(score),
                })
            payload["people"].append({"landmarks": landmarks})
        return payload

    # ── Feedback / LLM pipeline (private) ───────────────────────

    def _process_feedback(self, frame, fall_detected, fall_result, angles) -> str:
        """Handle fall-frame collection, LLM dispatch, and regular feedback."""
        feedback_text = ""
        current_time = time.time()

        # ── Check pending LLM future ──
        if self._pending_llm_future is not None:
            if self._pending_llm_future.done():
                try:
                    fall_feedback = self._pending_llm_future.result()
                    data = self._llm_pending_fall_data
                    if fall_feedback and data:
                        # Use Ovis's score if available
                        if fall_feedback.pose_score is not None:
                            data['technique_score'] = fall_feedback.pose_score
                        severity = fall_feedback.severity or "error"
                        feedback_text = self._record_fall_feedback(
                            data, fall_feedback.message, severity)
                        with self._frame_lock:
                            self._latest_severity = severity
                except Exception as e:
                    feedback_text = f"FALL DETECTED! (analysis error: {e})"
                    with self._frame_lock:
                        self._latest_severity = "error"
                finally:
                    self._pending_llm_future = None
                    self._llm_pending_fall_data = None
                    self._last_fall_recorded_time = current_time
                    self.sia_detector.reset_buffer()
            elif current_time - self._llm_submit_time > self._llm_timeout_seconds:
                # LLM timed out — cancel and record with rule-based fallback
                elapsed = current_time - self._llm_submit_time
                print(f"[Wizard] LLM timed out after {elapsed:.1f}s, using rule-based fallback")
                self._pending_llm_future.cancel()
                data = self._llm_pending_fall_data
                self._pending_llm_future = None
                self._llm_pending_fall_data = None
                self._last_fall_recorded_time = current_time
                self.sia_detector.reset_buffer()

                if data:
                    # Use rule-based only — don't call LLM again on the main thread
                    saved_use_llm = self.feedback_generator.use_llm
                    self.feedback_generator.use_llm = False
                    fallback = self.feedback_generator.generate_fall_feedback(
                        technique_score=data['technique_score'],
                        pose_angles=data['pose_angles'],
                        frames=None,
                        fall_action=data.get('fall_action'),
                        detected_actions=data.get('detected_actions'),
                    )
                    self.feedback_generator.use_llm = saved_use_llm
                    severity = fallback.severity or "warning"
                    feedback_text = self._record_fall_feedback(
                        data, fallback.message, severity)
                    with self._frame_lock:
                        self._latest_severity = severity
            else:
                # Still running — return empty so we don't spam _feedback_id.
                # The initial "analyzing technique..." message was already
                # recorded once when the LLM was first submitted.
                return ""

        # ── Collect post-fall frames then dispatch LLM ──
        with self._post_fall_lock:
            if self._collecting_post_fall:
                self._post_fall_frames.append(frame.copy())
                if len(self._post_fall_frames) >= self._post_fall_target:
                    normalized_pre_fall = [
                        cv2.resize(f, (640, 480), interpolation=cv2.INTER_LINEAR)
                        for f in self._pre_fall_frames
                    ]
                    all_frames = normalized_pre_fall + self._post_fall_frames
                    self._collecting_post_fall = False

                    data = self._pending_fall_data
                    self._pending_fall_data = None

                    # Submit to thread pool — non-blocking
                    self._llm_pending_fall_data = data
                    self._llm_submit_time = time.time()
                    print(
                        f"[Wizard] Submitting fall analysis to Ovis "
                        f"(timeout={self._llm_timeout_seconds:.0f}s, "
                        f"frames={len(all_frames)})",
                        flush=True,
                    )
                    self._pending_llm_future = self._llm_executor.submit(
                        self.feedback_generator.generate_fall_feedback,
                        technique_score=data['technique_score'],
                        pose_angles=data['pose_angles'],
                        frames=all_frames,
                        fall_action=data.get('fall_action'),
                        detected_actions=data.get('detected_actions'),
                    )
                    feedback_text = "Analyzing technique..."
                    with self._frame_lock:
                        self._latest_severity = "error"

            elif fall_detected and fall_result:
                # Check cooldown — skip if we recently recorded a fall
                time_since_last = current_time - self._last_fall_recorded_time
                if time_since_last < self._fall_cooldown_seconds:
                    # Still in cooldown — ignore this detection
                    pass
                else:
                    # Fall just detected — grab pre-fall frames from SiA buffer
                    self._pre_fall_frames = self.sia_detector.get_key_frames(num_frames=3)
                    self._post_fall_frames = []
                    self._collecting_post_fall = True
                    self._pending_fall_data = {
                        'technique_score': None,
                        'pose_angles': angles,
                        'fall_action': fall_result.action,
                        'detected_actions': fall_result.detected_actions,
                    }
                    feedback_text = "Fall detected: analyzing technique... (please wait)"
                    with self._frame_lock:
                        self._latest_severity = "error"

        return feedback_text

    def _record_fall_feedback(self, data: dict, feedback_msg: str,
                               severity: str) -> str:
        """Record a fall with feedback across all subsystems.

        Returns formatted feedback text for the UI.
        """
        score = data['technique_score']  # May be None if Ovis didn't return a score
        self.session_manager.record_fall(
            technique_score=score or 0,
            feedback=feedback_msg,
            pose_angles=data['pose_angles'],
        )
        stats = self.session_manager.get_stats()
        self.ws_server.send_fall_event(
            score or 0, feedback_msg,
            total_falls=stats.total_falls,
            duration_seconds=stats.duration_seconds,
        )
        self.data_exporter.record_feedback(
            feedback_msg, "fall", score or 0
        )
        self.session_manager.record_feedback(
            feedback_msg, severity, score or 0
        )
        self.ws_server.send_feedback(
            feedback_msg, severity=severity,
            pose_score=score or 0,
        )
        return feedback_msg

    def _cancel_pending_llm(self, wait: bool = False):
        """Cancel any pending LLM future.

        Args:
            wait: If True, block until the future completes (up to 10s).
                  Used during stop_session to prevent post-stop data corruption.
        """
        if self._pending_llm_future is not None:
            if not self._pending_llm_future.done():
                self._pending_llm_future.cancel()
                if wait:
                    try:
                        self._pending_llm_future.result(timeout=10)
                    except Exception:
                        pass  # Cancelled or timed out — either way, it's done
            self._pending_llm_future = None
        self._llm_pending_fall_data = None

    # ── Placeholder frames ──────────────────────────────────────

    @staticmethod
    def _no_camera_frame() -> np.ndarray:
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, "No camera feed", (200, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        return cv2.cvtColor(placeholder, cv2.COLOR_BGR2RGB)

    @staticmethod
    def _paused_frame() -> np.ndarray:
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, "PAUSED", (230, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        cv2.putText(placeholder, "Press Resume to continue", (140, 290),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2)
        return cv2.cvtColor(placeholder, cv2.COLOR_BGR2RGB)

    # ── Camera disconnect callback ──────────────────────────────

    def _on_camera_disconnect(self):
        """Called by CameraCapture when camera disconnects."""
        self._component_health["camera"] = self._get_camera_health()
        print("[Wizard] Camera disconnected")
        # Auto-pause session so timer doesn't keep running with frozen video
        if self.session_manager.is_active and not self._paused:
            print("[Wizard] Auto-pausing session due to camera disconnect")
            self.pause()

    # ── Session callbacks ───────────────────────────────────────

    def _get_mobile_session_status(self):
        """Return current SessionStatusMessage for periodic mobile broadcast."""
        from services.websocket_server import SessionStatusMessage
        state = self.session_manager.state
        if state not in (SessionState.ACTIVE, SessionState.PAUSED):
            return None
        status_map = {
            SessionState.ACTIVE: "active",
            SessionState.PAUSED: "paused",
        }
        stats = self.session_manager.get_stats()
        return SessionStatusMessage(
            status=status_map[state],
            duration_seconds=stats.duration_seconds,
            falls_practiced=stats.total_falls,
        )

    def _on_session_state_change(self, new_state: SessionState):
        status_map = {
            SessionState.ACTIVE: "active",
            SessionState.PAUSED: "paused",
            SessionState.ENDED: "ended",
        }
        status = status_map.get(new_state, "unknown")
        stats = self.session_manager.get_stats()
        self.ws_server.send_session_status(
            status,
            total_falls=stats.total_falls,
            duration_seconds=stats.duration_seconds,
        )

    def _on_fall_detected(self, record):
        pass  # Handled in process_frame

    def _on_feedback_sent(self, message: str, severity: str, score: int):
        pass  # Handled in process_frame

    # ── Camera management ───────────────────────────────────────

    def set_camera(self, camera_index: int):
        """Switch to a different camera device."""
        was_running = self.camera.is_running
        if was_running:
            self.camera.stop()
        self.camera = CameraCapture(
            camera_index=camera_index, width=640, height=480, fps=30,
            on_disconnect=self._on_camera_disconnect,
        )
        if was_running:
            self.camera.start()
            self._component_health["camera"] = self._get_camera_health()

    def get_camera_frame(self) -> Optional[np.ndarray]:
        """Get current camera frame with ML processing applied."""
        if not self._processing:
            return None
        frame = self.camera.get_frame()
        if frame is None:
            return None
        annotated, _, _ = self.process_frame(frame)
        return annotated

    # ── Cleanup ─────────────────────────────────────────────────

    def cleanup(self):
        """Clean up resources."""
        self._processing = False
        self._cancel_pending_llm()
        self._llm_executor.shutdown(wait=True, cancel_futures=True)
        self.camera.stop()
        self.ws_server.stop()
