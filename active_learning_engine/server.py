#!/usr/bin/env python3
"""
FastAPI server for SafeFall Active Learning Wizard.

Exposes the ML pipeline (pose estimation, fall detection, LLM feedback)
via REST endpoints, MJPEG streaming, and a state WebSocket. The Flutter
desktop app connects to this server on localhost:8000.

The mobile app WebSocket (port 8765) is unchanged and managed by the
existing WebSocketServer class.
"""

import asyncio
import json
import re
import time
import threading
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from pydantic import BaseModel

from active_learning_engine.models import SiADetector, PoseEstimator, FeedbackGenerator
from active_learning_engine.services import WebSocketServer as MobileWSServer, QRGenerator, SessionManager
from active_learning_engine.services.session_data_exporter import SessionDataExporter
from active_learning_engine.utils import CameraCapture

from active_learning_engine.wizard import ActiveLearningWizard


# ── Pydantic models for request/response ─────────────────────

class CameraStartRequest(BaseModel):
    camera_index: int = 0

class SessionStartRequest(BaseModel):
    participant_id: str = ""
    # When True, frames are supplied by the client via POST /frame (e.g. a web
    # browser using the user's webcam) and the server-side camera is not opened.
    use_client_camera: bool = False

class SessionNoteRequest(BaseModel):
    text: str


# ── Global state ─────────────────────────────────────────────

wizard: Optional[ActiveLearningWizard] = None
_researcher_notes: List[Dict] = []
_preview_mode: bool = False  # Camera running but no session
_client_camera_mode: bool = False  # Frames supplied by client via POST /frame
_state_ws_clients: set = set()
_state_broadcast_task: Optional[asyncio.Task] = None

# Serializes /frame processing so concurrent uploads don't race on the
# SiA temporal buffer / shared feedback state (process_frame is single-threaded
# by design — the desktop path calls it from one MJPEG loop).
_frame_process_lock = asyncio.Lock()


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global wizard, _state_broadcast_task
    wizard = ActiveLearningWizard()
    print("[Server] Initializing ML pipeline...")
    # Run blocking initialization in a thread so the event loop stays responsive.
    # Without this, HTTP health checks time out while ML models load.
    import asyncio as _asyncio
    await _asyncio.to_thread(wizard.initialize)
    print("[Server] ML pipeline ready.\n")

    # Start state broadcast loop
    _state_broadcast_task = asyncio.create_task(_broadcast_state_loop())

    yield

    # Cleanup
    if _state_broadcast_task:
        _state_broadcast_task.cancel()
    if wizard:
        wizard.cleanup()


# ── App creation ─────────────────────────────────────────────

app = FastAPI(
    title="SafeFall Active Learning Server",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ───────────────────────────────────────────────────

@app.get("/health")
async def health():
    if wizard is None:
        # Return 200 so Flutter doesn't show "Offline" during startup
        return {"status": "starting", "components": {}, "camera_running": False,
                "session_active": False, "mobile_clients": 0}
    return {
        "status": "ok",
        "components": wizard._component_health,
        "camera_running": wizard.camera.is_running,
        "session_active": wizard.session_manager.is_active,
        "mobile_clients": wizard.ws_server.client_count,
    }


# ── Camera ───────────────────────────────────────────────────

@app.get("/cameras")
async def list_cameras():
    cameras = CameraCapture.list_cameras()
    return {"cameras": [{"index": i, "label": f"Camera {i}"} for i in cameras]}


@app.post("/camera/start")
async def camera_start(req: CameraStartRequest):
    global _preview_mode
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    wizard.set_camera(req.camera_index)
    success = wizard.camera.start()
    if success:
        wizard._component_health["camera"] = wizard._get_camera_health()
        wizard._processing = True  # Enable frame processing for preview
        _preview_mode = True
        # Auto-resume if session was paused (e.g. by a previous camera stop)
        session_resumed = False
        if wizard._paused:
            wizard.resume()
            session_resumed = True
        return {"status": "started", "camera_index": req.camera_index,
                "session_resumed": session_resumed}
    return JSONResponse({"error": "Failed to open camera"}, status_code=500)


@app.post("/camera/stop")
async def camera_stop():
    global _preview_mode
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    session_was_active = wizard.session_manager.is_active
    # If session is active, auto-pause it first
    if session_was_active and not wizard._paused:
        wizard.pause()

    wizard._processing = False
    wizard.camera.stop()
    wizard._component_health["camera"] = wizard._get_camera_health()
    _preview_mode = False
    return {
        "status": "stopped",
        "session_paused": session_was_active,
    }


class CameraSwitchRequest(BaseModel):
    camera_index: int = 0


@app.post("/camera/switch")
async def camera_switch(req: CameraSwitchRequest):
    global _preview_mode
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    session_was_active = wizard.session_manager.is_active and not wizard._paused

    # Auto-pause session if active
    if session_was_active:
        wizard.pause()

    # Stop current camera
    wizard._processing = False
    wizard.camera.stop()

    # Start new camera
    wizard.set_camera(req.camera_index)
    success = wizard.camera.start()
    if not success:
        wizard._component_health["camera"] = wizard._get_camera_health()
        return JSONResponse({"error": "Failed to open camera"}, status_code=500)

    wizard._component_health["camera"] = wizard._get_camera_health()
    wizard._processing = True
    _preview_mode = not wizard.session_manager.is_active

    # Auto-resume session if it was active before
    if session_was_active:
        wizard.resume()

    return {
        "status": "switched",
        "camera_index": req.camera_index,
        "session_resumed": session_was_active,
    }


# ── MJPEG Stream ─────────────────────────────────────────────

def _generate_mjpeg():
    """Yield MJPEG frames from the ML pipeline."""
    while wizard and wizard._processing:
        if wizard.session_manager.is_active or _preview_mode:
            annotated_rgb, _, _ = wizard.process_and_get_frame()
            # RGB → BGR for JPEG encoding
            frame_bgr = cv2.cvtColor(annotated_rgb, cv2.COLOR_RGB2BGR)
        else:
            # No active processing — yield placeholder
            frame_bgr = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame_bgr, "No camera feed", (200, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        _, jpeg = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg.tobytes()
            + b"\r\n"
        )
        time.sleep(0.033)  # ~30fps


@app.get("/video_feed")
async def video_feed():
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)
    return StreamingResponse(
        _generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── Client-supplied frames (browser webcam) ──────────────────

@app.post("/frame")
async def process_client_frame(request: Request):
    """Analyze a single webcam frame supplied by the client (e.g. a browser).

    The browser captures the user's webcam, POSTs each frame here as raw JPEG
    bytes, and receives the annotated frame (pose overlay) back as JPEG.
    Coaching feedback and scores are pushed separately over /ws/state, exactly
    as they are for the server-side camera path — this endpoint just feeds the
    same ML pipeline (wizard.process_frame) from a different frame source.
    """
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)
    if not wizard.session_manager.is_active:
        return JSONResponse({"error": "No active session"}, status_code=400)

    raw = await request.body()
    if not raw:
        return JSONResponse({"error": "Empty frame"}, status_code=400)

    arr = np.frombuffer(raw, dtype=np.uint8)
    frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame_bgr is None:
        return JSONResponse({"error": "Could not decode frame"}, status_code=400)

    if wizard._paused:
        # Don't run the pipeline while paused — echo the frame back untouched.
        annotated_bgr = frame_bgr
    else:
        # process_frame is CPU/GPU-heavy and not async — run it off the event
        # loop, and serialize so concurrent uploads don't race on shared state.
        async with _frame_process_lock:
            annotated_rgb, _, _ = await asyncio.to_thread(
                wizard.process_frame, frame_bgr
            )
        annotated_bgr = cv2.cvtColor(annotated_rgb, cv2.COLOR_RGB2BGR)

    ok, jpeg = cv2.imencode(".jpg", annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return JSONResponse({"error": "Failed to encode frame"}, status_code=500)
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")


# ── Session ──────────────────────────────────────────────────

@app.post("/session/start")
async def session_start(req: SessionStartRequest):
    global _preview_mode, _researcher_notes, _client_camera_mode
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    participant_id = (req.participant_id or "").strip()
    if participant_id and not re.match(r'^[A-Za-z0-9_-]+$', participant_id):
        return JSONResponse(
            {"error": "Participant ID must contain only letters, numbers, dashes, underscores"},
            status_code=400,
        )

    # Clear researcher notes for new session
    _researcher_notes = []

    _client_camera_mode = bool(req.use_client_camera)

    if not _client_camera_mode:
        # Server-side camera (Flutter desktop). When the browser supplies its
        # own webcam frames via POST /frame we skip opening a local camera.
        if not wizard.camera.is_running:
            wizard.camera.start()
            wizard._component_health["camera"] = wizard._get_camera_health()

    qr_image, info, status = wizard.start_session(
        study_id=participant_id,
        start_camera=not _client_camera_mode,
    )
    _preview_mode = False  # Now in session mode

    # Extract session_id from info string
    session_id = "unknown"
    if "Session ID:" in info:
        for line in info.strip().split("\n"):
            if "Session ID:" in line:
                session_id = line.split("Session ID:")[-1].strip()
                break

    # Get QR data for Flutter to display
    qr_data = None
    if wizard.qr_generator.current_session_id:
        qr_data = {
            "session_id": wizard.qr_generator.current_session_id,
            "ws_url": wizard.qr_generator.get_connection_url(),
        }

    return {
        "status": "started",
        "session_id": session_id,
        "participant_id": participant_id or "anonymous",
        "qr_data": qr_data,
    }


@app.post("/session/pause")
async def session_pause():
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)
    wizard.pause()
    return {"status": "paused"}


@app.post("/session/resume")
async def session_resume():
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)
    wizard.resume()
    return {"status": "active"}


@app.post("/session/stop")
async def session_stop():
    global _preview_mode, _client_camera_mode
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    summary_text, has_data = wizard.stop_session()
    # Camera is stopped by stop_session(); user must restart for preview
    _preview_mode = False
    _client_camera_mode = False

    stats = wizard.session_manager.stats
    return {
        "status": "ended",
        "has_pending_data": has_data,
        "summary": {
            "duration_seconds": stats.duration_seconds,
            "total_falls": stats.total_falls,
            "average_score": round(stats.average_technique_score, 1),
            "best_score": stats.best_technique_score,
            "feedback_count": stats.total_feedback_count,
            "fall_records": [
                {
                    "timestamp": round(fr.timestamp - stats.start_time, 2),
                    "technique_score": fr.technique_score,
                    "feedback": fr.feedback,
                }
                for fr in stats.fall_records
            ],
        },
        "notes": _researcher_notes,
    }


@app.post("/session/note")
async def session_note(req: SessionNoteRequest):
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)
    if wizard.session_manager.state.value not in ("active", "paused"):
        return JSONResponse({"error": "No active session"}, status_code=400)

    note_text = req.text.strip()
    if not note_text:
        return JSONResponse({"error": "Note text cannot be empty"}, status_code=400)

    relative_ts = round(
        time.time() - wizard.session_manager.stats.start_time, 2
    )
    note = {
        "relative_timestamp": relative_ts,
        "text": note_text,
    }
    _researcher_notes.append(note)
    return {"status": "added", "note": note}


@app.post("/session/export")
async def session_export():
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    paths = wizard.export_pending_data()
    if not paths:
        return JSONResponse({"error": "No pending data to export"}, status_code=400)

    # Also save researcher notes alongside the export
    if _researcher_notes and paths.get("json"):
        notes_path = paths["json"].replace(".json", "_notes.json")
        try:
            import json as json_mod
            with open(notes_path, "w") as f:
                json_mod.dump(_researcher_notes, f, indent=2)
            paths["notes_json"] = notes_path
        except Exception as e:
            print(f"[Server] Failed to save notes: {e}")

    return {"status": "exported", "paths": paths}


@app.post("/session/discard")
async def session_discard():
    global _researcher_notes
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)
    wizard.discard_pending_data()
    _researcher_notes = []
    return {"status": "discarded"}


# ── QR Code ──────────────────────────────────────────────────

@app.get("/session/qr")
async def session_qr():
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    qr_image, _ = wizard.qr_generator.generate(
        session_id=wizard.qr_generator.current_session_id,
    )
    if qr_image is None:
        return JSONResponse({"error": "QR generation failed"}, status_code=500)

    buf = BytesIO()
    qr_image.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png")


# ── State WebSocket ──────────────────────────────────────────

async def _broadcast_state_loop():
    """Push state to all connected Flutter clients at ~10Hz."""
    global _state_ws_clients
    while True:
        try:
            if _state_ws_clients and wizard:
                state = _build_state()
                message = json.dumps(state)
                disconnected = set()
                for ws in _state_ws_clients.copy():
                    try:
                        await ws.send_text(message)
                    except Exception:
                        disconnected.add(ws)
                _state_ws_clients -= disconnected
        except Exception as e:
            print(f"[Server] State broadcast error: {e}", flush=True)
        await asyncio.sleep(0.1)  # 10Hz


def _build_state() -> dict:
    """Build the state dict to push over WebSocket."""
    if wizard is None:
        return {"session_active": False}

    stats = wizard.session_manager.stats
    session_active = wizard.session_manager.is_active
    elapsed = stats.duration_seconds if (session_active or wizard._paused or 
                                        stats.end_time > 0) else 0

    # Get latest feedback from wizard's internal state
    with wizard._frame_lock:
        latest_feedback = wizard._latest_feedback
        pose_info = wizard._latest_pose_info
        severity = wizard._latest_severity
        feedback_time = wizard._latest_feedback_time
        feedback_id = wizard._feedback_id

    # Parse pose_score from pose_info (simple heuristic)
    pose_score = 0
    fall_confidence = 0.0
    if wizard.sia_detector and wizard.sia_detector._last_result is not None:
        fall_confidence = wizard.sia_detector._last_result.confidence

    return {
        "session_active": session_active,
        "paused": wizard._paused,
        "duration_str": f"{elapsed // 60:02d}:{elapsed % 60:02d}",
        "duration_seconds": elapsed,
        "fall_count": stats.total_falls,
        "pose_score": pose_score,
        "fall_confidence": fall_confidence,
        "latest_feedback": latest_feedback,
        "feedback_id": feedback_id,
        "severity": severity,
        "component_health": wizard._component_health,
        "mobile_clients": wizard.ws_server.client_count,
        "camera_fps": round(wizard.camera.actual_fps, 1),
        "camera_running": wizard.camera.is_running,
    }


@app.websocket("/ws/state")
async def state_websocket(ws: WebSocket):
    await ws.accept()
    _state_ws_clients.add(ws)
    try:
        while True:
            # Keep alive — handle client messages (ping/close)
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                # Client can send pings; we just ignore
            except asyncio.TimeoutError:
                # Send a keep-alive ping
                try:
                    await ws.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        _state_ws_clients.discard(ws)


# ── Webcam Ingest WebSocket ──────────────────────────────────
#
# Self-contained, additive endpoint: lets the browser push its webcam frames
# to the server when the machine running the engine has no local camera. Each
# JPEG frame is decoded and run through the SAME pipeline as a camera frame
# (wizard.process_frame), so the resulting coaching feedback is broadcast over
# /ws/state exactly as usual. No other part of the server or wizard changes.
#
# Protocol (matches safe-fall-coach-Web/src/lib/activeLearningApi.ts):
#   1. Client opens ws://<host>/ws/ingest
#   2. Optional first TEXT frame: {"type":"hello","format":"jpeg",...} — ignored
#   3. Then BINARY messages, each a complete JPEG frame, ~12 fps.

@app.websocket("/ws/ingest")
async def ingest_websocket(ws: WebSocket):
    await ws.accept()
    if wizard is None:
        await ws.close()
        return

    latest = {"frame": None}   # most recent decoded frame (newer replaces older)
    busy = {"flag": False}     # single-flight guard: one frame in the pipeline

    def _process_latest():
        frame = latest["frame"]
        if frame is not None:
            wizard.process_frame(frame)

    async def _run():
        try:
            # Run the (heavy, blocking) ML pipeline off the event loop.
            await asyncio.to_thread(_process_latest)
        except Exception as e:
            print(f"[Server] Ingest processing error: {e}", flush=True)
        finally:
            busy["flag"] = False

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data is None:
                # Text frame (hello / keep-alive) — nothing to decode.
                continue
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            latest["frame"] = frame
            # Process the newest frame; drop any that arrive while busy so the
            # pipeline never queues up behind a fast stream.
            if not busy["flag"]:
                busy["flag"] = True
                asyncio.create_task(_run())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[Server] Ingest socket error: {e}", flush=True)
