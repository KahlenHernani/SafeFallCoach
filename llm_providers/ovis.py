"""
Ovis2.5-2B local multimodal LLM provider.

Requires: NVIDIA GPU with CUDA, transformers==4.51.3
"""

import time
from typing import Dict, List, Optional

import numpy as np

from .base import LLMFeedbackResult, LLMProvider


class OvisProvider(LLMProvider):
    """Local Ovis 2.5 model provider with smart conditional loading."""

    def __init__(self, model_id: str = "AIDC-AI/Ovis2.5-2B",
    required_vram_gb: float = 12.0):
        self._model_id = model_id
        self._model = None
        self._torch_dtype = None
        self._dependencies_available = False
        self._vram_threshold_gb = required_vram_gb
        self._persistent_mode = False  # Set during initialize()
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check if requried dependencies are available."""
        try:
            import torch
            from transformers import AutoModelForCausalLM
            self._dependencies_available = True
        except ImportError:
            self._dependencies_available = False


    @property
    def name(self) -> str:
        mode = "Persistent" if self._persistent_mode else "Lazy"
        return f"Ovis-2.5 (Local, {mode})"

    @property
    def needs_rate_limiting(self) -> bool:
        """Local model - no rate limiting needed."""
        return False

    @property
    def rate_limit_config(self) -> dict:
        """No rate limiting for local model."""
        return {
            'max_calls_per_minute': 1000,  # Effectively unlimited
            'backoff_duration': 0.0,
            'only_for_falls': False         # Use for all feedback
        }

    def initialize(self) -> bool:
        """ Detect VRAM and choose loading strategy (persistent vs lazy)."""
        if not self._dependencies_available:
            print("[Ovis] Missing dependencies: torch, transformers")
            print("[Ovis] Run: pip install transformers torch")
            return False

        import torch
        if not torch.cuda.is_available():
            print("[Ovis] ERROR: CUDA not available")
            return False

        # Detect total VRAM
        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        gpu_name = torch.cuda.get_device_name()

        print(f"[Ovis] GPU: {gpu_name} ({total_vram_gb:.2f}GB VRAM)")

        # Decide loading strategy
        if total_vram_gb >= self._vram_threshold_gb:
            self._persistent_mode = True
            print("[Ovis] High VRAM detected - using PERSISTENT mode (always loaded)")
            print("[Ovis] Loading model at startup...")
            return self._load_model()
        else:
            self._persistent_mode = False
            print("[Ovis] Low VRAM detected - using LAZY mode (load on fall, unload after)")
            print("[Ovis] Model will load on first fall detection.")
            return True

    def _load_model(self) -> bool:
        """Lazy load the model into VRAM on first use."""
        if self._model is not None:
            return True  # Already loaded

        try:
            import torch
            from transformers import AutoModelForCausalLM
            import warnings

            # Suppress harmless warnings about image processor speed and device_map keys
            warnings.filterwarnings('ignore', message='.*use_fast.*')
            warnings.filterwarnings('ignore', message='.*device_map keys do not match.*')

            print(f"[Ovis] Loading model {self._model_id} into VRAM...")
            print("[Ovis] First run will download ~4GB (cached after)")

            # Determine dtype based on GPU's architecture
            if torch.cuda.is_available():
                capability = torch.cuda.get_device_capability()
                # bfloat16 requires Ampere+ (compute capability 8.0+)
                self._torch_dtype = torch.bfloat16 if capability[0] >= 8 else torch.float16
                print(f"[Ovis] GPU: {torch.cuda.get_device_name()}")
                print(f"[Ovis] Compute capability: {capability[0]}.{capability[1]}")
                print(f"[Ovis] Using dtype: {self._torch_dtype}")
            else:
                print("[Ovis] ERROR: CUDA not availaible")
                return False

            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_id,
                torch_dtype=self._torch_dtype,
                trust_remote_code=True,
                device_map="auto",              # Auto-distribute to GPU
                max_memory={0: "9GB"},          # Cap GPU 0 usage (leaves room for RTMLib+SiA)
            )

            self._model.eval()

            # Report VRAM usage
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                print(f"[Ovis] Model loaded successfully")
                print(f"[Ovis] VRAM: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")

            return True

        except Exception as e:
            print(f"[Ovis] Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            return False

    def unload_model(self) -> None:
        """Unload model from VRAM to free memory (only in lazy mode)."""
        if self._persistent_mode:
            # Don't unload in persistent mode
            return

        if self._model is None:
            return

        print("[Ovis] Unloading model from VRAM...")
        try:
            import torch

            # Get VRAM before unload
            if torch.cuda.is_available():
                before = torch.cuda.memory_allocated() / 1024**3

            del self._model
            self._model = None

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                after = torch.cuda.memory_allocated() / 1024**3
                freed = before - after
                print(f"[Ovis] Model unloaded. Freed ~{freed:.2f}GB RAM")

        except Exception as e:
            print(f"[Ovis] Error during unload: {e}")


    def generate_feedback(
        self,
        pose_angles: Dict[str, float],
        technique_score: int,
        fall_detected: bool = False,
        frames: Optional[List[np.ndarray]] = None,
        fall_action: Optional[str] = None,
        detected_actions: Optional[List] = None,
    ) -> Optional[LLMFeedbackResult]:

        if not self._dependencies_available:
            return None

        # Lazy load model on first call
        if not self._load_model():
            return None

        try:
            from PIL import Image
            import torch
            import cv2

            print(f"[Ovis] generate_feedback called (fall={fall_detected}, "
                  f"action={fall_action}, frames={len(frames) if frames else 0})", flush=True)
            t0 = time.time()

            # Build multimodal feedback content
            feedback_content = []

            # Add frames as images (convert BGR numpy -> PIL RGB)
            if frames:
                for i, frame in enumerate(frames):
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_frame)
                    feedback_content.append({"type": "image", "image": pil_image})

            # Build text prompt
            prompt_text = self._build_prompt(
                pose_angles, technique_score, fall_detected, len(frames or []),
                fall_action=fall_action, detected_actions=detected_actions,
            )
            feedback_content.append({"type": "text", "text": prompt_text})

            messages = [{"role": "user", "content": feedback_content}]

            # Preprocess and generate
            input_ids, pixel_values, grid_thws = self._model.preprocess_inputs(
                messages = messages,
                add_generation_prompt = True,
                enable_thinking = False,
            )
            input_ids = input_ids.cuda()
            if pixel_values is not None:
                pixel_values = pixel_values.cuda()
            if grid_thws is not None:
                grid_thws = grid_thws.cuda()

            with torch.no_grad():
                outputs = self._model.generate(
                    inputs = input_ids,
                    pixel_values = pixel_values,
                    grid_thws = grid_thws,
                    max_new_tokens = 700,
                    do_sample = True,
                    temperature = 0.7,
                    eos_token_id = self._model.text_tokenizer.eos_token_id,
                    pad_token_id = self._model.text_tokenizer.pad_token_id,
                )

            # Decode generated tokens (Ovis generate returns only new tokens)
            text = self._model.text_tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            print(f"[Ovis] Inference completed in {time.time() - t0:.1f}s, "
                  f"output length: {len(text)} chars", flush=True)

            # Parse technique score from Ovis response
            ovis_score = self._parse_technique_score(text)
            if ovis_score is not None:
                print(f"[Ovis] Technique score: {ovis_score}/100")
                if ovis_score >= 80:
                    severity = "success"
                elif ovis_score >= 60:
                    severity = "info"
                else:
                    severity = "warning"
            else:
                print("[Ovis] No technique score available")
                severity = "info"

            return LLMFeedbackResult(
                message = text,
                severity = severity,
                pose_score = ovis_score
            )

        except Exception as e:
            print(f"[Ovis] Inference error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_raw(
        self,
        prompt: str,
        frames: Optional[List[np.ndarray]] = None,
        max_new_tokens: int = 800,
    ) -> Optional[str]:
        """Generate raw text from a custom prompt (for educational instructions)."""
        if not self._dependencies_available:
            return None

        if not self._load_model():
            return None

        try:
            from PIL import Image
            import torch
            import cv2

            content = []

            if frames:
                for frame in frames:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_frame)
                    content.append({"type": "image", "image": pil_image})

            content.append({"type": "text", "text": prompt})

            messages = [{"role": "user", "content": content}]

            input_ids, pixel_values, grid_thws = self._model.preprocess_inputs(
                messages=messages,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            input_ids = input_ids.cuda()
            if pixel_values is not None:
                pixel_values = pixel_values.cuda()
            if grid_thws is not None:
                grid_thws = grid_thws.cuda()

            with torch.no_grad():
                outputs = self._model.generate(
                    inputs=input_ids,
                    pixel_values=pixel_values,
                    grid_thws=grid_thws,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.5,
                    eos_token_id=self._model.text_tokenizer.eos_token_id,
                    pad_token_id=self._model.text_tokenizer.pad_token_id,
                )

            text = self._model.text_tokenizer.decode(
                outputs[0], skip_special_tokens=True
            ).strip()
            return text

        except Exception as e:
            print(f"[Ovis] generate_raw error: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def _parse_technique_score(text: str) -> Optional[int]:
        """Extract technique score from Ovis response text.

        Looks for patterns like "Technique score: 75" or "Technique score: 75/100".
        """
        import re
        match = re.search(r'[Tt]echnique\s+[Ss]core[:\s]+(\d{1,3})', text)
        if match:
            score = int(match.group(1))
            if 0 <= score <= 100:
                return score
        return None

    def _build_prompt(
        self,
        pose_angles: Dict[str, float],
        technique_score: int,
        fall_detected: bool,
        num_frames: int,
        fall_action: Optional[str] = None,
        detected_actions: Optional[List] = None,
    ) -> str:
        # Build action context from SiA detection
        action_context = ""
        if fall_action:
            action_context = f"Detected fall type: {fall_action}. "
        if detected_actions:
            other = [f"{a} ({s:.0%})" for a, s in detected_actions if a != fall_action]
            if other:
                action_context += f"Other detected activities: {', '.join(other)}. "

        if fall_detected and num_frames > 0:
            context = (
                f"You are viewing {num_frames} sequential frames of an elderly person "
                f"practicing a fall / fall recovery technique. The images show moments "
                f"before and after the fall. {action_context}"
            )

            return f"""You are a fall prevention coach for the SafeFall Coach app, coaching an older adult practicing safe falling.

        {context}

        Analyze the images carefully and give thorough, detailed coaching. Respond with exactly this format:

        Technique score: <number from 0 to 100 based on how well they executed the fall technique>
        What you did well: (3-4 specific things you observe in the images, e.g. good chin tuck, knees bent. Describe what you actually see in each.)
        What to improve: (3-4 specific things to work on. For EACH one, briefly explain WHY it matters for avoiding injury.)
        How to do it better next time: (2-3 concrete, step-by-step cues they can practice)
        Recovery tip: (a clear, step-by-step description of how to safely get back up, using nearby support if available)
        Environment & safety: (1-2 sentences on the surroundings — padding, hard objects, furniture to use or avoid)

        Write in a warm, encouraging tone. Be specific and detailed — aim for several full sentences in each section rather than short fragments.

        Scoring guide:
        - 80-100: Excellent technique, safe execution
        - 60-79: Good attempt, minor corrections needed
        - 40-59: Needs improvement, some unsafe elements
        - 0-39: Significant safety concerns, major corrections needed

        Safe-fall technique criteria to evaluate:
        - Chin tucked to protect the head when falling backwards
        - Arms bent, not extended (avoid catching with straight palms/wrists)
        - Knees bent, controlled descent
        - Body aligned, rolling through impact rather than landing flat
        - Landing on padded body parts (forearm, thigh, buttock) rather than bony points

        Note any nearby furniture or objects (couch, chair, table, wall) that could help with recovery
        (e.g. "use the couch armrest to push yourself up") or pose a safety risk.

        Be encouraging, specific to what you see in the images, and use plain text only."""

        elif fall_detected:
            context = f"A fall was just detected during practice. {action_context}"
        else:
            context = "The user is practicing fall techniques."

        return f"""You are a fall prevention coach for the SafeFall Coach app.
        {context}

        Analyze the fall technique AND the safety of the environment, then give detailed,
        encouraging coaching (several sentences, not just one tip).

        Cover both:
        - TECHNIQUE: chin tucking, arm positioning (arms bent not extended), knee bending,
        rolling motion, body alignment — say what looks good and what to adjust, and why.
        - SAFETY: head protection, landing surface, proximity to furniture/hard objects, overall injury risk.

        Finish with 1-2 concrete cues they can try right now. Be specific and warm.
        No markdown. Plain text only."""
