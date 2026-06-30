"""
LLM Provider base classes — shared interface for all LLM backends.

Provides:
  - LLMFeedbackResult: dataclass for feedback results
  - LLMProvider: abstract base class for providers (Ovis, Gemini, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass
class LLMFeedbackResult:
    """Result from LLM feedback generation."""
    message: str
    severity: str  # 'info', 'warning', 'success'
    pose_score: int
    suggestion: Optional[str] = None  # Specific coaching suggestion from LLM


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the provider. Returns True if successful."""
        pass

    @abstractmethod
    def generate_feedback(
        self,
        pose_angles: Dict[str, float],
        technique_score: int,
        fall_detected: bool = False,
        frames: Optional[List[np.ndarray]] = None,
        fall_action: Optional[str] = None,
        detected_actions: Optional[List] = None,
    ) -> Optional[LLMFeedbackResult]:
        """Generate coaching feedback from pose data.

        Args:
            pose_angles: Body segment angles
            technique_score: Technique score (0-100)
            fall_detected: Whether a fall was detected
            frames: Camera frames for multimodal analysis
            fall_action: The detected fall action (e.g. 'fall down', 'lie/sleep')
            detected_actions: All (action, confidence) pairs detected on the person
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass

    def generate_raw(
        self,
        prompt: str,
        frames: Optional[List[np.ndarray]] = None,
        max_new_tokens: int = 500,
    ) -> Optional[str]:
        """Generate raw text from a custom prompt. Override in subclasses."""
        return None

    @property
    def needs_rate_limiting(self) -> bool:
        """Whether this provider needs rate limiting (for free tier APIs)."""
        return False  # Default: no rate limiting

    @property
    def rate_limit_config(self) -> dict:
        """Rate limiting configuration."""
        return {
            'max_calls_per_minute': 60,  # Default unlimited
            'backoff_duration': 60.0,     # Seconds to wait after error
            'only_for_falls': False       # Apply LLM only to fall events
        }
