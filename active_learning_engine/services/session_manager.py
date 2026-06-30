"""
Session Manager for Active Learning Sessions

This module manages the state of active learning sessions,
coordinating between the camera, ML models, and WebSocket server.
"""

import time
from time import monotonic as _monotonic
import threading
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class SessionState(Enum):
    """Possible states for a session."""
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDING = "ending"
    ENDED = "ended"


@dataclass
class FallRecord:
    """Record of a detected fall."""
    timestamp: float
    technique_score: int
    feedback: str
    pose_angles: Dict[str, float] = field(default_factory=dict)


@dataclass
class SessionStats:
    """Statistics for a session."""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_seconds: int = 0
    total_falls: int = 0
    average_technique_score: float = 0.0
    best_technique_score: int = 0
    total_feedback_count: int = 0
    fall_records: List[FallRecord] = field(default_factory=list)


class SessionManager:
    """
    Manages the lifecycle and state of active learning sessions.

    Coordinates:
    - Session state transitions
    - Fall detection and recording
    - Feedback generation and delivery
    - Statistics tracking
    """

    def __init__(self):
        """Initialize the session manager."""
        self._state = SessionState.IDLE
        self._session_id: Optional[str] = None
        self._stats = SessionStats()
        self._lock = threading.Lock()

        # Active-time accumulator (excludes paused intervals)
        self._accumulated_seconds: float = 0.0
        self._last_resume_time: float = 0.0

        # Callbacks
        self._on_state_change: Optional[Callable[[SessionState], None]] = None
        self._on_fall_detected: Optional[Callable[[FallRecord], None]] = None
        self._on_feedback: Optional[Callable[[str, str, int], None]] = None

    def start_session(self, session_id: str) -> bool:
        """
        Start a new session.

        Args:
            session_id: Unique identifier for this session

        Returns:
            True if session started successfully
        """
        with self._lock:
            if self._state not in [SessionState.IDLE, SessionState.ENDED]:
                return False

            self._session_id = session_id
            now = _monotonic()
            self._stats = SessionStats(start_time=time.time())  # wall-clock for export
            self._accumulated_seconds = 0.0
            self._last_resume_time = now
            self._state = SessionState.ACTIVE

        self._notify_state_change(SessionState.ACTIVE)
        return True

    def pause_session(self):
        """Pause the current session."""
        changed = False
        with self._lock:
            if self._state == SessionState.ACTIVE:
                self._accumulated_seconds += _monotonic() - self._last_resume_time
                self._last_resume_time = 0.0
                self._update_duration()
                self._state = SessionState.PAUSED
                changed = True
        if changed:
            self._notify_state_change(SessionState.PAUSED)

    def resume_session(self):
        """Resume a paused session."""
        changed = False
        with self._lock:
            if self._state == SessionState.PAUSED:
                self._last_resume_time = _monotonic()
                self._state = SessionState.ACTIVE
                changed = True
        if changed:
            self._notify_state_change(SessionState.ACTIVE)

    def end_session(self) -> SessionStats:
        """
        End the current session.

        Returns:
            Final session statistics
        """
        with self._lock:
            self._stats.end_time = time.time()  # wall-clock for export

            # Bank any remaining active time (if ending while active, not paused)
            if self._last_resume_time > 0:
                self._accumulated_seconds += _monotonic() - self._last_resume_time
                self._last_resume_time = 0.0
            self._update_duration()

            self._state = SessionState.ENDED

            # Calculate final stats
            if self._stats.fall_records:
                scores = [f.technique_score for f in self._stats.fall_records]
                self._stats.average_technique_score = sum(scores) / len(scores)
                self._stats.best_technique_score = max(scores)

            stats = self._stats

        self._notify_state_change(SessionState.ENDED)
        return stats

    def record_fall(self,
                   technique_score: int,
                   feedback: str,
                   pose_angles: Optional[Dict[str, float]] = None) -> FallRecord:
        """
        Record a detected fall.

        Args:
            technique_score: Score for the fall technique (0-100)
            feedback: Feedback message about the fall
            pose_angles: Body angles at time of fall

        Returns:
            The created FallRecord
        """
        record = FallRecord(
            timestamp=time.time(),
            technique_score=technique_score,
            feedback=feedback,
            pose_angles=pose_angles or {}
        )

        with self._lock:
            self._stats.fall_records.append(record)
            self._stats.total_falls += 1

        # Notify callback
        if self._on_fall_detected:
            self._on_fall_detected(record)

        return record

    def record_feedback(self, message: str, severity: str, pose_score: int):
        """
        Record that feedback was sent.

        Args:
            message: The feedback message
            severity: Message severity
            pose_score: Current pose score
        """
        with self._lock:
            self._stats.total_feedback_count += 1

        # Notify callback
        if self._on_feedback:
            self._on_feedback(message, severity, pose_score)

    def _update_duration(self):
        """Recompute duration_seconds from the accumulator. Must hold _lock."""
        active = self._accumulated_seconds
        if self._last_resume_time > 0:
            active += _monotonic() - self._last_resume_time
        self._stats.duration_seconds = max(0, int(active))

    def _notify_state_change(self, new_state: SessionState):
        """Fire state-change callback outside the lock to avoid deadlocks."""
        if self._on_state_change:
            self._on_state_change(new_state)

    def set_callbacks(self,
                     on_state_change: Optional[Callable[[SessionState], None]] = None,
                     on_fall_detected: Optional[Callable[[FallRecord], None]] = None,
                     on_feedback: Optional[Callable[[str, str, int], None]] = None):
        """
        Set callback functions for session events.

        Args:
            on_state_change: Called when session state changes
            on_fall_detected: Called when a fall is recorded
            on_feedback: Called when feedback is sent
        """
        self._on_state_change = on_state_change
        self._on_fall_detected = on_fall_detected
        self._on_feedback = on_feedback

    @property
    def state(self) -> SessionState:
        """Get current session state."""
        return self._state

    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._session_id

    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self._state == SessionState.ACTIVE

    @property
    def stats(self) -> SessionStats:
        """Get current session statistics (updates live duration)."""
        with self._lock:
            self._update_duration()
        return self._stats

    def get_stats(self) -> SessionStats:
        """
        Get current session statistics (convenience method).

        Returns:
            Current SessionStats object with live duration
        """
        with self._lock:
            self._update_duration()
        return self._stats

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current/last session.

        Returns:
            Dictionary with session summary data
        """
        return {
            "session_id": self._session_id,
            "state": self._state.value,
            "duration_seconds": self._stats.duration_seconds,
            "total_falls": self._stats.total_falls,
            "average_score": round(self._stats.average_technique_score, 1),
            "best_score": self._stats.best_technique_score,
            "feedback_count": self._stats.total_feedback_count
        }
