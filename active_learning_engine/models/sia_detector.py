"""
SiA Fall Detection Wrapper

This module wraps the SiA (Skeleton-in-Action) fall detection model
for real-time fall detection in the Active Learning Wizard.
"""

import json
import os
import numpy as np
import cv2
import time
import torch
import torch.nn.functional as F
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from pathlib import Path

# Load full AVA action vocabulary (80 actions) — needed for proper classification.
# With only a few actions, the model is forced to classify all motion as one of them,
# causing false positives. The full vocabulary lets it distinguish walking from falling.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_avatextaug = json.load(open(_PROJECT_ROOT / 'sia_model' / 'gpt' / 'GPT_AVA.json'))


@dataclass
class FallDetectionResult:
    """Result from fall detection analysis."""
    detected: bool
    confidence: float
    timestamp: float
    technique_score: Optional[int] = None
    action: Optional[str] = None  # The fall trigger action (e.g. 'fall down', 'lie/sleep')
    detected_actions: List[Tuple[str, float]] = field(default_factory=list)  # All actions detected on the person


class SiADetector:
    """
    Wrapper for SiA fall detection model.

    This class provides real-time fall detection using the SiA model
    with a streaming frame buffer approach.
    """

    def __init__(self, model_path: Optional[str] = None, buffer_size: int = 72):
        """
        Initialize the SiA fall detector.

        Args:
            model_path: Path to the SiA model weights. If None, uses default.
            buffer_size: Number of frames to buffer for temporal context (default: 72)
        """
        # Determine model path
        if model_path is None:
            project_root = Path(__file__).parent.parent.parent
            model_path = project_root / 'sia_model' / 'weights' / 'avak_b16_10.pt'

        self.model_path = Path(model_path)
        self.model = None
        self.postprocess = None
        self.text_embeds = None
        self._is_initialized = False

        # Frame buffer for temporal context
        self.buffer_size = buffer_size
        self.buffer = []
        self.frame_count = 0

        # Image processing settings
        self.imgsize = (240, 320)  # Height, Width for model input

        # Full AVA action vocabulary (80 actions) for proper classification
        self.all_actions = list(_avatextaug.keys())

        # Only these actions trigger a "fall detected" event
        self.fall_trigger_actions = {'fall down', 'lie/sleep'}

        # Inference throttling — only run model every N frames to reduce
        # noise and duplicate detections from nearly-identical buffers
        self._inference_interval = 8  # run inference every 8 frames
        self._frames_since_inference = 0
        self._last_result: Optional['FallDetectionResult'] = None

        # Device
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        # Normalization transform
        from torchvision.transforms import v2
        self.tfs = v2.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])

    def initialize(self) -> bool:
        """
        Initialize the model. Call this before processing frames.

        Returns:
            True if initialization successful, False otherwise.
        """
        try:
            # Check if model weights exist
            if not self.model_path.exists():
                print(f"[SiA] Model weights not found at {self.model_path}")
                print("[SiA] Please place the model weights at:")
                print("    sia_model/weights/avak_b16_10.pt")
                print("[SiA] Running in placeholder mode (no actual detection)")
                self._is_initialized = True
                return True

            # Import SiA model as subpackage to preserve relative imports
            from sia_model.sia import get_sia, PostProcessViz

            # Load model
            print(f"[SiA] Loading model from {self.model_path}")
            self.model = get_sia(
                size='b',
                pretrain=None,
                det_token_num=20,
                text_lora=True,
                num_frames=9
            )['sia']

            self.model.load_state_dict(
                torch.load(self.model_path, map_location=torch.device('cpu'), weights_only=False),
                strict=False
            )
            self.model.to(self.device)
            self.model.eval()

            # Initialize postprocessor
            self.postprocess = PostProcessViz()

            # Encode ALL action labels for proper classification
            self.text_embeds = self.model.encode_text(self.all_actions)
            self.text_embeds = F.normalize(self.text_embeds, dim=-1)

            self._is_initialized = True
            print(f"[SiA] Fall detector initialized on {self.device}")
            print(f"[SiA] Using {len(self.all_actions)} AVA actions for classification")
            print(f"[SiA] Fall trigger actions: {self.fall_trigger_actions}")
            return True

        except Exception as e:
            print(f"[SiA] Failed to initialize: {e}")
            import traceback
            traceback.print_exc()
            print("[SiA] Running in placeholder mode")
            self._is_initialized = True
            return True

    def detect(self, frame: np.ndarray, pose_keypoints: Optional[np.ndarray] = None) -> FallDetectionResult:
        """
        Detect falls in the given frame.

        Args:
            frame: BGR image frame from camera
            pose_keypoints: Optional pose keypoints from RTMLib (not used by SiA)

        Returns:
            FallDetectionResult with detection status and confidence
        """
        if not self._is_initialized:
            raise RuntimeError("SiA detector not initialized. Call initialize() first.")

        timestamp = time.time()

        # If model not loaded, return placeholder result
        if self.model is None:
            return FallDetectionResult(
                detected=False,
                confidence=0.0,
                timestamp=timestamp,
                technique_score=None,
                action=None
            )

        # Resize frame and add to buffer
        resized = cv2.resize(frame, (self.imgsize[1], self.imgsize[0]),
                           interpolation=cv2.INTER_NEAREST)
        color_image = resized.transpose(2, 0, 1)  # HWC -> CHW
        self.buffer.append(color_image)

        # Keep buffer at max size
        if len(self.buffer) > self.buffer_size:
            self.buffer.pop(0)

        self.frame_count += 1

        # Need full buffer before processing
        if len(self.buffer) < self.buffer_size:
            return FallDetectionResult(
                detected=False,
                confidence=0.0,
                timestamp=timestamp,
                technique_score=None,
                action=None
            )

        # Throttle inference — skip frames between runs to avoid
        # duplicate detections from nearly-identical buffers
        self._frames_since_inference += 1
        if self._frames_since_inference < self._inference_interval:
            if self._last_result is not None:
                # Return previous result but with updated timestamp and detected=False
                # so the same fall doesn't trigger multiple recordings
                return FallDetectionResult(
                    detected=False,
                    confidence=self._last_result.confidence,
                    timestamp=timestamp,
                    technique_score=None,
                    action=self._last_result.action,
                )
            return FallDetectionResult(
                detected=False,
                confidence=0.0,
                timestamp=timestamp,
                technique_score=None,
                action=None,
            )
        self._frames_since_inference = 0

        try:
            # Sample 9 frames evenly from buffer
            step = self.buffer_size // 9
            clip = np.array(self.buffer[0:self.buffer_size:step])

            # Convert to tensor and normalize
            clip_torch = torch.tensor(clip) / 255.0
            clip_torch = self.tfs(clip_torch)

            # Run model inference
            with torch.no_grad():
                outputs = self.model.encode_vision(clip_torch.unsqueeze(0).to(self.device))
                outputs['pred_logits'] = F.normalize(outputs['pred_logits'], dim=-1) @ self.text_embeds.T

                # Get frame dimensions for postprocessing
                outsize = (frame.shape[0], frame.shape[1])

                result = self.postprocess(
                    outputs,
                    outsize,
                    human_conf=0.0,
                    thresh=0.25
                )[0]

                # Add text labels (mapped to full 80-action vocabulary)
                result['text_labels'] = [
                    [self.all_actions[e] for e in ele]
                    for ele in result['labels']
                ]

                # Check for fall detection
                boxes = result['boxes']
                labels = result['text_labels']
                scores = result['scores']

                # Find highest confidence fall across all detected persons
                max_fall_confidence = 0.0
                fall_action = None
                fall_person_actions = []
                detected = False

                for i, (label_list, score_list) in enumerate(zip(labels, scores)):
                    person_actions = [(act, float(s)) for act, s in zip(label_list, score_list)]
                    for action, score_val in person_actions:
                        if action in self.fall_trigger_actions:
                            if score_val > max_fall_confidence:
                                max_fall_confidence = score_val
                                fall_action = action
                                fall_person_actions = person_actions
                                detected = True

                # Evaluate technique if fall detected
                technique_score = None
                if detected:
                    actions_str = ", ".join(
                        f"{act} ({s:.2f})" for act, s in fall_person_actions
                    )
                    print(f"[SiA] Fall detected: {fall_action} "
                          f"(confidence: {max_fall_confidence:.2f}) | "
                          f"Actions: {actions_str}")

                if detected and pose_keypoints is not None:
                    technique_score = self._evaluate_technique(pose_keypoints)

                result = FallDetectionResult(
                    detected=detected,
                    confidence=max_fall_confidence,
                    timestamp=timestamp,
                    technique_score=technique_score,
                    action=fall_action,
                    detected_actions=fall_person_actions,
                )
                self._last_result = result
                return result

        except Exception as e:
            print(f"[SiA] Detection error: {e}")
            import traceback
            traceback.print_exc()
            return FallDetectionResult(
                detected=False,
                confidence=0.0,
                timestamp=timestamp,
                technique_score=None,
                action=None
            )

    
    def reset_buffer(self):
        """Reset the frame buffer and counters for a new session."""
        self.buffer.clear()
        self.frame_count = 0
        self._frames_since_inference = 0
        self._last_result = None

    def get_key_frames(self, num_frames: int = 3) -> List[np.ndarray]:
        """
        Extract key frames from the buffer for LLM analysis.

        Selects evenly-spaced frames from the buffer, giving temporal
        context of the moments leading up to the current detection.

        Args:
            num_frames: Number of frames to extract (default 3)

        Returns:
            List of BGR numpy arrays (full resolution reconstructed from buffer)
        """

        if not self.buffer or num_frames <= 0:
            return []
        
        buffer_len = len(self.buffer)
        if buffer_len <= num_frames:
            # Return all frames if buffer smaller than requested
            indices = list(range(buffer_len))
        else: 
            # Evenly spaced across buffer with bias towards recent frames
            step = buffer_len // num_frames
            indices = [buffer_len - 1 - (i * step) for i in range(num_frames)]
            indices.reverse()  # Chronological order
        
        frames = []
        for idx in indices: 
            # Buffer stores CHW format at model input resolution 240x320
            # Convert back to HWC BGR for downstream use
            chw = self.buffer[idx]
            hwc = chw.transpose(1, 2, 0) # CHW -> HWC

            # NOTE: these frames are at model resolution (320x240), not orginal 
            frames.append(hwc)
        
        return frames






    
    
    
    def _evaluate_technique(self, pose_keypoints: Optional[np.ndarray]) -> Optional[int]:
        """
        Evaluate the fall technique based on pose keypoints.

        Args:
            pose_keypoints: Body keypoints from pose estimation

        Returns:
            Technique score 0-100, or None if cannot evaluate
        """
        if pose_keypoints is None:
            return None

        # TODO: Implement technique evaluation
        # Consider factors like:
        # - Chin tucked (head position relative to chest)
        # - Arms positioned to break fall
        # - Rolling motion (if tracking over time)
        # - Landing on appropriate body parts

        return None

    @property
    def is_initialized(self) -> bool:
        """Check if the detector is initialized."""
        return self._is_initialized
