"""
RTMLib Pose Estimation Wrapper

This module provides real-time pose estimation using RTMLib.
"""

import numpy as np
from typing import Optional, Tuple, List
from dataclasses import dataclass

POSE_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class PoseResult:
    """Result from pose estimation."""
    keypoints: np.ndarray  # Shape: (num_people, num_keypoints, 3) - x, y, confidence
    scores: np.ndarray  # Per-person confidence scores
    num_people: int


# RTMLib keypoint indices (COCO format)
class Keypoints:
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16


class PoseEstimator:
    """
    Real-time pose estimation using RTMLib.

    RTMLib provides efficient pose estimation models that can run
    in real-time on consumer hardware.
    """

    def __init__(self,
                 model_name: str = None,
                 device: str = "cpu"):
        """
        Initialize the pose estimator.

        Args:
            model_name: RTMLib model name (None for default, or model string)
            device: Device to run on ('cpu' or 'cuda')
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self._is_initialized = False

    def initialize(self) -> bool:
        """
        Initialize the RTMLib model.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Try to import and initialize RTMLib
            from rtmlib import Body

            self.model = Body(
                pose=self.model_name,
                to_openpose=False,
                device=self.device
            )
            self._is_initialized = True
            model_desc = self.model_name if self.model_name else "default"
            print(f"\n[RTMLib] Pose estimator initialized: {model_desc}")
            return True
        except ImportError:
            print("[RTMLib] rtmlib not installed. Running in placeholder mode.")
            self._is_initialized = True  # Allow placeholder operation
            return True
        except Exception as e:
            print(f"[RTMLib] Failed to initialize: {e}")
            return False

    def estimate(self, frame: np.ndarray) -> PoseResult:
        """
        Estimate poses in the given frame.

        Args:
            frame: BGR image frame from camera

        Returns:
            PoseResult with keypoints and confidence scores
        """
        if not self._is_initialized:
            raise RuntimeError("Pose estimator not initialized. Call initialize() first.")

        if self.model is not None:
            try:
                # RTMLib returns (keypoints, scores) tuple
                result = self.model(frame)

                # Handle the output format
                if isinstance(result, tuple):
                    keypoints, scores_per_kp = result
                else:
                    keypoints = result
                    scores_per_kp = None

                if keypoints is None or len(keypoints) == 0:
                    return PoseResult(
                        keypoints=np.array([]),
                        scores=np.array([]),
                        num_people=0
                    )

                # Ensure proper shape
                if keypoints.ndim == 2:
                    keypoints = keypoints[np.newaxis, ...]
                    if scores_per_kp is not None and scores_per_kp.ndim == 1:
                        scores_per_kp = scores_per_kp[np.newaxis, ...]

                # Combine keypoints (x, y) with scores to get (x, y, confidence)
                if scores_per_kp is not None:
                    # keypoints shape: (num_people, num_keypoints, 2)
                    # scores_per_kp shape: (num_people, num_keypoints)
                    # Combine to: (num_people, num_keypoints, 3)
                    keypoints_with_conf = np.concatenate([
                        keypoints,
                        scores_per_kp[..., np.newaxis]
                    ], axis=-1)
                else:
                    # If no scores, assume confidence of 1.0
                    conf = np.ones((*keypoints.shape[:-1], 1))
                    keypoints_with_conf = np.concatenate([keypoints, conf], axis=-1)

                # Calculate per-person scores (average confidence)
                scores = np.mean(keypoints_with_conf[..., 2], axis=1)

                return PoseResult(
                    keypoints=keypoints_with_conf,
                    scores=scores,
                    num_people=len(keypoints_with_conf)
                )
            except Exception as e:
                print(f"[RTMLib] Estimation error: {e}")
                import traceback
                traceback.print_exc()

        # Placeholder: Return empty result
        return PoseResult(
            keypoints=np.array([]),
            scores=np.array([]),
            num_people=0
        )

    def draw_pose(self, frame: np.ndarray, pose_result: PoseResult,
                  thickness: int = 2, circle_radius: int = 4) -> np.ndarray:
        """
        Draw pose keypoints and skeleton on the frame using RTMLib's draw_skeleton.

        Args:
            frame: BGR image frame
            pose_result: Result from estimate()
            thickness: Line thickness for skeleton
            circle_radius: Radius for keypoint circles

        Returns:
            Frame with pose overlay drawn
        """
        if pose_result.num_people == 0:
            return frame.copy()

        from rtmlib import draw_skeleton

        output = frame.copy()
        # PoseResult.keypoints is (N, K, 3) — split into (N, K, 2) xy and (N, K, 1) scores
        kps_xy = pose_result.keypoints[..., :2]
        kps_scores = pose_result.keypoints[..., 2:3]

        return draw_skeleton(output, kps_xy, kps_scores,
                             kpt_thr=POSE_CONFIDENCE_THRESHOLD, radius=circle_radius,
                             line_width=thickness)

    def calculate_angles(self, pose_result: PoseResult) -> dict:
        """
        Calculate body segment angles for technique analysis.

        Args:
            pose_result: Result from estimate()

        Returns:
            Dictionary of angle measurements
        """
        if pose_result.num_people == 0:
            return {}

        # Use first detected person
        keypoints = pose_result.keypoints[0]

        angles = {}

        # Helper function to calculate angle between three points
        def angle_between_points(p1, p2, p3):
            """Calculate angle at p2 formed by p1-p2-p3."""
            v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
            v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])

            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            angle = np.arccos(np.clip(cos_angle, -1, 1))
            return np.degrees(angle)

        try:
            # Left elbow angle
            if all(keypoints[i][2] >= POSE_CONFIDENCE_THRESHOLD for i in [Keypoints.LEFT_SHOULDER, Keypoints.LEFT_ELBOW, Keypoints.LEFT_WRIST]):
                angles['left_elbow'] = angle_between_points(
                    keypoints[Keypoints.LEFT_SHOULDER],
                    keypoints[Keypoints.LEFT_ELBOW],
                    keypoints[Keypoints.LEFT_WRIST]
                )

            # Right elbow angle
            if all(keypoints[i][2] >= POSE_CONFIDENCE_THRESHOLD for i in [Keypoints.RIGHT_SHOULDER, Keypoints.RIGHT_ELBOW, Keypoints.RIGHT_WRIST]):
                angles['right_elbow'] = angle_between_points(
                    keypoints[Keypoints.RIGHT_SHOULDER],
                    keypoints[Keypoints.RIGHT_ELBOW],
                    keypoints[Keypoints.RIGHT_WRIST]
                )

            # Left knee angle
            if all(keypoints[i][2] >= POSE_CONFIDENCE_THRESHOLD for i in [Keypoints.LEFT_HIP, Keypoints.LEFT_KNEE, Keypoints.LEFT_ANKLE]):
                angles['left_knee'] = angle_between_points(
                    keypoints[Keypoints.LEFT_HIP],
                    keypoints[Keypoints.LEFT_KNEE],
                    keypoints[Keypoints.LEFT_ANKLE]
                )

            # Right knee angle
            if all(keypoints[i][2] >= POSE_CONFIDENCE_THRESHOLD for i in [Keypoints.RIGHT_HIP, Keypoints.RIGHT_KNEE, Keypoints.RIGHT_ANKLE]):
                angles['right_knee'] = angle_between_points(
                    keypoints[Keypoints.RIGHT_HIP],
                    keypoints[Keypoints.RIGHT_KNEE],
                    keypoints[Keypoints.RIGHT_ANKLE]
                )

            # Torso angle (vertical alignment)
            mid_shoulder = (keypoints[Keypoints.LEFT_SHOULDER] + keypoints[Keypoints.RIGHT_SHOULDER]) / 2
            mid_hip = (keypoints[Keypoints.LEFT_HIP] + keypoints[Keypoints.RIGHT_HIP]) / 2
            if mid_shoulder[2] >= POSE_CONFIDENCE_THRESHOLD and mid_hip[2] >= POSE_CONFIDENCE_THRESHOLD:
                # Angle from vertical
                dx = mid_shoulder[0] - mid_hip[0]
                dy = mid_shoulder[1] - mid_hip[1]
                angles['torso_tilt'] = np.degrees(np.arctan2(abs(dx), abs(dy)))

        except (IndexError, KeyError):
            pass

        return angles

    @property
    def is_initialized(self) -> bool:
        """Check if the estimator is initialized."""
        return self._is_initialized
