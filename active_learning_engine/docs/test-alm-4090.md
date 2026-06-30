# Testing SafeFall Coach App on Windows 11 RTX 4090 System

## Context

This guide explains how to test the **entire SafeFall Coach app** on a Windows 11 PC with RTX 4090 GPU (24GB VRAM) and 32GB RAM.

**Current Architecture:**
- **Frontend:** Flutter mobile app (cross-platform: Android, iOS, Windows desktop)
- **Backend:** Supabase cloud (PostgreSQL + Auth) - already hosted, no local setup needed
- **AI/ML Models:** 3 Python components (Active Learning Wizard, SiA detector, Skeletal Overlay)

**Key Finding:** Docker is **planned but not yet implemented** for the ML components. For testing purposes, **native Windows setup is simpler and faster**.

---

## Why Native Windows Setup is Simplest & Fastest

### 1. **Direct GPU Access**
- **Native:** PyTorch with CUDA talks directly to RTX 4090 → Zero overhead
- **Docker:** Requires NVIDIA Container Toolkit, GPU passthrough configuration, potential VRAM allocation issues
- **Verdict:** Native is 10-15% faster for real-time inference (no virtualization layer)

### 2. **Webcam Access**
- **Native:** Windows Camera API → Python OpenCV → Works immediately
- **Docker:** Complex passthrough (requires custom streaming script or Linux-only device mounting)
- **Verdict:** Native setup takes 0 minutes, Docker webcam hybrid takes 1-2 hours to configure

### 3. **Flutter Development**
- **Native:** Hot reload works, emulator/device access native, full IDE support
- **Docker:** Hot reload broken, device access requires USB passthrough, IDE integration fails
- **Verdict:** Flutter explicitly should NOT be containerized (per docker-plan.md §9)

### 4. **Setup Time**
- **Native:** 15-20 minutes (install Python, create venv, pip install, run)
- **Docker:** 45-90 minutes (install Docker Desktop, build images, configure GPU, setup volumes, debug issues)
- **Verdict:** Native is 3-4x faster for initial testing

### 5. **Debugging**
- **Native:** Full Python debugger, stack traces point to actual files, `nvidia-smi` shows exact usage
- **Docker:** Container logs, need to exec into containers, volume mount path differences
- **Verdict:** Native debugging is more straightforward

### 6. **When Docker DOES Make Sense**
Docker becomes valuable when:
- Deploying to production (reproducible environment)
- Onboarding new team members (one-command setup)
- Managing multiple CUDA versions
- Batch processing videos (SiA + Skeletal Overlay pipeline)
- Running on multiple machines (eliminate "works on my machine")

**For testing on a single Windows PC:** Native wins on simplicity and speed.

---

## Docker Requirements by Component

| Component | Docker Needed? | Rationale |
|-----------|----------------|-----------|
| **Flutter Mobile App** | ❌ **NO** | Must run natively (hot reload, device access, IDE) |
| **Supabase Backend** | ❌ **NO** | Cloud-hosted (already running remotely) |
| **PostgreSQL (Local)** | ⚠️ **Optional** | Planned for HIPAA-safe dev, not required for testing |
| **Active Learning Wizard** | ⚠️ **Optional** | Planned but not implemented; native is simpler for testing |
| **SiA Fall Detection** | ⚠️ **Optional** | Planned but not implemented; native works fine |
| **Skeletal Overlay** | ⚠️ **Optional** | Planned but not implemented; native works fine |

**Summary:** Docker is **not required** to test the app. All components can run natively on Windows 11.

---

## Recommended Testing Setup (Native Windows)

### Architecture
```
[Windows 11 PC - RTX 4090]
├── Flutter Desktop App (native)
│   ├── Connects to Supabase cloud (HTTPS)
│   └── Connects to Active Learning Wizard via WebSocket (localhost:8765)
│
├── Active Learning Wizard (Python - native venv)
│   ├── Gradio UI: http://localhost:7860
│   ├── WebSocket Server: ws://localhost:8765
│   ├── RTMLib (pose estimation)
│   ├── SiA (fall detection)
│   └── Gemini API or Ovis2.5-2B (feedback generation)
│
├── Supabase Backend (cloud - no local setup)
│   ├── PostgreSQL 15 (auth.users, public.users, falls, tutorials, etc.)
│   └── Authentication (email/password, RLS policies)
│
└── Optional: SiA + Skeletal Overlay (Python - separate venv)
    ├── Batch video processing
    └── Educational content generation
```

---

## Step-by-Step Testing Instructions

### Phase 1: Prerequisites (5 minutes)

**Install required software:**

1. **Python 3.10+** - [python.org/downloads](https://www.python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation
   - Verify: `python --version` (should show 3.10 or higher)

2. **Git** - [git-scm.com/download/win](https://git-scm.com/download/win)
   - Use default options
   - Verify: `git --version`

3. **CUDA Toolkit 12.x** - [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads)
   - RTX 4090 supports CUDA 12.x (latest)
   - Verify: `nvidia-smi` (should show CUDA Version 12.x)

4. **Flutter SDK** (for mobile app testing) - [flutter.dev/docs/get-started/install/windows](https://flutter.dev/docs/get-started/install/windows)
   - Download Flutter SDK, extract to `C:\flutter`
   - Add to PATH: `C:\flutter\bin`
   - Run: `flutter doctor` (installs dependencies)
   - Install Visual Studio Build Tools if prompted

5. **Visual Studio Code** (recommended IDE)
   - Install Flutter + Dart extensions

---

### Phase 2: Repository Setup (2 minutes)

```powershell
# Open PowerShell
cd C:\Users\YourUsername\Documents

# Clone repository
git clone https://github.com/Eva-M-Lopez/SeniorDesign1.git
cd SeniorDesign1

# Check repository status
git status
git log --oneline -5
```

---

### Phase 3: Active Learning Wizard Setup (10-15 minutes)

**3.1. Create Python Virtual Environment**

```powershell
# Navigate to project root
cd C:\Users\YourUsername\Documents\SeniorDesign1

# Create virtual environment
python -m venv venv_windows

# Activate virtual environment (IMPORTANT: Do this every time you open new terminal)
venv_windows\Scripts\activate

# You should see (venv_windows) in your prompt
```

**3.2. Install PyTorch with CUDA Support**

```powershell
# Install PyTorch with CUDA 12.1 (check your CUDA version with nvidia-smi)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

**3.3. Install Active Learning Wizard Dependencies**

```powershell
# Install all Python dependencies
pip install -r active_learning_engine/requirements.txt

# OPTIONAL but RECOMMENDED: Install flash-attention for 2-3x faster Ovis inference
# This compiles from source (takes 5-10 minutes)
pip install flash-attn --no-build-isolation
```

**3.4. Verify GPU Setup**

```powershell
# Test CUDA is available
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')"

# Expected output:
# CUDA available: True
# GPU: NVIDIA GeForce RTX 4090
```

**3.5. Configure Environment Variables (Optional)**

If using Gemini API for feedback (current implementation):

```powershell
# Create .env file in active_learning_engine/
cd active_learning_engine
notepad .env

# Add:
GOOGLE_API_KEY=your_gemini_api_key_here
```

**Note:** Ovis2.5-2B (local model) is planned but not yet implemented. Current implementation uses Gemini API (free tier).

---

### Phase 4: Run Active Learning Wizard (2 minutes)

```powershell
# Navigate to Active Learning Wizard directory
cd C:\Users\YourUsername\Documents\SeniorDesign1\active_learning_engine

# Activate virtual environment if not already active
..\venv_windows\Scripts\activate

# Run the app
python app.py
```

**First Run:**
- Models will auto-download from Hugging Face (~4GB total, takes 1-2 minutes)
- Cache location: `C:\Users\YourUsername\.cache\huggingface\`
- Subsequent runs start instantly

**Expected Output:**
```
Loading RTMLib model...
Loading SiA model...
Starting Gradio server...
Running on local URL:  http://127.0.0.1:7860
Running on local URL:  http://0.0.0.0:7860
WebSocket server started on port 8765
```

**Access the App:**
- Open browser: http://127.0.0.1:7860
- Grant webcam access when prompted

**Monitor GPU Usage:**
- Open second PowerShell window: `nvidia-smi -l 1` (updates every 1 second)
- Expected VRAM: ~2.5GB baseline (RTMLib + SiA), ~10.5GB when Ovis loads (on fall detection)

---

### Phase 5: Flutter Mobile App Setup (10 minutes)

**5.1. Configure Environment**

```powershell
# Navigate to Flutter project
cd C:\Users\YourUsername\Documents\SeniorDesign1\safefall_coach_mobile

# Copy environment template (if it doesn't exist)
# Note: .env file already exists with Supabase credentials

# Verify .env file exists and has valid credentials
notepad .env
```

**Contents should include:**
```
SUPABASE_URL=https://kmupfezhcyjlqdkuubfe.supabase.co
SUPABASE_ANON_KEY=eyJhb...your-anon-key
```

**5.2. Generate Environment Configuration**

```powershell
# Get Flutter dependencies
flutter pub get

# Generate env.g.dart from .env file
dart run build_runner build --delete-conflicting-outputs
```

**5.3. Run Flutter App**

**Option A: Windows Desktop App**
```powershell
# Run on Windows desktop
flutter run -d windows
```

**Option B: Android Emulator** (if Android SDK installed)
```powershell
# List available devices
flutter devices

# Run on emulator
flutter run -d emulator-5554
```

**Option C: Physical Android/iOS Device**
```powershell
# Connect device via USB, enable USB debugging
flutter devices
flutter run
```

**Expected Behavior:**
- App launches to splash screen → Welcome screen → User selection → Sign in/Sign up
- Can create account, log in
- Dashboard appears after authentication
- Active Learning tab shows QR code to connect to Active Learning Wizard

---

### Phase 6: End-to-End Testing (5 minutes)

**6.1. Test Active Learning Wizard Integration**

1. **Start Active Learning Wizard** (from Phase 4)
   - Open http://127.0.0.1:7860 in browser
   - QR code displayed on screen

2. **Connect Flutter App**
   - Navigate to Active Learning tab in mobile app
   - Scan QR code (or manually enter session ID)
   - WebSocket connection established

3. **Test Real-Time Feedback**
   - Perform practice fall in front of webcam
   - Pose estimation overlay appears in Gradio UI
   - Fall detection triggers after ~72 frames
   - AI feedback generated (Gemini or Ovis)
   - Feedback appears in Flutter mobile app

**6.2. Test User Flows**

- **Sign Up:** Create new account with email/password
- **Sign In:** Log in with existing account
- **Dashboard:** View user dashboard, navigation
- **Tutorials:** Browse educational content
- **Active Learning:** Real-time coaching session
- **Profile:** View/edit user profile

**6.3. Monitor Performance**

Open second terminal for GPU monitoring:
```powershell
# Watch GPU usage in real-time
nvidia-smi -l 1
```

**RTX 4090 Expected VRAM Usage:**
- **Baseline:** ~2.5GB (RTMLib + SiA in persistent mode)
- **Peak:** ~10.5GB (when Ovis2.5-2B loads for feedback generation)
- **Persistent Mode:** ~10.5GB continuous (if configured, RTX 4090 has plenty of headroom)

**Performance Targets:**
- Pose estimation: 30+ FPS
- Fall detection latency: <100ms after buffer fills
- AI feedback generation: 1-3 seconds
- WebSocket latency: <50ms

---

### Phase 7: Optional - Batch Video Processing (SiA + Skeletal Overlay)

**7.1. Test SiA Fall Detection**

```powershell
# Activate virtual environment
cd C:\Users\YourUsername\Documents\SeniorDesign1
venv_windows\Scripts\activate

# Run SiA demo on test video
cd sia_model
python demo.py -i ..\sidefall-1.mp4 -o output\fall_detection.json
```

**Expected Output:**
- JSON file with fall timestamps
- Fall events: 'fall down', 'lying down', 'get up', etc.

**7.2. Test Skeletal Overlay Generator**

```powershell
# Run overlay test
cd ..\skeletal_overlay
python test_overlay.py -i ..\sidefall-1.mp4 -o output\overlay_result.mp4

# Run full pipeline (fall detection + overlay)
python pipeline.py -i ..\sidefall-1.mp4 -o output\
```

**Expected Output:**
- Video with skeletal pose overlay
- Fall events annotated
- Educational content ready for mobile app

---

## Troubleshooting

### Issue: "CUDA out of memory"
**Unlikely with RTX 4090 (24GB), but if it happens:**
- Close other GPU applications (Chrome with hardware acceleration, games)
- Restart Active Learning Wizard
- Check GPU usage: `nvidia-smi`

### Issue: "Module not found" errors
```powershell
# Make sure virtual environment is activated
venv_windows\Scripts\activate

# Reinstall dependencies
pip install -r active_learning_engine/requirements.txt
```

### Issue: "WebSocket connection failed"
- Verify Active Learning Wizard is running (`python app.py`)
- Check port 8765 is not blocked by firewall
- Use `ws://127.0.0.1:8765` instead of `localhost`

### Issue: Flutter build errors
```powershell
# Clean and rebuild
flutter clean
flutter pub get
dart run build_runner build --delete-conflicting-outputs
flutter run
```

### Issue: Slow Ovis inference
- Install flash-attention: `pip install flash-attn --no-build-isolation`
- Verify GPU usage during inference: `nvidia-smi`
- Check VRAM usage (should be ~10.5GB during Ovis inference)

---

## Performance Validation

### Expected Metrics (RTX 4090)

| Metric | Target | Actual |
|--------|--------|--------|
| **Pose Estimation FPS** | 30+ | ___ |
| **Fall Detection Latency** | <100ms | ___ |
| **AI Feedback Generation** | 1-3s | ___ |
| **VRAM Usage (Baseline)** | ~2.5GB | ___ |
| **VRAM Usage (Peak)** | ~10.5GB | ___ |
| **WebSocket Latency** | <50ms | ___ |

**How to Measure:**
- **FPS:** Displayed in Gradio UI
- **Latency:** Timestamps in console logs
- **VRAM:** `nvidia-smi` command
- **WebSocket:** Network tab in browser DevTools

---

## Critical Files Reference

### Python Components
| Component | Entry Point | Configuration |
|-----------|-------------|---------------|
| **Active Learning Wizard** | `active_learning_engine/app.py` | `active_learning_engine/.env` (Gemini API key) |
| **SiA Fall Detection** | `sia_model/demo.py` | `sia_model/weights/` (model weights) |
| **Skeletal Overlay** | `skeletal_overlay/pipeline.py` | None |

### Flutter App
| File | Purpose |
|------|---------|
| `safefall_coach_mobile/.env` | Supabase credentials |
| `safefall_coach_mobile/lib/config/env.dart` | Environment config |
| `safefall_coach_mobile/lib/main.dart` | App entry point |
| `safefall_coach_mobile/lib/router/app_router.dart` | Navigation |
| `safefall_coach_mobile/lib/services/websocket_service.dart` | WebSocket client |

### Documentation
| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project architecture |
| `docker-plan.md` | Docker containerization plan (future) |
| `ovis-plan.md` | Ovis2.5-2B implementation plan (future) |
| `active_learning_engine/SIA_INTEGRATION.md` | SiA integration guide |

---

## Docker: When It Makes Sense (Future)

Docker implementation is **planned but not required for testing**. When implemented, it will provide:

### Benefits
1. **One-command setup** - `docker compose --profile demo up`
2. **Reproducible environment** - No "works on my machine" issues
3. **Model weight distribution** - Auto-download from Hugging Face
4. **GPU resource isolation** - VRAM allocation per container
5. **HIPAA-safe local database** - PostgreSQL container (no PHI on cloud)

### Implementation Status
- ✅ Comprehensive plan: `docker-plan.md` (33KB, 28-day timeline)
- ❌ Not yet implemented (Dockerfiles, docker-compose.yml not created)
- ⏳ Estimated timeline: 4 weeks for full implementation

### When to Use Docker
- Onboarding new team members
- Deploying to production
- Batch video processing (SiA + Skeletal Overlay)
- Running on multiple machines
- Demo day / presentations

### When to Use Native
- **Initial testing** (faster setup, simpler debugging)
- Active development (hot reload, IDE integration)
- Single developer machine
- When Docker isn't available (no admin rights)

**For this testing scenario (RTX 4090 Windows 11 PC):** Native setup is recommended.

---

## Next Steps After Testing

1. **Validate end-to-end flow:**
   - User sign up → dashboard → active learning session → fall detection → AI feedback

2. **Collect performance metrics:**
   - Fill in "Performance Validation" table above
   - Screenshot GPU usage during peak load

3. **Document issues:**
   - Any setup blockers encountered
   - Performance bottlenecks
   - Missing features or bugs

4. **Optional: Implement Docker** (if team wants reproducible setup)
   - Follow `docker-plan.md` (28-day plan)
   - Start with ML pipeline (SiA + Skeletal Overlay)
   - Then Active Learning Wizard
   - Finally local PostgreSQL

5. **Optional: Implement Ovis2.5-2B** (replace Gemini API)
   - Follow `ovis-plan.md`
   - Lazy loading strategy for 8-15GB VRAM
   - Persistent loading for ≥16GB VRAM (RTX 4090 perfect for this)

---

## Summary

**For testing the SafeFall Coach app on RTX 4090 Windows 11:**

✅ **Native Windows setup is recommended**
- Faster setup (15-20 minutes vs 45-90 minutes)
- Direct GPU access (10-15% better performance)
- Native webcam access (no passthrough complexity)
- Full debugging support
- Works for all components: Flutter, Python models, Supabase cloud

❌ **Docker is NOT needed**
- Flutter must run natively (hot reload, device access)
- Supabase backend is cloud-hosted (no local setup)
- Python models work fine with native virtual environments
- Docker is planned for future (reproducibility, deployment) but not required for testing

**Total Setup Time:** ~30 minutes
**Components:** Flutter app + Active Learning Wizard + Supabase (cloud)
**Result:** Full-stack testing on single Windows PC
