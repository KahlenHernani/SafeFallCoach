# SafeFall Active Learning Wizard

Desktop application for providing real-time feedback on fall techniques using pose estimation and fall detection ML models.

## Overview

The Active Learning Wizard is a Gradio-based Python application that:

- Captures video from your webcam
- Performs real-time pose estimation using RTMLib
- Detects falls using the SiA (Skeleton-in-Action) model
- Generates coaching feedback based on body positioning
- Communicates with the SafeFall Coach mobile app via WebSocket

## Architecture

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
                          │ Local Network
                          ▼
                   Mobile App (Flutter)
```

## Installation

### Prerequisites

- Python 3.9 or higher
- Webcam
- Both desktop and mobile devices on the same local network

### Setup

1. Navigate to the wizard directory:
   ```bash
   cd active_learning_engine
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Install CUDA-enabled PyTorch for GPU acceleration:
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```

## Usage

1. Start the wizard:
   ```bash
   python app.py
   ```

2. Open the Gradio interface in your browser (usually http://localhost:7860)

3. Click "Start Session" to begin

4. Scan the QR code with the SafeFall Coach mobile app

5. Position yourself in front of the camera and practice fall techniques

6. Receive real-time feedback on your mobile device

7. Click "Stop Session" when done to see your summary

## Components

### Models (`models/`)

- **`sia_detector.py`** - SiA fall detection wrapper (integrates with Eva's work)
- **`pose_estimator.py`** - RTMLib pose estimation with skeleton drawing
- **`feedback_generator.py`** - Rule-based and LLM-based coaching feedback

### Services (`services/`)

- **`websocket_server.py`** - AsyncIO WebSocket server for mobile communication
- **`qr_generator.py`** - QR code generation with session info
- **`session_manager.py`** - Session state and statistics management

### Utils (`utils/`)

- **`camera.py`** - Threaded camera capture with frame rate control

## WebSocket Protocol

### Message Types

**Feedback Message (Server → Mobile)**
```json
{
  "type": "feedback",
  "timestamp": "2024-01-26T15:00:05Z",
  "message": "Good form! Keep your chin tucked.",
  "severity": "info",
  "pose_score": 85
}
```

**Fall Event (Server → Mobile)**
```json
{
  "type": "fall_event",
  "timestamp": "2024-01-26T15:00:10Z",
  "technique_score": 72,
  "feedback": "Try to roll more on your side next time."
}
```

**Session Status (Server → Mobile)**
```json
{
  "type": "session_status",
  "status": "active",
  "duration_seconds": 120,
  "falls_practiced": 3
}
```

## Configuration

### Camera Settings

Edit `app.py` to change camera settings:

```python
self.camera = CameraCapture(
    camera_index=0,      # Camera device index
    width=640,           # Frame width
    height=480,          # Frame height
    fps=30               # Target FPS
)
```

### WebSocket Port

Default port is 8765. To change:

```python
self.ws_server = WebSocketServer(port=YOUR_PORT)
self.qr_generator = QRGenerator(ws_port=YOUR_PORT)
```

## Integrating ML Models

### SiA Fall Detection

The `SiADetector` class is a placeholder for integration with Eva's SiA implementation. To integrate:

1. Import the SiA model from the groundingdino submodule
2. Update `models/sia_detector.py` to load and run the model
3. Return proper `FallDetectionResult` with detection status and confidence

### RTMLib Pose Estimation

RTMLib should work out of the box. If you encounter issues:

1. Ensure rtmlib is installed: `pip install rtmlib`
2. Check that model weights are downloaded automatically
3. For GPU acceleration, ensure CUDA is properly configured

### Multimodal LLM Feedback

The `FeedbackGenerator` currently uses rule-based feedback. To add LLM:

1. Install the desired LLM library (e.g., transformers)
2. Update `models/feedback_generator.py` to load and query the model
3. Pass frames to the LLM for more nuanced feedback

## Troubleshooting

### Camera not working

- Check that your webcam is connected and not in use by another application
- Try a different camera index (0, 1, 2, etc.)
- On macOS, grant camera permissions to Terminal/Python

### Mobile app can't connect

- Ensure both devices are on the same WiFi network
- Check that firewall isn't blocking port 8765
- Try using the IP address displayed in the QR code directly

### Pose estimation slow

- Reduce camera resolution
- Use a smaller RTMLib model (rtmpose-s instead of rtmpose-m)
- Enable GPU acceleration if available

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

Follow PEP 8 guidelines. Format with:

```bash
black .
isort .
```

## License

Part of the SafeFall Coach project. See main repository for license information.
