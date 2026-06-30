"""
Feedback Generator using Multimodal LLM

This module generates coaching feedback based on pose analysis and fall detection.
Uses Ovis2.5-2B for local GPU inference (requires NVIDIA GPU with CUDA).
"""

import os
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import numpy as np

from .llm_provider import LLMProvider, OvisProvider, LLMFeedbackResult


def _select_llm_provider() -> LLMProvider:
    """Select Ovis2.5-2B as the LLM provider. Requires CUDA GPU."""
    print("[Feedback] Using Ovis2.5-2B (local GPU)")
    return OvisProvider()


@dataclass
class CoachingFeedback:
    """Coaching feedback message."""
    message: str
    severity: str  # 'info', 'warning', 'success'
    pose_score: int
    timestamp: float
    category: Optional[str] = None  # e.g., 'fall_technique', 'posture'
    suggestion: Optional[str] = None  # Additional coaching suggestion


class FeedbackGenerator:
    """
    Generates coaching feedback for fall technique practice.

    This class can operate in two modes:
    1. Rule-based: Uses predefined rules based on pose angles
    2. LLM-based: Uses a multimodal LLM for more nuanced feedback
    """

    def __init__(self, use_llm: bool = False):
        """
        Initialize the feedback generator.

        Args:
            use_llm: Whether to use LLM for feedback generation
        """
        self.use_llm = use_llm
        self._is_initialized = False

        # Auto-select provider based on hardware (override with LLM_PROVIDER env var)
        self._llm_provider: LLMProvider = _select_llm_provider()

        # Get rate limiting config from provider
        self._rate_limit_config = self._llm_provider.rate_limit_config

        # Coaching rules for different scenarios
        self._coaching_rules = {
            'chin_not_tucked': {
                'message': "Remember to tuck your chin to protect your head!",
                'severity': 'warning'
            },
            'arms_extended': {
                'message': "Try not to extend your arms to catch yourself - this can cause wrist injuries.",
                'severity': 'warning'
            },
            'good_form': {
                'message': "Good form! Keep practicing.",
                'severity': 'success'
            },
            'knees_bent': {
                'message': "Good job keeping your knees bent!",
                'severity': 'success'
            },
            'torso_tilted': {
                'message': "Try to keep your torso more aligned for better control.",
                'severity': 'info'
            },
            'preparing': {
                'message': "Get ready in your starting position.",
                'severity': 'info'
            },
            'no_person': {
                'message': "Step into the camera view to begin.",
                'severity': 'info'
            }
        }

        # Track last feedback to avoid repetition
        self._last_feedback_key: Optional[str] = None
        self._last_feedback_time: float = 0
        self._feedback_cooldown: float = 5.0  # seconds (increased for quota conservation)

        # Rate limiting state (only active if provider needs it)
        self._llm_call_count: int = 0
        self._llm_call_window_start: float = 0
        self._llm_last_error_time: float = 0

    def initialize(self) -> bool:
        """
        Initialize the feedback generator.

        Returns:
            True if successful, False otherwise.
        """
        if self.use_llm:
            if self._llm_provider.initialize():
                print(f"[Feedback] LLM mode active: {self._llm_provider.name}")
                if self._llm_provider.needs_rate_limiting:
                    cfg = self._rate_limit_config
                    mode = "fall events only" if cfg['only_for_falls'] else "all feedback"
                    print(f"[Feedback] Rate limiting: {cfg['max_calls_per_minute']} calls/min, {mode}")
                else:
                    print(f"[Feedback] Rate limiting: DISABLED (local model)")
            else:
                print(f"[Feedback] {self._llm_provider.name} failed to init. Falling back to rule-based.")
                self.use_llm = False

        self._is_initialized = True
        mode = self._llm_provider.name if self.use_llm else "rule-based"
        print(f"[Feedback] Feedback generator initialized ({mode} mode)")
        return True

    def generate(self,
                 pose_angles: Dict[str, float],
                 fall_detected: bool = False,
                 technique_score: Optional[int] = None,
                 frame: Optional[np.ndarray] = None) -> Optional[CoachingFeedback]:
        """
        Generate coaching feedback based on current pose and state.

        Args:
            pose_angles: Dictionary of body segment angles
            fall_detected: Whether a fall was just detected
            technique_score: Score for the fall technique (if fall detected)
            frame: Current camera frame (for LLM mode)

        Returns:
            CoachingFeedback if there's something to say, None otherwise
        """
        if not self._is_initialized:
            raise RuntimeError("Feedback generator not initialized.")

        current_time = time.time()

        # Check cooldown
        if current_time - self._last_feedback_time < self._feedback_cooldown:
            return None

        feedback_key, pose_score = self._analyze_pose(pose_angles, fall_detected)

        # Override score if technique score provided
        if technique_score is not None:
            pose_score = technique_score

        # Don't repeat the same feedback
        if feedback_key == self._last_feedback_key:
            return None

        # Try LLM first if enabled and allowed
        use_llm_for_this = self.use_llm and feedback_key != 'no_person'

        # Check provider's rate limit config
        if use_llm_for_this and self._rate_limit_config['only_for_falls'] and not fall_detected:
            use_llm_for_this = False  # Skip LLM for non-fall feedback if configured

        if use_llm_for_this and self._can_call_llm():
            llm_result = self._try_llm_with_backoff(
                pose_angles = pose_angles,
                technique_score = pose_score,
                fall_detected = fall_detected,
                frames = [frame] if frame is not None else None, # Pass single frame
            )
            if llm_result is not None:
                self._last_feedback_key = feedback_key
                self._last_feedback_time = current_time
                return CoachingFeedback(
                    message=llm_result.message,
                    severity=llm_result.severity,
                    pose_score=llm_result.pose_score,
                    timestamp=current_time,
                )

        # Fallback to rule-based
        rule = self._coaching_rules.get(feedback_key)
        if rule is None:
            return None

        # Update tracking
        self._last_feedback_key = feedback_key
        self._last_feedback_time = current_time

        return CoachingFeedback(
            message=rule['message'],
            severity=rule['severity'],
            pose_score=pose_score,
            timestamp=current_time
        )

    def generate_fall_feedback(self,
                               technique_score: int,
                               pose_angles: Dict[str, float],
                               frames: Optional[List[np.ndarray]] = None,
                               fall_action: Optional[str] = None,
                               detected_actions: Optional[List] = None) -> CoachingFeedback:
        """
        Generate specific feedback after a fall is detected.

        Args:
            technique_score: Overall technique score (0-100)
            pose_angles: Body segment angles during the fall
            frames: Camera frames (pre-fall + post-fall) for LLM analysis
            fall_action: The detected fall action (e.g. 'fall down', 'lie/sleep')
            detected_actions: All (action, score) pairs detected on the person

        Returns:
            CoachingFeedback with detailed analysis
        """
        current_time = time.time()
        technique_score = technique_score or 0

        can_call_llm = self._can_call_llm()

        # Try LLM first if enabled (fall events always eligible)
        if self.use_llm and can_call_llm:
            print(
                f"[Feedback] Requesting detailed fall feedback from {self._llm_provider.name} "
                f"(frames={len(frames) if frames else 0}, action={fall_action})",
                flush=True,
            )
            llm_result = self._try_llm_with_backoff(
                pose_angles = pose_angles,
                technique_score = technique_score,
                fall_detected = True,
                frames = frames,
                fall_action = fall_action,
                detected_actions = detected_actions,
            )

            # NEW: Unload Ovis to free VRAM (only in lazy mode, not in persistent mode)
            if hasattr(self._llm_provider, 'unload_model'):
                self._llm_provider.unload_model()
            
            if llm_result:
                score = llm_result.pose_score if llm_result.pose_score is not None else technique_score
                return CoachingFeedback(
                    message = llm_result.message,
                    severity = llm_result.severity,
                    pose_score = score,
                    category = "fall_technique",
                    suggestion = self._get_fall_suggestion(score, pose_angles),
                    timestamp = current_time,
                )
            print(
                "[Feedback] LLM returned no result; using detailed rule-based fallback.",
                flush=True,
            )
        else:
            reason = "LLM disabled during initialization" if not self.use_llm else "LLM call blocked by rate/backoff"
            print(f"[Feedback] {reason}; using detailed rule-based fallback.", flush=True)

        # Fallback to rule-based analysis
        positives = []
        improvements = []

        # Check elbow angles (arms should be bent, not extended)
        left_elbow = pose_angles.get('left_elbow', 180)
        right_elbow = pose_angles.get('right_elbow', 180)

        if left_elbow < 150 and right_elbow < 150:
            positives.append("arms bent correctly")
        elif left_elbow > 160 or right_elbow > 160:
            improvements.append(
                "Keep both arms bent instead of reaching out with straight hands. "
                "Straight arms can put a lot of force through the wrists, elbows, and shoulders during impact."
            )

        # Check knee angles (knees should be bent)
        left_knee = pose_angles.get('left_knee', 180)
        right_knee = pose_angles.get('right_knee', 180)

        if left_knee < 160 and right_knee < 160:
            positives.append("good knee bend")
        else:
            improvements.append(
                "Bend your knees more before and during the descent. "
                "More knee bend lowers your center of gravity and gives you more control before contact with the mat."
            )

        # Check torso tilt
        torso_tilt = pose_angles.get('torso_tilt', 0)
        if torso_tilt < 15:
            positives.append("good body alignment")
        else:
            improvements.append(
                "Control your center of gravity by keeping your torso organized and moving as one unit. "
                "This helps avoid twisting or landing flat on one hard point."
            )

        # Build supportive user-facing fallback message. Keep Ovis diagnostics in logs only.
        score = technique_score or 0
        if score >= 80:
            prefix = "Excellent effort - that was a strong practice fall."
        elif score >= 60:
            prefix = "Good attempt - you are building the right habits."
        else:
            prefix = "Keep practicing - this is exactly the kind of rep that helps you improve."

        action_text = f" Detected action: {fall_action}." if fall_action else ""
        likely_causes = []
        if left_elbow > 160 or right_elbow > 160:
            likely_causes.append(
                "reaching with straighter arms may have pulled your weight forward and made the landing harder to control"
            )
        if left_knee >= 160 or right_knee >= 160:
            likely_causes.append(
                "not bending the knees enough likely kept your center of gravity higher than ideal"
            )
        if torso_tilt >= 15:
            likely_causes.append(
                "torso tilt may have shifted your center of gravity away from a smooth, controlled descent"
            )
        cause_text = (
            "What might have caused the fall: " + "; ".join(likely_causes) + "."
            if likely_causes
            else "What might have caused the fall: The movement looked mostly controlled, so the main focus is repeating the same pattern slowly and consistently."
        )

        parts = [f"Summary: {prefix}{action_text}", cause_text]

        if positives:
            parts.append(
                "What you did well: " +
                " ".join(f"{item.capitalize()}." for item in positives)
            )
        else:
            parts.append(
                "What you did well: You completed a practice fall and stayed in the camera view long enough for the coach to evaluate the movement."
            )

        if improvements:
            parts.append("What to improve: " + " ".join(improvements))
        else:
            parts.append(
                "What to improve: Keep repeating the same controlled movement slowly, with attention to chin tuck, bent arms, bent knees, and a soft landing path."
            )

        message = " ".join(parts)

        # Determine severity
        if score >= 80:
            severity = 'success'
        elif score >= 60:
            severity = 'info'
        else:
            severity = 'warning'

        return CoachingFeedback(
            message=message,
            severity=severity,
            pose_score=technique_score,
            timestamp=current_time
        )

    def _analyze_pose(self, pose_angles: Dict[str, float], fall_detected: bool) -> tuple:
        """
        Analyze pose and determine appropriate feedback.

        Args:
            pose_angles: Dictionary of body segment angles
            fall_detected: Whether a fall was detected

        Returns:
            Tuple of (feedback_key, pose_score)
        """
        if not pose_angles:
            return ('no_person', 0)

        # Calculate a basic pose score
        score = 70  # Base score

        # Check various aspects
        issues = []
        positives = []

        # Torso alignment
        torso_tilt = pose_angles.get('torso_tilt', 0)
        if torso_tilt > 20:
            issues.append('torso_tilted')
            score -= 10
        else:
            score += 5

        # Knee bend (good for preparing to fall)
        left_knee = pose_angles.get('left_knee', 180)
        right_knee = pose_angles.get('right_knee', 180)
        avg_knee = (left_knee + right_knee) / 2

        if avg_knee < 160:
            positives.append('knees_bent')
            score += 10

        # Elbow position
        left_elbow = pose_angles.get('left_elbow', 180)
        right_elbow = pose_angles.get('right_elbow', 180)

        if left_elbow > 170 and right_elbow > 170:
            issues.append('arms_extended')
            score -= 15

        # Clamp score
        score = max(0, min(100, score))

        # Determine feedback
        if issues:
            return (issues[0], score)
        elif positives:
            return (positives[0], score)
        elif score >= 75:
            return ('good_form', score)
        else:
            return ('preparing', score)

    def _can_call_llm(self) -> bool:
        """
        Check if we can make an LLM call based on provider's rate limits.

        Returns:
            True if call is allowed, False if rate limited
        """
        # Skip all checks if provider doesn't need rate limiting
        if not self._llm_provider.needs_rate_limiting:
            return True

        current_time = time.time()
        cfg = self._rate_limit_config

        # Check backoff period after error
        if current_time - self._llm_last_error_time < cfg['backoff_duration']:
            return False

        # Reset window if minute has passed
        if current_time - self._llm_call_window_start > 60.0:
            self._llm_call_count = 0
            self._llm_call_window_start = current_time

        # Check rate limit
        return self._llm_call_count < cfg['max_calls_per_minute']

    def _try_llm_with_backoff(self, pose_angles, technique_score,
                              fall_detected, frames = None,
                              fall_action = None,
                              detected_actions = None) -> Optional[LLMFeedbackResult]:
        """
        Try to call LLM with error handling and backoff.

        Args:
            pose_angles: Body segment angles
            technique_score: Technique score
            fall_detected: Whether fall detected
            frames: Camera frames for multimodal analysis
            fall_action: The detected fall action type
            detected_actions: All (action, score) pairs for the person

        Returns:
            LLMFeedbackResult or None if failed
        """
        try:
            result = self._llm_provider.generate_feedback(
                pose_angles = pose_angles,
                technique_score = technique_score,
                fall_detected = fall_detected,
                frames = frames,
                fall_action = fall_action,
                detected_actions = detected_actions,
            )

            if result is not None:
                self._llm_call_count += 1
                return result

        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                # Rate limit hit - enter backoff period
                self._llm_last_error_time = time.time()
                backoff = self._rate_limit_config['backoff_duration']
                print(f"[Feedback] Rate limit hit. Backing off for {backoff}s")
            else:
                print(f"[Feedback] LLM error: {error_str}")

        return None

    def _get_fall_suggestion(self, technique_score: int, pose_angles: Dict[str, float]) -> Optional[str]:
        """
        Generate a specific suggestion based on technique score and pose angles.

        Args:
            technique_score: Overall technique score (0-100)
            pose_angles: Body segment angles

        Returns:
            Suggestion string or None
        """
        if technique_score >= 80:
            return None  # No suggestion needed for excellent technique

        # Provide targeted suggestions based on common issues
        suggestions = []

        # Check arm positioning
        left_elbow = pose_angles.get('left_elbow', 180)
        right_elbow = pose_angles.get('right_elbow', 180)
        if left_elbow > 160 or right_elbow > 160:
            suggestions.append("Keep your arms bent, not extended")

        # Check knee bend
        left_knee = pose_angles.get('left_knee', 180)
        right_knee = pose_angles.get('right_knee', 180)
        if left_knee > 160 or right_knee > 160:
            suggestions.append("Bend your knees more")

        # Check torso alignment
        torso_tilt = pose_angles.get('torso_tilt', 0)
        if torso_tilt > 20:
            suggestions.append("Keep your body more aligned")

        return suggestions[0] if suggestions else "Practice the movement slowly"

    def reset_cooldown(self):
        """Reset the feedback cooldown to allow immediate feedback."""
        self._last_feedback_time = 0
        self._last_feedback_key = None

    def get_quota_status(self) -> dict:
        """Get current quota usage stats."""
        if not self._llm_provider.needs_rate_limiting:
            return {'rate_limiting': 'disabled', 'provider': self._llm_provider.name}

        current_time = time.time()
        cfg = self._rate_limit_config
        window_remaining = 60.0 - (current_time - self._llm_call_window_start)

        return {
            'provider': self._llm_provider.name,
            'calls_this_minute': self._llm_call_count,
            'max_calls_per_minute': cfg['max_calls_per_minute'],
            'calls_remaining': max(0, cfg['max_calls_per_minute'] - self._llm_call_count),
            'window_reset_in': max(0, window_remaining),
            'in_backoff': (current_time - self._llm_last_error_time) < cfg['backoff_duration'],
            'backoff_remaining': max(0, cfg['backoff_duration'] - (current_time - self._llm_last_error_time)),
            'only_for_falls': cfg['only_for_falls']
        }

    @property
    def is_initialized(self) -> bool:
        """Check if the generator is initialized."""
        return self._is_initialized
