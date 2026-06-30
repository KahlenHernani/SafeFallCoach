# Active Learning Mode v2 - Product & Implementation Plan

**Document Version:** 1.0
**Date:** February 5, 2026
**Status:** Draft - Pending Team Review

---

## Executive Summary

This document outlines the v2 improvements for the Active Learning Wizard, focusing on UI/UX enhancements, SiA fall detection integration, and MLLM-based feedback generation. The goal is to transform the current prototype into a professional, accessible tool for physical therapists, caregivers, and researchers.

---

## 1. User Research Summary

### 1.1 Target Users
| Persona | Primary Use | Key Needs |
|---------|-------------|-----------|
| Physical Therapist/Clinician | Guided patient training | Clear metrics, session tracking, professional appearance |
| Caregiver (non-clinical) | Home practice supervision | Simple controls, readable from distance, audio feedback |
| Research/QA Tester | Data collection & debugging | Developer mode, detailed logs, raw data access |

### 1.2 Usage Environments
- **Clinical setting (PT office):** Controlled lighting, dedicated space, patient at distance from screen
- **Home living room:** Variable lighting, furniture obstacles, caregiver may be near patient
- **Research lab:** Controlled environment, focus on data collection and analysis

### 1.3 v1 Pain Points (Must Address)
1. **Hard to see feedback from distance** - Text too small during active training
2. **Confusing session state** - Unclear if session is active, paused, or needs setup
3. **QR code scanning issues** - Code too small, connection process unclear
4. **Information overload** - Too much technical data for non-developers
5. **Dark background, small text** - Poor contrast and readability
6. **Performance/FPS issues** - Video lag affecting real-time feedback

---

## 2. UI/UX Requirements

### 2.1 Visual Design Principles

**Style:** Clinical/Professional
- Clean whites and blues
- Minimal decoration
- Medical software aesthetic
- SafeFall Coach branding consistency

**Accessibility:**
- Minimum 18px font for body text, 24px+ for feedback banners
- High contrast (WCAG AA minimum)
- Colorblind-friendly palette (no red/green only indicators)
- Icons + text labels (never icons alone)

**Color Palette (Proposed):**
```
Primary Blue:      #2563EB (actions, links)
Success Green:     #10B981 (good form, positive feedback)
Warning Amber:     #F59E0B (needs attention)
Error Red:         #EF4444 (critical issues, falls detected)
Background:        #F8FAFC (light gray-white)
Surface:           #FFFFFF (cards, panels)
Text Primary:      #1E293B (dark slate)
Text Secondary:    #64748B (muted)
```

### 2.2 Layout Structure

**Primary Layout: Video-Dominant Single Screen**

```
┌─────────────────────────────────────────────────────────────────────┐
│  [SafeFall Logo]  Active Learning Wizard        [Settings ⚙️] [?]  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                                                             │   │
│  │                                                             │   │
│  │                    CAMERA FEED                              │   │
│  │              (70%+ of screen height)                        │   │
│  │                                                             │   │
│  │    ┌──────────┐                        ┌─────────────────┐  │   │
│  │    │ TRAFFIC  │                        │  SESSION TIMER  │  │   │
│  │    │ LIGHTS   │                        │    00:05:32     │  │   │
│  │    │ 🟢🟡🟢   │                        │  Falls: 3       │  │   │
│  │    └──────────┘                        └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ✓ GOOD FORM - Keep your chin tucked and arms ready        │   │
│  │    (Large feedback banner - readable from 10+ feet)         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│  │  ▶ START SESSION       │  │  ⏸ PAUSE  │  ⏹ END SESSION     │  │
│  └─────────────────────────┘  └─────────────────────────────────┘  │
│                                                                     │
│  Connection: 🟢 Mobile Connected (iPhone 14)     [View QR Code]    │
└─────────────────────────────────────────────────────────────────────┘
```

**Video Feed Overlays:**
- Traffic light indicators (top-left): Body parts with good/warning/error colors
- Session timer + fall count (top-right)
- Skeleton overlay on person (semi-transparent)
- Connection status indicator (corner)

**Collapsible Side Panel (Toggle with keyboard shortcut or button):**
- Detailed pose metrics (for developers)
- Feedback history log
- Connected devices list

### 2.3 Component Specifications

#### 2.3.1 Camera Feed
- **Default size:** 70%+ of viewport height
- **Aspect ratio:** 16:9 or 4:3 (auto-detect from camera)
- **Overlays:**
  - Skeleton: Semi-transparent, colorblind-friendly palette
  - Traffic lights: 3 indicators (upper body, core, lower body)
  - Timer badge: Top-right, high contrast background
- **Resizable:** User can drag to resize (remember preference)

#### 2.3.2 Feedback Banner
- **Height:** 80-100px minimum
- **Font size:** 24-32px (readable from 10+ feet)
- **Background color:** Indicates severity (green/amber/red with patterns)
- **Animation:** Subtle pulse on new feedback, avoid jarring transitions
- **Audio:** Optional TTS readout (configurable voice)

#### 2.3.3 Connection Panel (Pre-Session)
```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONNECT YOUR MOBILE DEVICE                       │
│                                                                     │
│         ┌─────────────────────┐                                    │
│         │                     │   1. Open SafeFall Coach app       │
│         │      QR CODE        │   2. Go to Active Learning         │
│         │     (300x300px)     │   3. Tap "Connect to Desktop"     │
│         │                     │   4. Scan this QR code            │
│         └─────────────────────┘                                    │
│                                                                     │
│         Or enter session code:  [ ABC-123-XYZ ]                   │
│                                                                     │
│         [Skip - Continue Without Mobile]                           │
└─────────────────────────────────────────────────────────────────────┘
```
- **QR Code:** 300x300px minimum, high error correction
- **Session Code:** 9-character alphanumeric for manual entry
- **Instructions:** Clear step-by-step, large text

#### 2.3.4 Session Controls
| Control | State | Appearance |
|---------|-------|------------|
| Start Session | Pre-session | Large primary button, prominent |
| Pause | Active session | Secondary button |
| Resume | Paused | Primary button (replaces Pause) |
| End Session | Active/Paused | Stop variant, requires confirmation |

#### 2.3.5 Status Indicators
- **Connection status:** Icon + text + device name
- **Session state:** Clear visual indicator (badge color, text)
- **Frame rate:** Only in developer mode
- **WiFi quality:** Warning if degraded, with fallback message

### 2.4 Session Flow

```
┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  IDLE   │───▶│  CONNECTING │───▶│   ACTIVE    │───▶│   SUMMARY   │
│         │    │  (QR/Code)  │    │  (Training) │    │  (Results)  │
└─────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │   PAUSED    │
                                  └─────────────┘
```

**State Behaviors:**
- **IDLE:** Show connection panel, camera preview, settings accessible
- **CONNECTING:** Large QR code + session code, waiting for mobile
- **ACTIVE:** Full training view, feedback active, metrics tracking
- **PAUSED:** Video continues, feedback paused, clear "Paused" indicator
- **SUMMARY:** Full-screen overlay with session results

### 2.5 Session Summary Screen

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SESSION COMPLETE                               │
│                                                                     │
│  Duration: 12:34          Falls Practiced: 5                       │
│  Average Technique Score: 78/100                                   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  PERFORMANCE OVER TIME                                      │   │
│  │  [Bar chart: 5 falls with scores]                          │   │
│  │  Fall 1: 65  |  Fall 2: 72  |  Fall 3: 81  |  ...          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                       │
│  │  BEST     │  │  NEEDS    │  │  KEY      │                       │
│  │  ATTEMPT  │  │  WORK     │  │  FRAME    │                       │
│  │  [image]  │  │  [image]  │  │  [image]  │                       │
│  │  Score:85 │  │  Score:65 │  │           │                       │
│  └───────────┘  └───────────┘  └───────────┘                       │
│                                                                     │
│  RECOMMENDATIONS FOR NEXT SESSION:                                 │
│  • Focus on keeping elbows bent during impact                     │
│  • Practice chin tuck timing - currently tucking too late         │
│  • Great improvement on knee positioning!                          │
│                                                                     │
│  [Return to Main Screen]           [Export Session Data]          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.6 Settings Panel

**Categories:**
1. **Camera**
   - Camera selection dropdown
   - Resolution selection (480p, 720p, 1080p)
   - Mirror video toggle

2. **Audio**
   - Enable/disable audio feedback
   - Voice selection (System TTS / Calm & Encouraging)
   - Volume slider

3. **Display**
   - Developer mode toggle (shows raw pose data)
   - Skeleton overlay style
   - Traffic light position

4. **Account** (if authenticated)
   - Supabase sync status
   - Session history

---

## 3. Technical Architecture

### 3.1 Framework Recommendation

**Decision Required: UI Framework**

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Stay with Gradio** | Fastest to iterate, Python-native, team familiarity | Limited customization, dark theme issues, component constraints | ✅ **Recommended for MVP** - Gradio 4.x has improved themes and custom CSS support |
| **Custom Web UI (FastAPI + React)** | Full control, modern UI, responsive design | Longer dev time, requires frontend expertise, more complexity | Consider for v3 if Gradio limitations become blockers |
| **Desktop Native (PyQt6)** | Best performance, native feel, offline-first | Steeper learning curve, less portable, harder to style | Not recommended - web-based is more flexible |
| **Electron + React** | Cross-platform, full web UI control, native feel | Heavy resource usage, complex packaging, overkill | Not recommended - adds unnecessary complexity |

**Recommendation:** Stay with Gradio for v2 MVP, but use Gradio 4.x features:
- Custom CSS themes (override dark theme → light professional theme)
- `gr.HTML()` for custom components
- `gr.State()` for complex state management
- `gr.Timer()` for periodic updates without generators
- Consider Gradio Lite for future if needed

### 3.2 Performance Optimizations

**Current Issue:** FPS drops and video lag

**Solutions:**
1. **Frame skipping:** Process every 2nd or 3rd frame for pose estimation
2. **Resolution scaling:** Run pose estimation on 320x240, display at higher res
3. **Async processing:** Move pose estimation to separate thread/process
4. **Model selection:** Use lighter RTMLib models for lower-end hardware
5. **Batching:** Accumulate frames for SiA detection (already using 72-frame buffer)

**Target Performance:**
- Video display: 30fps minimum
- Pose estimation: 15fps minimum
- Fall detection: 3-5fps (acceptable given buffer approach)
- Feedback latency: <500ms from detection to display

### 3.3 SiA Integration Requirements

**Current Status:** Partially integrated, weights need download

**v2 Requirements:**
- [ ] Automatic weight download on first run (with progress indicator)
- [ ] Graceful fallback if weights unavailable (show warning, disable fall detection)
- [ ] Fall detection confidence threshold tuning
- [ ] Per-fall technique scoring (evaluate form quality)
- [ ] Fall event recording with timestamp and frame snapshot

**API:**
```python
class SiADetector:
    def detect(frame, pose_keypoints) -> FallDetectionResult:
        """
        Returns:
            FallDetectionResult(
                detected: bool,
                confidence: float (0-1),
                action: str ('fall down', 'lying down', etc.),
                technique_score: float (0-100),
                key_frame: Optional[np.ndarray]  # NEW: Best frame for review
            )
        """
```

### 3.4 MLLM Feedback Integration

**Requirement:** Local multimodal LLM that runs on entry-level to prosumer GPU (GTX 1650 to RTX 3070)

**Recommended Models:**

| Model | VRAM | Quality | Speed | Notes |
|-------|------|---------|-------|-------|
| **Qwen2-VL-2B-Instruct** | ~4GB | Good | Fast | ✅ Best for GTX 1650, fits in 6GB VRAM |
| **LLaVA-1.6-7B** | ~8GB | Better | Medium | Good for RTX 3060+ |
| **Phi-3-Vision-128k** | ~6GB | Good | Fast | Microsoft model, efficient |
| **MiniCPM-V-2.6** | ~4GB | Good | Fast | Lightweight, good for CPU+GPU |

**Recommendation:** Start with **Qwen2-VL-2B-Instruct** for widest hardware support

**Integration Architecture:**
```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Pose Data   │────▶│              │────▶│  Coaching       │
│ + Key Frame │     │  MLLM        │     │  Feedback       │
│ + Context   │     │  (Local)     │     │  (Natural Lang) │
└─────────────┘     └──────────────┘     └─────────────────┘
```

**Prompt Template:**
```
You are a physical therapy coach helping an elderly patient practice safe falling techniques.

Current pose analysis:
- Elbow angles: {left_elbow}°, {right_elbow}°
- Knee angles: {left_knee}°, {right_knee}°
- Torso tilt: {torso_tilt}°

Fall detected: {yes/no}
Technique score: {score}/100

Based on the image and pose data, provide:
1. One brief encouragement or correction (1 sentence)
2. Specific improvement tip if needed (1 sentence)

Keep response under 30 words. Use simple, non-technical language.
```

**Fallback:** Keep rule-based feedback generator as backup when MLLM is unavailable

### 3.5 Data Persistence (Supabase)

**Tables Needed:**

```sql
-- Active Learning Sessions
CREATE TABLE active_learning_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    total_falls INTEGER DEFAULT 0,
    average_technique_score DECIMAL(5,2),
    best_technique_score DECIMAL(5,2),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fall Records
CREATE TABLE fall_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES active_learning_sessions(id),
    timestamp TIMESTAMPTZ NOT NULL,
    technique_score DECIMAL(5,2),
    feedback TEXT,
    pose_angles JSONB,
    key_frame_url TEXT,  -- Optional: store in Supabase Storage
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback History
CREATE TABLE feedback_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES active_learning_sessions(id),
    timestamp TIMESTAMPTZ NOT NULL,
    message TEXT,
    severity VARCHAR(20),
    pose_score DECIMAL(5,2),
    source VARCHAR(20) CHECK (source IN ('rule_based', 'mllm')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.6 WebSocket Reliability

**Current Issue:** Connection drops, slow WiFi problems

**Solutions:**
1. **Auto-reconnect:** Client-side reconnection with exponential backoff
2. **Heartbeat:** Ping/pong every 5 seconds to detect disconnection
3. **Local-only fallback:** Continue desktop session if mobile disconnects
4. **Connection quality indicator:** Show warning when latency >500ms
5. **Message queuing:** Buffer messages during brief disconnections

**Protocol Enhancement:**
```json
// Connection health message (every 5s)
{
    "type": "ping",
    "timestamp": "2026-02-05T10:00:00Z"
}

// Connection quality warning
{
    "type": "connection_quality",
    "status": "degraded",
    "latency_ms": 850,
    "message": "Slow connection detected. Mobile updates may be delayed."
}
```

---

## 4. Safety & Best Practices

### 4.1 Session Start Disclaimer

Display before first session (with "Don't show again" option):

```
⚠️ IMPORTANT SAFETY INFORMATION

This app helps practice safe falling techniques under supervision.

• Always practice on a padded surface (mat, carpet, grass)
• Have a spotter present during all practice sessions
• Stop immediately if you feel pain or discomfort
• This app is not a substitute for professional medical advice
• Consult your healthcare provider before starting fall training

[I Understand and Accept] [Cancel]
```

### 4.2 Session Limits (Recommended)

- **Soft limit:** Suggest 15-minute break after 20 minutes of continuous practice
- **Fall limit:** Suggest break after 10 consecutive falls
- **Fatigue detection:** If technique scores decline >20% over 5 falls, suggest rest

### 4.3 Emergency Information

- Optional: Display emergency contact (configurable in settings)
- Optional: Quick-access button to pause and show emergency info

---

## 5. Implementation Phases

### Phase 1: Core UI Overhaul (MVP)
**Focus:** Address v1 pain points, improve readability

- [ ] Light theme with professional color palette
- [ ] Large feedback banner (readable from distance)
- [ ] Improved QR code flow with session code fallback
- [ ] Clear session state indicators
- [ ] Video-dominant layout with overlays
- [ ] Basic settings panel (camera, audio)
- [ ] Session summary overlay

**Dependencies:** None (can start immediately)

### Phase 2: SiA Integration
**Focus:** Reliable fall detection with scoring

- [ ] Automatic weight download with progress
- [ ] Per-fall technique scoring
- [ ] Key frame capture on fall detection
- [ ] Fall count and score display
- [ ] Performance optimization for smooth video

**Dependencies:** SiA model weights, GPU testing

### Phase 3: MLLM Feedback
**Focus:** Natural language coaching feedback

- [ ] Local MLLM integration (Qwen2-VL-2B or similar)
- [ ] Prompt engineering for coaching feedback
- [ ] Fallback to rule-based when MLLM unavailable
- [ ] Audio TTS for feedback

**Dependencies:** MLLM selection, hardware testing

### Phase 4: Data Persistence
**Focus:** Session history and sync

- [ ] Supabase schema creation
- [ ] Session recording and upload
- [ ] Session history view
- [ ] Export functionality

**Dependencies:** Supabase access, authentication flow

### Phase 5: Polish & Accessibility
**Focus:** Production readiness

- [ ] Accessibility audit (contrast, screen reader)
- [ ] Performance profiling and optimization
- [ ] Error handling and edge cases
- [ ] Documentation and help system

**Dependencies:** User testing feedback

---

## 6. Open Questions

1. **Authentication:** Should desktop wizard require login, or allow anonymous sessions?
2. **Multi-device:** Can multiple mobile devices connect to one desktop session?
3. **Recording:** Should sessions be video-recorded for later review?
4. **Gamification:** Add points, achievements, or progress tracking?
5. **Offline sync:** Queue Supabase uploads for when connection restored?

---

## 7. Success Metrics

| Metric | Current (v1) | Target (v2) |
|--------|--------------|-------------|
| Feedback readability (10ft) | Poor | Good |
| QR code scan success | ~70% | >95% |
| Session state clarity | Confusing | Clear |
| Time to first session | ~2 min | <30 sec |
| Video FPS | Variable | 30fps stable |
| Technique score accuracy | N/A | >80% correlation with PT assessment |

---

## 8. Appendix

### A. Keyboard Shortcuts (Proposed)

| Shortcut | Action |
|----------|--------|
| Space | Start/Pause session |
| Escape | End session (with confirmation) |
| Q | Show/hide QR code |
| D | Toggle developer mode |
| F | Toggle fullscreen |
| S | Open settings |

### B. Audio Feedback Options

**System TTS:**
- Uses OS text-to-speech
- Fastest response, variable quality
- Works offline

**Calm/Encouraging Voice:**
- Pre-selected warm, slower voice
- Appropriate for older adults
- May require voice pack download

### C. Gradio 4.x Custom Theme Example

```python
import gradio as gr

safefall_theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="slate",
    neutral_hue="slate",
    font=gr.themes.GoogleFont("Inter"),
).set(
    body_background_fill="#F8FAFC",
    block_background_fill="#FFFFFF",
    block_title_text_color="#1E293B",
    block_label_text_color="#64748B",
    input_background_fill="#FFFFFF",
    button_primary_background_fill="#2563EB",
    button_primary_text_color="#FFFFFF",
)
```

---

*Document prepared based on user interview conducted February 5, 2026.*
