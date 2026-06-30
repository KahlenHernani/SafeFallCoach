# Ovis2.5-2B Implementation Plan for Active Learning Mode

**Date:** February 10, 2026
**Updated:** February 11, 2026 (smart conditional loading for high-VRAM GPUs)
**Goal:** Replace Gemini API with local Ovis2.5-2B multimodal LLM for fall coaching feedback
**Scope:** Working OvisProvider (MVP) with smart VRAM-based loading strategy

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hardware | NVIDIA GPU 8GB+ VRAM | Full GPU inference, no quantization needed |
| Inference trigger | Moments before + after fall events | Captures the key moments that matter for technique analysis |
| Input mode | Multimodal (image + text) | Leverages Ovis vision capabilities for richer, visual feedback |
| Model loading | HuggingFace auto-download | ~4GB download on first run, cached at `~/.cache/huggingface/` |
| Provider strategy | Replace Gemini entirely | No API key needed, unlimited local inference |
| Feedback focus | Technique + safety | Comprehensive: form critique + injury risk assessment |
| **GPU memory** | **Smart conditional loading** | **RTMLib + SiA always loaded (~2.5GB). Ovis: persistent on ≥16GB GPUs, lazy-loaded on 8-15GB GPUs. Auto-detects VRAM at startup.** |
| Latency tolerance | 1-3 seconds post-fall (no load delay on high VRAM) | Persistent mode: instant inference. Lazy mode: +1-2s first load only. |
| Frame capture | 3 pre-fall + 2 post-fall | From existing SiA 72-frame buffer + subsequent frames |

---

## Architecture Overview

```
Camera Frame (30fps)
    |
    v
RTMLib Pose Estimation (always loaded: ~0.5GB VRAM) --> Joint Angles
    |
    v
SiA Fall Detection (always loaded: ~1-2GB VRAM, 72-frame buffer)
    |
    |-- Fall Detected?
    |       |
    |       YES --> Extract 3 pre-fall frames from SiA buffer
    |       |       Collect 2 post-fall frames from subsequent process_frame calls
    |       |       Convert all 5 frames to PIL Images
    |       |       |
    |       |       v
    |       |   OvisProvider.generate_feedback(frames, pose_angles, technique_score)
    |       |       |
    |       |       v
    |       |   [CONDITIONAL LOAD]
    |       |   - High VRAM (≥16GB): Ovis pre-loaded at startup, ready instantly
    |       |   - Low VRAM (8-15GB): Lazy load on first fall (~1-2s delay)
    |       |       |
    |       |       v
    |       |   Multimodal prompt: [Image1] [Image2] ... [Image5] + coaching prompt
    |       |       |
    |       |       v
    |       |   Ovis2.5-2B inference (~1-3 sec)
    |       |       |
    |       |       v
    |       |   Technique + safety feedback --> WebSocket --> Mobile App
    |       |       |
    |       |       v
    |       |   [CONDITIONAL UNLOAD]
    |       |   - High VRAM: Keep loaded (persistent)
    |       |   - Low VRAM: Unload to free VRAM (back to ~2.5GB)
    |       |
    |       NO --> Rule-based coaching (existing logic, no LLM call, no Ovis)
```

**VRAM Timeline:**

**High VRAM Mode (≥16GB):**
- **Continuous**: RTMLib + SiA + Ovis = ~10.5GB (persistent)
- **Fall detected**: Instant inference (~1-3s, no load delay)

**Low VRAM Mode (8-15GB):**
- **Continuous**: RTMLib + SiA = ~2.5GB
- **Fall detected**: Load Ovis → Peak ~10.5GB for 2-5 seconds
- **Feedback sent**: Unload Ovis → Back to ~2.5GB baseline

---

## Smart Conditional Loading Strategy

**Why Conditional?**
- **Problem**: Loading/unloading Ovis repeatedly (lazy mode) has overhead (~1-2s per fall)
- **Solution**: Keep Ovis loaded on high-VRAM GPUs for instant inference (no load delay)

**How It Works:**

1. **At Startup** (`OvisProvider.initialize()`):
   - Detect total GPU VRAM via `torch.cuda.get_device_properties(0).total_memory`
   - If VRAM ≥ 16GB → **Persistent Mode**: Load Ovis immediately, never unload
   - If VRAM < 16GB → **Lazy Mode**: Don't load yet, load on first fall, unload after

2. **During Fall Events**:
   - **Persistent Mode**: Ovis already loaded → instant inference (~1-3s)
   - **Lazy Mode**: Load Ovis (if not loaded) → inference (~2-5s first fall, ~1-3s subsequent) → unload

3. **Configurable Threshold**:
   - Default: 16GB (optimized for RTX 4060/4070 and up)
   - Can override via `OvisProvider(vram_threshold_gb=20.0)` for custom thresholds

**Benefits:**
- **High-VRAM GPUs (RTX 4090, A6000)**: Zero load delay, instant feedback
- **Low-VRAM GPUs (RTX 2080 Ti, RTX 3060)**: Still works, avoids OOM, slight delay acceptable
- **Easy to Implement**: Single VRAM check at startup, rest is automatic

---

## Files to Modify

### 1. `active_learning_engine/models/llm_provider.py` (~60% of work)

**Update `LLMProvider` abstract base class:**
```python
@abstractmethod
def generate_feedback(
    self,
    pose_angles: Dict[str, float],
    technique_score: int,
    fall_detected: bool = False,
    frames: Optional[List[np.ndarray]] = None,  # NEW: BGR frames
) -> Optional[LLMFeedbackResult]:
    """Generate coaching feedback from pose data and optional frames."""
    pass
```

**Update `GeminiProvider.generate_feedback()`:**
- Add `frames` parameter (ignored, for backward compatibility)
- No other changes needed

**Implement `OvisProvider` with lazy loading:**

```python
class OvisProvider(LLMProvider):
    """Local Ovis 2.5-2B multimodal model provider with smart conditional loading."""

    def __init__(self, model_id: str = "AIDC-AI/Ovis2.5-2B", vram_threshold_gb: float = 16.0):
        self._model_id = model_id
        self._model = None
        self._torch_dtype = None
        self._dependencies_available = False
        self._vram_threshold_gb = vram_threshold_gb
        self._persistent_mode = False  # Set during initialize()
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        try:
            import torch
            from transformers import AutoModelForCausalLM
            self._dependencies_available = True
        except ImportError:
            self._dependencies_available = False

    @property
    def name(self) -> str:
        mode = "Persistent" if self._persistent_mode else "Lazy"
        return f"Ovis-2.5-2B (Local, {mode})"

    @property
    def needs_rate_limiting(self) -> bool:
        return False  # Local model, no rate limits

    @property
    def rate_limit_config(self) -> dict:
        return {
            'max_calls_per_minute': 1000,
            'backoff_duration': 0.0,
            'only_for_falls': False
        }

    def initialize(self) -> bool:
        """Detect VRAM and choose loading strategy (persistent vs lazy)."""
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

        print(f"[Ovis] GPU: {gpu_name} ({total_vram_gb:.1f}GB VRAM)")

        # Decide loading strategy
        if total_vram_gb >= self._vram_threshold_gb:
            self._persistent_mode = True
            print(f"[Ovis] High VRAM detected - using PERSISTENT mode (always loaded)")
            print(f"[Ovis] Loading model at startup...")
            return self._load_model()
        else:
            self._persistent_mode = False
            print(f"[Ovis] Low VRAM detected - using LAZY mode (load on fall, unload after)")
            print(f"[Ovis] Model will load on first fall detection.")
            return True

    def _load_model(self) -> bool:
        """Lazy load the model into VRAM on first use."""
        if self._model is not None:
            return True  # Already loaded

        try:
            import torch
            from transformers import AutoModelForCausalLM

            print(f"[Ovis] Loading model {self._model_id} into VRAM...")
            print("[Ovis] First run will download ~4GB (cached after)")

            # Determine dtype based on GPU capability
            if torch.cuda.is_available():
                capability = torch.cuda.get_device_capability()
                # bfloat16 requires Ampere+ (compute capability 8.0+)
                self._torch_dtype = torch.bfloat16 if capability[0] >= 8 else torch.float16
                print(f"[Ovis] GPU: {torch.cuda.get_device_name()}")
                print(f"[Ovis] Compute capability: {capability[0]}.{capability[1]}")
                print(f"[Ovis] Using dtype: {self._torch_dtype}")
            else:
                print("[Ovis] ERROR: CUDA not available")
                return False

            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_id,
                torch_dtype=self._torch_dtype,
                trust_remote_code=True,
            ).cuda()

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
                print(f"[Ovis] Model unloaded. Freed ~{freed:.2f}GB VRAM")

        except Exception as e:
            print(f"[Ovis] Error during unload: {e}")

    def generate_feedback(
        self,
        pose_angles: Dict[str, float],
        technique_score: int,
        fall_detected: bool = False,
        frames: Optional[List[np.ndarray]] = None,
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

            # Build multimodal message content
            content = []

            # Add frames as images (convert BGR numpy -> PIL RGB)
            if frames:
                for i, frame in enumerate(frames):
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_frame)
                    content.append({"type": "image", "image": pil_image})

            # Build text prompt
            prompt_text = self._build_prompt(pose_angles, technique_score, fall_detected, len(frames or []))
            content.append({"type": "text", "text": prompt_text})

            messages = [{"role": "user", "content": content}]

            # Preprocess and generate
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
                    max_new_tokens=150,  # Short feedback for mobile display
                    do_sample=True,
                    temperature=0.7,
                    eos_token_id=self._model.text_tokenizer.eos_token_id,
                    pad_token_id=self._model.text_tokenizer.pad_token_id,
                )

            # Decode only the generated tokens (skip input)
            generated = outputs[0][input_ids.shape[1]:]
            text = self._model.text_tokenizer.decode(generated, skip_special_tokens=True).strip()

            # Determine severity from technique score
            if technique_score >= 80:
                severity = "success"
            elif technique_score >= 60:
                severity = "info"
            else:
                severity = "warning"

            return LLMFeedbackResult(
                message=text[:200],  # Cap for mobile display
                severity=severity,
                pose_score=technique_score,
            )

        except Exception as e:
            print(f"[Ovis] Inference error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_prompt(
        self,
        pose_angles: Dict[str, float],
        technique_score: int,
        fall_detected: bool,
        num_frames: int,
    ) -> str:
        angles_str = ", ".join(f"{k}: {v:.1f} degrees" for k, v in pose_angles.items())

        if fall_detected and num_frames > 0:
            context = (
                f"You are viewing {num_frames} sequential frames of an elderly person "
                f"practicing a fall technique. The images show moments before and after "
                f"the fall."
            )
        elif fall_detected:
            context = "A fall was just detected during practice."
        else:
            context = "The user is practicing fall techniques."

        return f"""You are a fall prevention coach for the SafeFall Coach app.
{context}

Technique score: {technique_score}/100
Body angles: {angles_str}

Analyze the fall technique AND safety of the environment. Give ONE short tip (max 2 sentences).

Consider:
- TECHNIQUE: chin tucking, arm positioning (arms bent not extended), knee bending, rolling motion, body alignment
- SAFETY: head protection, landing surface, proximity to furniture/hard objects, overall injury risk

Be encouraging and specific. No markdown. Plain text only."""
```

---

### 2. `active_learning_engine/models/sia_detector.py`

**Add `get_key_frames()` method to `SiADetector` class:**

```python
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
        # Evenly space across buffer, biased toward recent frames
        step = buffer_len // num_frames
        indices = [buffer_len - 1 - (i * step) for i in range(num_frames)]
        indices.reverse()  # Chronological order

    frames = []
    for idx in indices:
        # Buffer stores CHW format at model input resolution (240x320)
        # Convert back to HWC BGR for downstream use
        chw = self.buffer[idx]
        hwc = chw.transpose(1, 2, 0)  # CHW -> HWC
        # Note: these are at model resolution (320x240), not original
        frames.append(hwc)

    return frames
```

**Important note:** The SiA buffer stores frames at model resolution (320x240) in CHW format. For Ovis, these need to be converted back to HWC. The resolution is lower than camera output but sufficient for Ovis analysis.

---

### 3. `active_learning_engine/models/feedback_generator.py`

**Changes:**

1. **Switch provider (line 49):**
```python
# BEFORE:
self._llm_provider: LLMProvider = GeminiProvider(free_tier=True)

# AFTER:
self._llm_provider: LLMProvider = OvisProvider()
```

2. **Update `generate_fall_feedback()` to accept frames and unload Ovis after inference:**
```python
def generate_fall_feedback(self,
                           technique_score: int,
                           pose_angles: Dict[str, float],
                           frames: Optional[List[np.ndarray]] = None) -> CoachingFeedback:
    # ... existing code ...

    # Try LLM first if enabled (fall events always eligible)
    if self.use_llm and self._can_call_llm():
        llm_result = self._try_llm_with_backoff(
            pose_angles=pose_angles,
            technique_score=technique_score,
            fall_detected=True,
            frames=frames,  # NEW: pass frames
        )

        # NEW: Unload Ovis to free VRAM (only in lazy mode, no-op in persistent mode)
        if hasattr(self._llm_provider, 'unload_model'):
            self._llm_provider.unload_model()

        if llm_result:
            return CoachingFeedback(
                message=llm_result.message,
                severity=llm_result.severity,
                category="fall_technique",
                suggestion=self._get_fall_suggestion(technique_score, pose_angles),
            )

    # Fallback to rule-based
    return self._generate_rule_based_fall_feedback(technique_score, pose_angles)
```

3. **Update `_try_llm_with_backoff()` to accept and pass frames:**
```python
def _try_llm_with_backoff(self, pose_angles, technique_score, fall_detected,
                          frames=None) -> Optional[LLMFeedbackResult]:
    try:
        result = self._llm_provider.generate_feedback(
            pose_angles=pose_angles,
            technique_score=technique_score,
            fall_detected=fall_detected,
            frames=frames,  # NEW: pass frames
        )
        # ... rest unchanged ...
```

4. **Update `generate()` to pass frames through:**
```python
# In the generate() method, update the _try_llm_with_backoff call:
llm_result = self._try_llm_with_backoff(
    pose_angles=pose_angles,
    technique_score=pose_score,
    fall_detected=fall_detected,
    frames=[frame] if frame is not None else None,  # Pass single frame
)
```

---

### 4. `active_learning_engine/app.py`

**Add post-fall frame collection logic to `ActiveLearningWizard`:**

```python
class ActiveLearningWizard:
    def __init__(self):
        # ... existing init ...

        # Post-fall frame collection
        self._collecting_post_fall = False
        self._post_fall_frames: List[np.ndarray] = []
        self._post_fall_target: int = 2  # Collect 2 frames after fall
        self._pre_fall_frames: List[np.ndarray] = []
        self._pending_fall_data: Optional[dict] = None  # Store fall data while collecting
```

**Update `process_frame()` fall handling:**

```python
def process_frame(self, frame):
    # ... existing pose + SiA detection ...

    feedback_text = ""
    current_time = time.time()

    # Check if we're collecting post-fall frames
    if self._collecting_post_fall:
        self._post_fall_frames.append(frame.copy())
        if len(self._post_fall_frames) >= self._post_fall_target:
            # All frames collected - now run Ovis
            all_frames = self._pre_fall_frames + self._post_fall_frames
            self._collecting_post_fall = False

            data = self._pending_fall_data
            fall_feedback = self.feedback_generator.generate_fall_feedback(
                technique_score=data['technique_score'],
                pose_angles=data['pose_angles'],
                frames=all_frames,
            )

            self.session_manager.record_fall(
                technique_score=data['technique_score'],
                feedback=fall_feedback.message,
                pose_angles=data['pose_angles'],
            )
            self.ws_server.send_fall_event(data['technique_score'], fall_feedback.message)
            feedback_text = f"FALL DETECTED! {fall_feedback.message}"
            self._pending_fall_data = None

    elif fall_result.detected:
        # Fall just detected - grab pre-fall frames from SiA buffer
        self._pre_fall_frames = self.sia_detector.get_key_frames(num_frames=3)
        self._post_fall_frames = []
        self._collecting_post_fall = True
        self._pending_fall_data = {
            'technique_score': fall_result.technique_score or 70,
            'pose_angles': angles,
        }
        feedback_text = "Fall detected - analyzing technique..."

    elif current_time - self._last_feedback_time > self._feedback_interval:
        # Regular coaching feedback (rule-based, no Ovis call)
        feedback = self.feedback_generator.generate(
            pose_angles=angles,
            fall_detected=False,
            frame=frame  # Not used by Ovis for non-fall events
        )
        # ... rest unchanged ...
```

---

### 5. `active_learning_engine/requirements.txt`

**Add/verify these dependencies:**
```
# Existing deps (verify versions)
torch>=2.4.0
transformers>=4.51.0

# New: Ovis2.5-2B
flash-attn>=2.7.0    # Optional but recommended for faster inference
```

**Note on flash-attn:** This package requires CUDA toolkit and can be difficult to install. Ovis2.5-2B will work without it (using standard attention), just slower. If installation fails:
```bash
# Try pre-built wheel first
pip install flash-attn --no-build-isolation

# If that fails, skip it - Ovis will use sdpa attention fallback
```

---

### 6. `active_learning_engine/models/__init__.py`

Verify `OvisProvider` is exported (should already be if using wildcard import from `llm_provider`).

---

## Implementation Order

| Step | File | What | Est. Effort |
|------|------|------|-------------|
| 1 | `llm_provider.py` | Implement OvisProvider + update LLMProvider interface | Heavy |
| 2 | `sia_detector.py` | Add `get_key_frames()` method | Light |
| 3 | `feedback_generator.py` | Wire frames through + switch provider | Medium |
| 4 | `app.py` | Post-fall frame collection logic | Medium |
| 5 | `requirements.txt` | Add dependencies | Light |
| 6 | End-to-end test | Run app, verify Ovis loads and generates feedback | Light |

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `flash-attn` install fails | Slower inference (~2x) | Ovis works without it via sdpa attention. Skip if problematic. |
| `bfloat16` not supported | Model won't load | Auto-detect GPU capability; fall back to `float16` for pre-Ampere GPUs (RTX 2080 Ti) |
| ~~VRAM overflow~~ | ~~OOM crash~~ | **MITIGATED**: Smart conditional loading. High VRAM (≥16GB): persistent mode (~10.5GB continuous). Low VRAM (8-15GB): lazy mode (~2.5GB baseline, load on fall). |
| First-run download (~4GB) | Slow first startup | Print progress message. Model cached after first download. |
| First fall adds load latency (lazy mode) | +1-2s delay on first fall only | Only affects low-VRAM GPUs. High-VRAM GPUs use persistent mode (instant inference). |
| SiA buffer frames are low-res (320x240) | Lower quality Ovis analysis | Sufficient for fall technique assessment. Could optionally store full-res frames separately. |

---

## Testing Checklist

### Model Loading & Conditional Loading
**High VRAM Mode (≥16GB):**
- [ ] `OvisProvider.initialize()` detects high VRAM and enters persistent mode
- [ ] Ovis loads at startup (~10.5GB total VRAM)
- [ ] First fall: instant inference (no load delay)
- [ ] `unload_model()` is a no-op (model stays loaded)
- [ ] Multiple falls: consistent instant inference

**Low VRAM Mode (8-15GB):**
- [ ] `OvisProvider.initialize()` detects low VRAM and enters lazy mode
- [ ] Baseline VRAM usage (RTMLib + SiA) = ~2.5GB before any falls
- [ ] First fall triggers Ovis lazy load (~8GB VRAM increase)
- [ ] After inference, `unload_model()` frees VRAM (back to ~2.5GB)
- [ ] Second fall re-loads Ovis successfully (lazy load works repeatedly)

**Both Modes:**
- [ ] Ovis `generate_feedback()` returns valid text from test frames

### Frame Collection
- [ ] SiA `get_key_frames()` returns correct number of frames in chronological order
- [ ] Post-fall frame collection gathers 3 pre + 2 post frames correctly
- [ ] All 5 frames passed to Ovis have correct format (BGR numpy arrays)

### End-to-End
- [ ] Camera -> pose estimation -> fall detection -> frame collection -> Ovis load -> inference -> unload -> WebSocket broadcast
- [ ] Fallback: if Ovis fails to load, rule-based feedback still works
- [ ] Multiple falls in one session: Ovis loads/unloads correctly each time

### VRAM Monitoring
- [ ] Peak VRAM during Ovis inference ≤ 11GB (safe for RTX 2080 Ti)
- [ ] VRAM returns to baseline (~2.5GB) after each fall
- [ ] No memory leaks over 10+ fall events

---

## Ovis2.5-2B Quick Reference

- **Model ID:** `AIDC-AI/Ovis2.5-2B`
- **Size:** ~4GB download, ~7-8GB VRAM during inference (weights + activations + KV cache)
- **API:** `AutoModelForCausalLM.from_pretrained()` with `trust_remote_code=True`
- **Inference:** `model.preprocess_inputs()` -> `model.generate()` -> `model.text_tokenizer.decode()`
- **Input format:** Messages list with `{"type": "image", "image": PIL.Image}` and `{"type": "text", "text": "..."}`
- **Dtype:** `torch.bfloat16` (Ampere+ / RTX 3000+) or `torch.float16` (Turing / RTX 2000 series)
- **Loading:** Smart conditional - persistent on ≥16GB GPUs, lazy on 8-15GB GPUs (auto-detects at startup)
- **Source:** [HuggingFace](https://huggingface.co/AIDC-AI/Ovis2.5-2B) | [GitHub](https://github.com/AIDC-AI/Ovis) | [Paper](https://arxiv.org/abs/2508.11737)

## VRAM Budget Summary

**Persistent Mode (≥16GB VRAM):**
| Component | Continuous Usage |
|-----------|------------------|
| RTMLib | ~0.5GB |
| SiA | ~1-2GB |
| Ovis | ~7-8GB (always loaded) |
| **Total** | **~10.5GB** |

**Lazy Mode (8-15GB VRAM):**
| Component | Continuous Usage | Peak (During Fall) |
|-----------|------------------|-------------------|
| RTMLib | ~0.5GB | ~0.5GB |
| SiA | ~1-2GB | ~1-2GB |
| Ovis | 0GB (unloaded) | ~7-8GB (loaded) |
| **Total** | **~2.5GB** | **~10.5GB** |

**Target Hardware:**
- RTX 2080 Ti (11GB): ✅ Lazy mode, 95% peak usage, safe
- RTX 4090 (24GB): ✅ Persistent mode, 44% continuous usage, instant inference
