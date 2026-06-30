"""
Video Recorder Interface (Stub)

ABC for future session video recording. Implementation deferred until
sponsor approval for video capture during IRB testing.
"""

from abc import ABC, abstractmethod
import numpy as np


class VideoRecorderInterface(ABC):
    """Abstract base class for session video recording."""

    @abstractmethod
    def start(self, session_id: str, width: int, height: int, fps: float):
        """Begin recording a new session."""
        ...

    @abstractmethod
    def write_frame(self, frame: np.ndarray):
        """Write a single BGR frame."""
        ...

    @abstractmethod
    def stop(self) -> str:
        """Stop recording and return the output file path."""
        ...


class NoOpVideoRecorder(VideoRecorderInterface):
    """No-op recorder that silently discards frames."""

    def start(self, session_id: str, width: int = 640, height: int = 480,
              fps: float = 30.0):
        pass

    def write_frame(self, frame: np.ndarray):
        pass

    def stop(self) -> str:
        return ""
