# Active Learning Mode - Implementation Documentation

This document describes the Active Learning Mode feature added to SafeFall Coach, enabling real-time fall technique feedback through a desktop-mobile connection.

## Overview

Active Learning Mode allows users to practice fall techniques in front of a camera while receiving real-time coaching feedback on their mobile device. The system consists of:

1. **Desktop Wizard** - A Python/Gradio application running ML models for pose estimation and fall detection
2. **Mobile App Screen** - A Flutter screen that connects via QR code and displays feedback

```
┌─────────────────────────────────────────────────────────────┐
│                    DESKTOP WIZARD (Gradio)                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────────┐  │
│  │  SiA    │  │ RTMLib  │  │Grounding│  │ Multimodal LLM│  │
│  │ (fall)  │  │ (pose)  │  │  DINO   │  │  (feedback)   │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  └───────┬───────┘  │
│       └────────────┴───────────┴────────────────┘          │
│                         │                                   │
│              ┌──────────▼──────────┐                       │
│              │   WebSocket Server  │◄── QR Code contains   │
│              │   (localhost:8765)  │    ws://IP:8765       │
│              └──────────┬──────────┘                       │
└─────────────────────────┼───────────────────────────────────┘
                          │ Local Network (WiFi)
┌─────────────────────────┼───────────────────────────────────┐
│  MOBILE APP             │                                   │
│              ┌──────────▼──────────┐                       │
│              │  WebSocket Client   │                       │
│              └──────────┬──────────┘                       │
│                         │                                   │
│              ┌──────────▼──────────┐                       │
│              │ Active Learning     │                       │
│              │ Screen (feedback    │                       │
│              │ display, session    │                       │
│              │ status, coaching)   │                       │
│              └─────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Added/Modified

### Mobile App (Flutter)

| File | Type | Description |
|------|------|-------------|
| `safefall_coach_mobile/pubspec.yaml` | Modified | Added `mobile_scanner` and `web_socket_channel` dependencies |
| `safefall_coach_mobile/lib/services/websocket_service.dart` | New | WebSocket client for communicating with desktop wizard |
| `safefall_coach_mobile/lib/providers/active_session_provider.dart` | New | Riverpod state management for active learning sessions |
| `safefall_coach_mobile/lib/widgets/feedback_card.dart` | New | UI widgets for displaying feedback messages |
| `safefall_coach_mobile/lib/screens/active_learning_screen.dart` | New | Main active learning screen with QR scanner |
| `safefall_coach_mobile/lib/screens/main_screen.dart` | Modified | Wired up the "Active" tab in bottom navigation |

### Desktop Wizard (Python)

| File | Description |
|------|-------------|
| `active_learning_engine/app.py` | Main Gradio application entry point |
| `active_learning_engine/requirements.txt` | Python dependencies |
| `active_learning_engine/README.md` | Setup and usage documentation |
| `active_learning_engine/models/__init__.py` | Models package init |
| `active_learning_engine/models/sia_detector.py` | SiA fall detection wrapper (placeholder for Eva's model) |
| `active_learning_engine/models/pose_estimator.py` | RTMLib pose estimation with skeleton drawing |
| `active_learning_engine/models/feedback_generator.py` | Rule-based coaching feedback generator |
| `active_learning_engine/services/__init__.py` | Services package init |
| `active_learning_engine/services/websocket_server.py` | AsyncIO WebSocket server for mobile communication |
| `active_learning_engine/services/qr_generator.py` | QR code generation with session info |
| `active_learning_engine/services/session_manager.py` | Session state and statistics tracking |
| `active_learning_engine/utils/__init__.py` | Utils package init |
| `active_learning_engine/utils/camera.py` | Threaded camera capture utility |

---

## How It Works

### Connection Flow

1. User starts the Desktop Wizard (`python app.py`)
2. Wizard displays a QR code containing WebSocket URL and session ID
3. User opens SafeFall Coach app and navigates to "Active" tab
4. User scans QR code with mobile app
5. Mobile app connects to desktop via WebSocket
6. Real-time feedback streams from desktop to mobile

### Data Flow

1. **Camera Capture** → Desktop captures video frames at 30fps
2. **Pose Estimation** → RTMLib extracts body keypoints from each frame
3. **Fall Detection** → SiA model detects if a fall occurred
4. **Feedback Generation** → Based on pose angles and fall events, coaching feedback is generated
5. **WebSocket Broadcast** → Feedback is sent to all connected mobile clients
6. **Mobile Display** → App shows feedback cards with scores and coaching tips

---

## WebSocket Protocol

Messages are JSON objects sent from server to mobile client.

### Feedback Message
```json
{
  "type": "feedback",
  "timestamp": "2024-01-26T15:00:05Z",
  "message": "Good form! Keep your chin tucked.",
  "severity": "info",
  "pose_score": 85
}
```
- `severity`: `"info"` | `"warning"` | `"success"`
- `pose_score`: 0-100 indicating current form quality

### Fall Event
```json
{
  "type": "fall_event",
  "timestamp": "2024-01-26T15:00:10Z",
  "technique_score": 72,
  "feedback": "Try to roll more on your side next time."
}
```

### Session Status
```json
{
  "type": "session_status",
  "status": "active",
  "duration_seconds": 120,
  "falls_practiced": 3
}
```
- `status`: `"active"` | `"paused"` | `"ended"`

### QR Code Content
```json
{
  "type": "safefall_active_session",
  "version": 1,
  "ws_url": "ws://192.168.1.100:8765",
  "session_id": "abc12345",
  "created_at": "2024-01-26T15:00:00Z"
}
```

---

## Mobile App Components

### `websocket_service.dart`

Handles WebSocket connection and message parsing:
- `WsConnectionState` enum: `disconnected`, `connecting`, `connected`, `error`
- `WsMessage` base class with subclasses:
  - `FeedbackMessage` - coaching tips
  - `FallEventMessage` - fall detection events
  - `SessionStatusMessage` - session updates
- `WebSocketService` class manages connection lifecycle

### `active_session_provider.dart`

Riverpod state management:
- `ActiveSessionState` - holds connection state, feedback history, stats
- `ActiveSessionNotifier` - manages state transitions and WebSocket events
- Providers:
  - `activeSessionProvider` - main session state
  - `latestFeedbackProvider` - most recent feedback
  - `feedbackMessagesProvider` - filtered feedback list
  - `fallEventsProvider` - filtered fall events

### `active_learning_screen.dart`

UI with multiple states:
1. **Idle** - "Scan QR to Connect" button with instructions
2. **Scanning** - Camera view with QR scanner overlay
3. **Connecting** - Loading indicator
4. **Connected** - Live feedback display with stats
5. **Error** - Error message with retry option

### `feedback_card.dart`

Display widgets:
- `FeedbackCard` - compact card for feedback history
- `LargeFeedbackDisplay` - prominent display for latest feedback

---

## Desktop Wizard Components

### `app.py`

Main Gradio application:
- Initializes all ML models and services
- Creates Gradio UI with video feed, QR code, and controls
- Coordinates frame processing pipeline

### `models/pose_estimator.py`

RTMLib integration:
- `PoseEstimator` class wraps RTMLib Wholebody model
- `estimate()` returns keypoints for detected people
- `draw_pose()` overlays skeleton on video frame
- `calculate_angles()` computes joint angles for technique analysis

### `models/sia_detector.py`

Fall detection (placeholder):
- `SiADetector` class wraps SiA model
- `detect()` analyzes frame for fall events
- **TODO**: Integrate Eva's actual SiA implementation

### `models/feedback_generator.py`

Coaching feedback:
- Rule-based analysis of pose angles
- Checks for: chin tucked, arms bent, knees bent, torso alignment
- Generates appropriate coaching messages
- Has cooldown to avoid spam

### `services/websocket_server.py`

AsyncIO WebSocket server:
- Runs in background thread (non-blocking)
- Broadcasts messages to all connected clients
- Tracks session duration and fall count

### `services/qr_generator.py`

QR code generation:
- Auto-detects local IP address
- Generates unique session ID
- Creates QR code image for Gradio display

### `services/session_manager.py`

Session lifecycle:
- Tracks session state (idle, active, paused, ended)
- Records fall events with technique scores
- Calculates session statistics

---

## Setup Instructions

### Mobile App

1. Navigate to Flutter project:
   ```bash
   cd safefall_coach_mobile
   ```

2. Get dependencies:
   ```bash
   flutter pub get
   ```

3. Run the app:
   ```bash
   flutter run
   ```

### Desktop Wizard

1. Navigate to wizard directory:
   ```bash
   cd active_learning_engine
   ```

2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the wizard:
   ```bash
   python app.py
   ```

5. Open browser to `http://localhost:7860`

---

## Testing the Connection

1. Start desktop wizard and ensure QR code is displayed
2. Ensure both devices are on the **same WiFi network**
3. Open SafeFall Coach app → tap "Active" tab
4. Tap "Scan QR Code to Connect"
5. Point camera at QR code on desktop screen
6. Verify "Connected" status appears on mobile
7. Practice a fall in front of the camera
8. Verify feedback appears on mobile device

---

## Next Steps / TODOs

1. **Integrate SiA Model** - Connect Eva's fall detection implementation in `models/sia_detector.py`
2. **Add Multimodal LLM** - Enhance feedback with vision-language model in `models/feedback_generator.py`
3. **Session Recording** - Save session data to Supabase for progress tracking
4. **Post-Session Summary** - Display detailed analysis after session ends
5. **Technique Library** - Add specific fall technique detection (forward roll, side fall, etc.)

---

## Troubleshooting

### Mobile can't connect
- Verify both devices are on same WiFi network
- Check firewall isn't blocking port 8765
- Try the WebSocket URL manually in browser

### Camera not working on desktop
- Check webcam is connected and not in use
- Try different camera index in `app.py`
- On macOS, grant camera permission to Terminal

### No feedback appearing
- Check WebSocket connection is established
- Verify pose estimation is detecting a person
- Check console for any error messages

---

## Authors

Implementation by Claude Code, January 2024.
Part of SafeFall Coach Senior Design Project.
