# Active Learning Mode - Product Requirements Document

This document captures the requirements and design decisions for the Active Learning Mode feature, based on stakeholder interviews conducted January 2026.

---

## Overview

Active Learning Mode enables real-time fall technique feedback through a desktop-mobile connection. A therapist operates the desktop wizard while the patient receives coaching feedback on their mobile device.

---

## Target Users

| User | Role | Interface |
|------|------|-----------|
| **Therapist/Caregiver** | Operates session, monitors patient, receives alerts | Desktop Wizard (Gradio) |
| **Older Adult Patient** | Practices fall techniques, receives feedback | Mobile App (Flutter) |

**Use Case**: Supervised practice sessions only. This is NOT a continuous fall monitor - Active Learning Mode only operates during explicit practice sessions for HIPAA/privacy compliance.

---

## Feature Requirements

### 1. Connection System

#### QR Code + WebSocket (MVP - Priority 1)
- Desktop displays QR code containing WebSocket URL and session ID
- Mobile scans QR to establish connection
- **Phase 1**: Local WiFi (same network required)
- **Phase 2**: Cloud relay via Firebase Realtime Database (under UCF's Google BAA)

#### Connection Handling
- On disconnect: Show alert on mobile with manual retry button
- No auto-reconnect (user should be aware of connection state)

### 2. Fall Detection

#### SiA Model Integration
- Use Eva's SiA (Skeleton-in-Action) model from `sia_model/` directory
- Detect ALL falls during practice session (no distinction between "safe" vs "dangerous" during practice)
- ML model classifies fall type; therapist can verify/correct if needed
- Falls outside Active Learning Mode are not monitored (privacy/HIPAA)

#### Dangerous Fall Alerts
- When concerning fall detected: Alert therapist on desktop only
- Visual and/or audio alert on desktop wizard
- Therapist handles situation directly (no automated emergency contacts)

### 3. Pose Estimation

#### RTMLib Integration
- Extract body keypoints for technique analysis
- Calculate joint angles for feedback generation
- Draw skeleton overlay on desktop video feed
- **Status**: Not yet implemented (placeholder code exists)

### 4. Feedback System

#### Real-time Feedback
- Rule-based feedback for immediate coaching tips
- Feedback interval: configurable (currently 2 seconds)

#### LLM-Powered Analysis (Future)
- **Model**: Ovis 2.5 (open-source multimodal)
- **Deployment**: Desktop GPU (NVIDIA 8GB+ VRAM recommended)
- **Fallback**: Show warning for CPU inference (slower, ~30-60s per analysis)
- **Latency**: 5-15 seconds acceptable for detailed fall analysis
- User sees loading indicator during analysis

### 5. Session Management

#### Session Lifecycle
- Therapist starts/stops session from desktop
- Session stats tracked: duration, falls practiced, feedback count
- **Recording**: Real-time only, no video storage (HIPAA compliance)
- Only metadata and feedback logs retained

#### Session Data
- Session ID, timestamps
- Fall events with technique scores
- Feedback messages sent
- No video frames stored

---

## User Interface Requirements

### Mobile App (Patient View)

#### Accessibility (Critical for Older Adults)
- Large text and buttons (easily tappable)
- Voice feedback via text-to-speech
- High contrast mode support
- Intuitive and intentional navigation

#### Feedback Display
- Visual indicators (colors/icons)
- Simplified scores (not raw 0-100 numbers)
- Word labels: "Good", "Needs Work", "Excellent"
- Combined approach: visual + scores + words, but not overwhelming

#### States
1. **Idle** - Instructions + "Scan QR Code" button
2. **Scanning** - Camera view with QR overlay
3. **Connecting** - Loading indicator
4. **Connected** - Live feedback, session stats
5. **Error** - Error message with retry button

### Desktop Wizard (Therapist View)

#### Current Implementation
- Gradio web UI (prototype/research setting)
- Camera feed with pose overlay
- QR code display
- Session controls (Start/Stop)
- Pose analysis panel
- Feedback log

#### Future Consideration
- Electron app for polished native feel (if needed for production)
- Packaged executable for non-technical therapists

#### Hardware Requirements
- Webcam (built-in or external)
- NVIDIA GPU recommended for ML inference (Ovis 2.5)
- M1/M2/M3 Mac works for basic testing (CPU mode)

---

## Technical Architecture

### Infrastructure

| Component | Technology | Notes |
|-----------|------------|-------|
| Mobile App | Flutter + Riverpod | Existing codebase |
| Desktop Wizard | Python + Gradio | Prototype UI |
| WebSocket (Local) | Python asyncio | Port 8765 |
| WebSocket (Cloud) | Firebase Realtime DB | Under UCF Google BAA |
| Pose Estimation | RTMLib | Wholebody model |
| Fall Detection | SiA | Eva's implementation in `sia_model/` |
| LLM Feedback | Ovis 2.5 | Desktop GPU inference |

### HIPAA Compliance

- Video streams exist only within active session
- No video recording or cloud video transfer
- Only metadata/feedback through cloud relay
- Firebase Realtime DB under UCF's Google BAA
- Session data: stats and feedback logs only

### Data Flow

```
Camera → Pose Estimation → Fall Detection → Feedback Generation
                                    ↓
                            WebSocket Server
                                    ↓
                            Mobile App Display
```

---

## Implementation Phases

### Phase 1: QR + WebSocket (Current Priority)
- [ ] Desktop: WebSocket server working and tested
- [ ] Desktop: QR code generation with correct URL
- [ ] Mobile: QR scanner working with camera permissions
- [ ] Mobile: WebSocket client connects and receives messages
- [ ] Mobile: Basic feedback display
- [ ] Test on Android device with local WiFi

### Phase 2: Pose Estimation
- [ ] Integrate RTMLib in desktop wizard
- [ ] Display skeleton overlay on video feed
- [ ] Calculate joint angles
- [ ] Send pose data with feedback messages

### Phase 3: Fall Detection
- [ ] Integrate Eva's SiA model from `sia_model/`
- [ ] Detect falls during practice session
- [ ] Generate technique scores
- [ ] Send fall events to mobile

### Phase 4: Enhanced Feedback
- [ ] Integrate Ovis 2.5 for LLM feedback
- [ ] Add GPU/CPU detection and fallback
- [ ] Implement loading states for analysis
- [ ] Add voice feedback (TTS) on mobile

### Phase 5: Cloud Relay
- [ ] Set up Firebase Realtime Database
- [ ] Verify HIPAA compliance under UCF BAA
- [ ] Implement cloud WebSocket relay
- [ ] Test across different networks

### Phase 6: Polish & Accessibility
- [ ] Mobile accessibility audit (large text, contrast)
- [ ] Voice feedback implementation
- [ ] Desktop packaging (if needed)
- [ ] User study preparation (Spring 2026)

---

## Testing Strategy

### Manual QA
- Team members perform falls on camera
- Test all connection states
- Test accessibility features

### Video Dataset
- Record test videos for automated accuracy testing
- Regression testing for ML model changes

### User Study
- Planned for Spring 2026
- Recruit older adult participants
- Usability and accuracy evaluation

---

## SiA Model Integration Details

Eva's SiA implementation is in `sia_model/` with the following structure:

### Key Components
- `fall_detection_processor.py` - Main processor class (ready to use)
- `sia/sia.py` - Core SiA model architecture
- `sia/sia_vision.py` - Vision encoder
- `sia/sia_text.py` - Text encoder for action labels

### FallDetectionProcessor Class
```python
from fall_detection_processor import FallDetectionProcessor
processor = FallDetectionProcessor(model_path='weights/.../avak_b16_10.pt')
result = processor.process_video(video_path, output_json_path)
```

### Actions Detected
- `fall down` - Primary fall detection
- `lying down` - Post-fall state
- `sit down` - Transition action
- `get up` - Recovery action

### Model Weights
Download required (~200MB):
```bash
cd sia_model
mkdir -p weights/avak_aws_stats_flt_b16_txtaug_txtlora/
wget -P weights/avak_aws_stats_flt_b16_txtaug_txtlora/ \
  https://github.com/ppriyank/SiA_OV-AR/releases/download/weights/avak_b16_10.pt
```

### Real-time Adaptation Needed
Current implementation processes full videos. For Active Learning Mode, need to:
1. Modify to accept streaming frames instead of video file
2. Maintain rolling 72-frame buffer (~2.4 seconds at 30fps)
3. Return detection results per-frame or per-buffer cycle

### Hardware Requirements
- CUDA GPU recommended (falls back to CPU)
- ~4GB VRAM for inference
- CPU mode significantly slower

---

## Open Questions

1. **Firebase BAA**: Need to confirm Firebase is covered under UCF's existing Google BAA, or if additional paperwork is needed
2. **Ovis 2.5 Hardware**: Confirm minimum GPU specs for acceptable inference speed
3. **SiA Real-time**: Validate real-time frame processing performance (target: 30fps input, detection every ~2 seconds)

---

## Team Responsibilities

| Area | Owner |
|------|-------|
| Mobile App UI | Thu Do |
| Desktop Wizard | TBD |
| SiA Integration | Eva Lopez |
| Database/Firebase | Diego Quinones |
| Code Review/QA | Thien Ha Le |

---

## References

- [ACTIVE_LEARNING_MODE.md](./ACTIVE_LEARNING_MODE.md) - Technical implementation documentation
- `sia_model/` - Eva's SiA fall detection code
- `active_learning_engine/` - Desktop wizard implementation
- `safefall_coach_mobile/lib/screens/active_learning_screen.dart` - Mobile screen

---

*Document created: January 2026*
*Last updated: January 2026*
