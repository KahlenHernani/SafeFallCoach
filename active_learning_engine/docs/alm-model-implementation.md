# Active Learning Mode - ML Model Implementation Plan

## Overview

This document outlines the implementation strategy for running ML models (RTMLib pose estimation, SiA fall detection, LLM feedback) on the UCF Newton GPU cluster for clip-based fall technique analysis.

## Architecture

### Design Rationale
- **Use case:** Patients practice safe-fall techniques with 1-2 minute rest between attempts
- **Processing approach:** Clip-based (10-15 second videos) with batch processing
- **Feedback latency:** 15-30 seconds is acceptable (users need rest between falls anyway)
- **Compute environment:** UCF Newton GPU cluster (Slurm batch jobs)
- **Real-time streaming:** Not needed - clip-based approach is sufficient

---

## Clip-Based Active Learning Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              CLIP-BASED ACTIVE LEARNING (UCF Newton)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   THERAPIST LAPTOP              UCF NEWTON              PATIENT     │
│   ┌─────────────────┐          ┌─────────────┐        ┌─────────┐  │
│   │ 1. Gradio UI    │          │             │        │ Mobile  │  │
│   │    (local,      │          │             │        │ App     │  │
│   │    no GPU need) │          │             │        │         │  │
│   │                 │          │             │        │         │  │
│   │ 2. Record 10sec │          │             │        │         │  │
│   │    video clip   │          │             │        │         │  │
│   │        │        │          │             │        │         │  │
│   │        ▼        │          │             │        │         │  │
│   │ 3. Upload to ───┼─────────▶│ Supabase    │        │         │  │
│   │    Supabase     │          │ Storage     │        │         │  │
│   │                 │          │     │       │        │         │  │
│   │                 │    ┌─────┼─────┴───────┤        │         │  │
│   │                 │    │     │ 4. Realtime │        │         │  │
│   │                 │    │     │    triggers │        │         │  │
│   │                 │    │     │    Newton   │        │         │  │
│   │                 │    │     ▼             │        │         │  │
│   │                 │    │ 5. Slurm job      │        │         │  │
│   │                 │    │    processes      │        │         │  │
│   │                 │    │    clip (ML)      │        │         │  │
│   │                 │    │     │             │        │         │  │
│   │                 │    │     ▼             │        │         │  │
│   │ 7. Display ◀────┼────┼─ 6. Feedback ─────┼───────▶│ 8. Show │  │
│   │    feedback     │    │    written &      │        │ feedback│  │
│   │ (Realtime sub)  │    │    pushed via     │        │ (Realtime)│
│   │                 │    │    Realtime       │        │         │  │
│   └─────────────────┘    └───────────────────┘        └─────────┘  │
│                                                                      │
│   Latency: 15-30 seconds per clip (acceptable for use case)         │
│   Notifications: Instant via Supabase Realtime subscriptions        │
└─────────────────────────────────────────────────────────────────────┘
```

### How It Works

1. **Gradio runs locally** on therapist laptop (M1 Mac or any machine) - no GPU needed
2. **Record 10-15 second clips** of patient practicing fall techniques
3. **Upload clip to Supabase Storage** with metadata in `processing_queue` table
4. **Slurm batch job on Newton** receives instant notification via Supabase Realtime
5. **ML pipeline processes clip** (RTMLib pose estimation, SiA fall detection, LLM feedback)
6. **Feedback written to Supabase** `session_feedback` table
7. **Gradio UI and Mobile app** receive instant notification via Supabase Realtime subscriptions
8. **Patient reviews feedback, rests, tries again** (1-2 minutes between attempts)

### Components to Build

#### 1. Docker Container (ML Backend)

```dockerfile
# Dockerfile
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

# Install dependencies
RUN pip install \
    rtmlib \
    opencv-python \
    gradio \
    supabase \
    torch torchvision \
    ftfy einops timm scipy regex

# Copy ML code
COPY active_learning_engine/ /app/active_learning_engine/
COPY sia_model/ /app/sia_model/

# Download model weights during build (faster startup)
RUN python -c "from rtmlib import Wholebody; Wholebody()"

WORKDIR /app
CMD ["python", "batch_processor.py"]
```

#### 2. Singularity Definition (For Newton)

```singularity
# singularity.def
Bootstrap: docker
From: safefall-ml:latest

%post
    # Any Newton-specific setup

%runscript
    python /app/batch_processor.py
```

#### 3. Supabase Schema (Processing Queue)

```sql
-- Table: processing_queue
CREATE TABLE processing_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES active_sessions(id),
    clip_path TEXT NOT NULL,           -- Supabase storage path
    status TEXT DEFAULT 'pending',      -- pending, processing, completed, failed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- Table: session_feedback
CREATE TABLE session_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES active_sessions(id),
    queue_item_id UUID REFERENCES processing_queue(id),
    feedback_type TEXT NOT NULL,        -- 'pose', 'fall_event', 'coaching'
    message TEXT NOT NULL,
    severity TEXT DEFAULT 'info',       -- info, warning, success
    pose_score INTEGER,                 -- 0-100
    technique_score INTEGER,            -- 0-100
    pose_data JSONB,                    -- Raw keypoints if needed
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for polling
CREATE INDEX idx_queue_status ON processing_queue(status, created_at);
```

#### 4. Batch Processor Script

```python
# batch_processor.py
"""
Runs on UCF Newton as a Slurm job.
Subscribes to Supabase Realtime for new clips, processes them, writes feedback.
"""
import os
import time
from supabase import create_client
from active_learning_engine.models.pose_estimator import PoseEstimator
from active_learning_engine.models.sia_detector import SiADetector
from active_learning_engine.models.feedback_generator import FeedbackGenerator

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_KEY']

def process_clip(supabase, item, pose_estimator, fall_detector, feedback_gen):
    """Process a single clip through the ML pipeline."""
    # Mark as processing
    supabase.table('processing_queue') \
        .update({'status': 'processing', 'started_at': 'now()'}) \
        .eq('id', item['id']) \
        .execute()

    try:
        # Download clip
        clip_data = supabase.storage.from_('clips').download(item['clip_path'])

        # Process with ML pipeline
        poses = pose_estimator.process_video(clip_data)
        falls = fall_detector.detect(clip_data)
        feedback = feedback_gen.generate(poses, falls)

        # Write feedback (triggers Realtime notification to UI/mobile)
        for fb in feedback:
            supabase.table('session_feedback').insert({
                'session_id': item['session_id'],
                'queue_item_id': item['id'],
                'feedback_type': fb['type'],
                'message': fb['message'],
                'severity': fb['severity'],
                'pose_score': fb.get('pose_score'),
                'technique_score': fb.get('technique_score'),
            }).execute()

        # Mark completed
        supabase.table('processing_queue') \
            .update({'status': 'completed', 'completed_at': 'now()'}) \
            .eq('id', item['id']) \
            .execute()

    except Exception as e:
        supabase.table('processing_queue') \
            .update({'status': 'failed', 'error_message': str(e)}) \
            .eq('id', item['id']) \
            .execute()

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Initialize models once at startup
    print("Loading ML models...")
    pose_estimator = PoseEstimator()
    fall_detector = SiADetector()
    feedback_gen = FeedbackGenerator()
    print("Models loaded, listening for clips...")

    # Subscribe to new clips via Realtime
    def handle_new_clip(payload):
        if payload['eventType'] == 'INSERT' and payload['new']['status'] == 'pending':
            print(f"Processing new clip: {payload['new']['id']}")
            process_clip(supabase, payload['new'], pose_estimator, fall_detector, feedback_gen)

    # Subscribe to INSERT events on processing_queue
    supabase.table('processing_queue') \
        .on('INSERT', handle_new_clip) \
        .subscribe()

    print("Subscribed to processing_queue. Waiting for clips...")

    # Keep process alive
    while True:
        time.sleep(60)

if __name__ == '__main__':
    main()
```

#### 5. Slurm Job Script

```bash
#!/bin/bash
#SBATCH --job-name=safefall-ml
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --time=04:00:00
#SBATCH --output=safefall-%j.out

# Load Singularity module (Newton-specific)
module load singularity

# Run container
singularity run --nv \
    --env SUPABASE_URL=$SUPABASE_URL \
    --env SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY \
    safefall-ml.sif
```

### File Structure

```
safefall-ml/
├── Dockerfile
├── singularity.def
├── docker-compose.yml          # For local testing
├── docker-compose.cpu.yml      # CPU-only override
├── .env.example
├── .env.local                  # Local dev (gitignored)
├── .env.newton                 # Newton settings (gitignored)
├── config/
│   ├── config.yaml             # Runtime configuration
│   └── llm.yaml                # LLM backend settings
├── scripts/
│   ├── build.sh                # Build Docker image
│   ├── build-singularity.sh    # Convert to Singularity
│   ├── run-local.sh            # Run locally with Docker
│   ├── submit-newton.sh        # Submit Slurm job
│   └── download-weights.sh     # Download model weights
├── batch_processor.py          # Main processing loop
└── requirements.txt
```

---

## Optional: Local GPU Testing

For development and testing without Newton cluster access, you can run the batch processor locally:

### Docker Compose (Local Testing)

```yaml
# docker-compose.yml
version: '3.8'

services:
  ml-backend:
    build: .
    env_file: .env.local
    volumes:
      - ./models:/app/models  # Persist model weights
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

```yaml
# docker-compose.cpu.yml (override for CPU-only)
version: '3.8'

services:
  ml-backend:
    environment:
      - CUDA_VISIBLE_DEVICES=""
    deploy:
      resources:
        reservations:
          devices: []
```

### Running Locally

```bash
# With GPU
docker compose up

# Without GPU (CPU fallback)
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up
```

**Note:** Local testing is optional. Production deployment uses Newton cluster with Slurm.

---

## LLM Backend Configuration

### Config File

```yaml
# config/llm.yaml
llm:
  default: gemini  # Options: gemini, ovis, ollama

  backends:
    gemini:
      provider: google
      model: gemini-1.5-flash
      api_key_env: GEMINI_API_KEY

    ovis:
      provider: local
      model: ovis-2.5
      model_path: /app/models/ovis-2.5
      device: auto  # auto-detect GPU/CPU

    ollama:
      provider: ollama
      model: llama3.2
      base_url: http://localhost:11434

  fallback_chain:
    - ovis      # Try local first
    - gemini    # Fall back to cloud API
```

### Environment Variable Override

```bash
# Override config via env var
LLM_BACKEND=gemini python app.py

# Or use config default
python app.py
```

---

## GPU Backend Switching

### Environment Detection

```python
# config/gpu.py
import torch
import os

def get_device():
    """Auto-detect best available device."""
    # Check for env var override
    if os.environ.get('FORCE_CPU'):
        return 'cpu'

    # Check for CUDA
    if torch.cuda.is_available():
        return 'cuda'

    # Check for Apple Silicon MPS
    if torch.backends.mps.is_available():
        return 'mps'

    return 'cpu'

def get_device_info():
    """Return device info for logging."""
    device = get_device()
    if device == 'cuda':
        return f"CUDA: {torch.cuda.get_device_name(0)}"
    elif device == 'mps':
        return "Apple Silicon (MPS)"
    return "CPU"
```

### Docker Compose Profiles

```bash
# Run with GPU profile
docker compose --profile gpu up

# Run with CPU profile
docker compose --profile cpu up
```

---

## Environment Variables

### .env.example

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key  # For batch processor only

# LLM Backend
LLM_BACKEND=gemini  # gemini, ovis, ollama
GEMINI_API_KEY=your-gemini-key

# GPU Settings
FORCE_CPU=false
CUDA_VISIBLE_DEVICES=0

# Processing Settings
CLIP_DURATION=10          # seconds
FEEDBACK_COOLDOWN=3       # seconds between feedback messages
```

---

## Implementation Checklist

### Docker Setup
- [ ] Create Dockerfile with all ML dependencies
- [ ] Test Docker build locally
- [ ] Create singularity.def for Newton
- [ ] Build and test Singularity image

### Supabase Schema
- [ ] Create `processing_queue` table
- [ ] Create `session_feedback` table
- [ ] Set up RLS policies
- [ ] Create storage bucket for clips
- [ ] Enable Realtime on both tables

### Batch Processor (Newton)
- [ ] Implement Realtime subscription for new clips
- [ ] Integrate pose estimation (RTMLib)
- [ ] Integrate fall detection (SiA)
- [ ] Integrate feedback generation (LLM)
- [ ] Error handling and logging
- [ ] Test connection retry logic

### Gradio UI Updates
- [ ] Add "Record Clip" button
- [ ] Implement clip upload to Supabase
- [ ] Subscribe to `session_feedback` via Realtime
- [ ] Display feedback in UI
- [ ] Show processing status

### Slurm Integration
- [ ] Create job submission script
- [ ] Test on Newton cluster
- [ ] Set up job monitoring
- [ ] Configure auto-restart on failure

### Mobile App Updates
- [ ] Subscribe to `session_feedback` table via Realtime
- [ ] Display feedback in active learning session
- [ ] Handle reconnection logic

---

## Hardware Requirements

| Environment | GPU | RAM | Storage |
|-------------|-----|-----|---------|
| UCF Newton | Cluster GPU | 16GB+ | Shared filesystem |
| Local (RTX 2080 Ti) | 11GB VRAM | 16GB+ | 10GB for models |
| Local (M1 Mac) | MPS (8-16GB unified) | 16GB+ | 10GB for models |
| CPU Fallback | None | 32GB+ | 10GB for models |

---

## Testing Strategy

### Unit Tests
- [ ] Pose estimator accuracy on sample videos
- [ ] Fall detector precision/recall
- [ ] Feedback generator rule coverage

### Integration Tests
- [ ] End-to-end batch processing flow
- [ ] Supabase queue reliability
- [ ] Mobile app feedback display

### Performance Tests
- [ ] Batch processing throughput (clips/hour)
- [ ] Real-time inference latency (ms/frame)
- [ ] Model loading time (seconds)

---

## Troubleshooting

### Common Issues

**Slurm job won't start:**
- Check GPU partition availability: `sinfo -p gpu`
- Check job queue: `squeue -u $USER`
- Check error log: `cat safefall-*.out`

**Singularity GPU access:**
- Ensure `--nv` flag is used
- Check CUDA drivers: `nvidia-smi`

**Model loading slow:**
- Pre-download weights in Docker build
- Use model caching in persistent volume

**Supabase connection timeout:**
- Check Newton network access to Supabase
- Use service role key (not anon key) for batch processor
