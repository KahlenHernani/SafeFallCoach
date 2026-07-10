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
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Any

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

class ActiveLearningRequest(BaseModel):
    participant_id: str

class ActiveLearningDecisionRequest(BaseModel):
    status: str

class ActiveLearningEnabledRequest(BaseModel):
    enabled: bool

class AnalyticsEventRequest(BaseModel):
    participant_id: str = ""
    event_type: str
    metadata: Dict[str, Any] = {}


# ── Global state ─────────────────────────────────────────────

wizard: Optional[ActiveLearningWizard] = None
_researcher_notes: List[Dict] = []
_preview_mode: bool = False  # Camera running but no session
_client_camera_mode: bool = False  # Frames supplied by client via POST /frame
_state_ws_clients: set = set()
_state_broadcast_task: Optional[asyncio.Task] = None
_active_learning_participant_id: Optional[str] = None

# Serializes /frame processing so concurrent uploads don't race on the
# SiA temporal buffer / shared feedback state (process_frame is single-threaded
# by design — the desktop path calls it from one MJPEG loop).
_frame_process_lock = asyncio.Lock()
_access_lock = threading.Lock()
_access_store_path = Path(__file__).with_name("active_learning_access.json")
_daily_session_start_time: float = 0
_analytics_lock = threading.Lock()
_analytics_store_path = Path(__file__).with_name("analytics_events.json")

ACTIVE_LEARNING_DAILY_SECONDS_LIMIT = 30 * 60
ACTIVE_LEARNING_DAILY_SESSION_LIMIT = 20
ACTIVE_LEARNING_REQUEST_STATUSES = {"pending", "approved", "rejected"}
ANALYTICS_ALLOWED_EVENTS = {
    "registration",
    "onboarding_completed",
    "training_started",
    "training_completed",
    "active_learning_session_started",
    "active_learning_session_completed",
}


def _today_key() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _normalize_participant_id(participant_id: str) -> str:
    normalized = (participant_id or "").strip()
    if not normalized:
        raise ValueError("Participant ID is required for Active Learning Mode.")
    if not re.match(r'^[A-Za-z0-9_-]+$', normalized):
        raise ValueError("Participant ID must contain only letters, numbers, dashes, underscores")
    return normalized


def _empty_access_store() -> dict:
    return {"users": {}}


def _load_access_store() -> dict:
    if not _access_store_path.exists():
        return _empty_access_store()
    try:
        with _access_store_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty_access_store()
        data.setdefault("users", {})
        return data
    except Exception as e:
        print(f"[Server] Failed to read Active Learning access store: {e}", flush=True)
        return _empty_access_store()


def _save_access_store(store: dict):
    tmp_path = _access_store_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, sort_keys=True)
    tmp_path.replace(_access_store_path)


def _default_access_record(participant_id: str) -> dict:
    return {
        "participant_id": participant_id,
        "request_status": "none",
        "enabled": False,
        "requested_at": None,
        "reviewed_at": None,
        "daily_usage": {},
    }


def _get_access_record(store: dict, participant_id: str) -> dict:
    users = store.setdefault("users", {})
    if participant_id not in users:
        users[participant_id] = _default_access_record(participant_id)
    users[participant_id].setdefault("daily_usage", {})
    return users[participant_id]


def _daily_usage(record: dict, day: Optional[str] = None) -> dict:
    day_key = day or _today_key()
    usage = record.setdefault("daily_usage", {}).setdefault(
        day_key,
        {"sessions": 0, "seconds": 0},
    )
    usage.setdefault("sessions", 0)
    usage.setdefault("seconds", 0)
    return usage


def _serialize_access_record(record: dict) -> dict:
    usage = _daily_usage(record)
    seconds_used = int(usage.get("seconds", 0))
    sessions_used = int(usage.get("sessions", 0))
    return {
        "participant_id": record["participant_id"],
        "request_status": record.get("request_status", "none"),
        "enabled": bool(record.get("enabled", False)),
        "requested_at": record.get("requested_at"),
        "reviewed_at": record.get("reviewed_at"),
        "daily_limit_seconds": ACTIVE_LEARNING_DAILY_SECONDS_LIMIT,
        "daily_session_limit": ACTIVE_LEARNING_DAILY_SESSION_LIMIT,
        "daily_seconds_used": seconds_used,
        "daily_seconds_remaining": max(0, ACTIVE_LEARNING_DAILY_SECONDS_LIMIT - seconds_used),
        "daily_sessions_used": sessions_used,
        "daily_sessions_remaining": max(0, ACTIVE_LEARNING_DAILY_SESSION_LIMIT - sessions_used),
    }


def _validate_active_learning_start(participant_id: str) -> Optional[JSONResponse]:
    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, participant_id)
        usage = _daily_usage(record)
        _save_access_store(store)

        if record.get("request_status") != "approved":
            return JSONResponse(
                {"error": "Active Learning Mode requires administrator approval.", "access": _serialize_access_record(record)},
                status_code=403,
            )
        if not record.get("enabled", False):
            return JSONResponse(
                {"error": "Active Learning Mode is disabled for this participant.", "access": _serialize_access_record(record)},
                status_code=403,
            )
        if int(usage.get("seconds", 0)) >= ACTIVE_LEARNING_DAILY_SECONDS_LIMIT:
            return JSONResponse(
                {"error": "Daily Active Learning time limit reached.", "access": _serialize_access_record(record)},
                status_code=403,
            )
        if int(usage.get("sessions", 0)) >= ACTIVE_LEARNING_DAILY_SESSION_LIMIT:
            return JSONResponse(
                {"error": "Daily Active Learning session limit reached.", "access": _serialize_access_record(record)},
                status_code=403,
            )
    return None


def _record_active_learning_session(participant_id: Optional[str], elapsed_seconds: int):
    if not participant_id:
        return
    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, participant_id)
        usage = _daily_usage(record)
        usage["sessions"] = min(
            ACTIVE_LEARNING_DAILY_SESSION_LIMIT,
            int(usage.get("sessions", 0)) + 1,
        )
        usage["seconds"] = min(
            ACTIVE_LEARNING_DAILY_SECONDS_LIMIT,
            int(usage.get("seconds", 0)) + max(0, elapsed_seconds),
        )
        _save_access_store(store)


def _daily_limit_reached(participant_id: Optional[str], current_elapsed: int = 0) -> bool:
    if not participant_id:
        return False
    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, participant_id)
        usage = _daily_usage(record)
        return (
            int(usage.get("seconds", 0)) + max(0, current_elapsed) >= ACTIVE_LEARNING_DAILY_SECONDS_LIMIT
            or int(usage.get("sessions", 0)) >= ACTIVE_LEARNING_DAILY_SESSION_LIMIT
        )


def _active_learning_access_revoked(participant_id: Optional[str]) -> bool:
    if not participant_id:
        return False
    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, participant_id)
        return record.get("request_status") != "approved" or not record.get("enabled", False)


def _finish_active_learning_session_for_limits() -> bool:
    global _preview_mode, _client_camera_mode, _active_learning_participant_id, _daily_session_start_time
    if wizard is None or not wizard.session_manager.is_active:
        return False

    participant_id = _active_learning_participant_id
    elapsed_for_limits = int(max(0, time.time() - _daily_session_start_time)) if _daily_session_start_time else 0
    wizard.stop_session()
    _record_active_learning_session(participant_id, elapsed_for_limits)
    _record_analytics_event(
        "active_learning_session_completed",
        participant_id or "anonymous",
        {"duration_seconds": elapsed_for_limits, "ended_by": "server_limit_or_disable"},
    )
    _active_learning_participant_id = None
    _daily_session_start_time = 0
    _preview_mode = False
    _client_camera_mode = False
    return True


def _analytics_now() -> datetime:
    return datetime.now()


def _analytics_date_key(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _analytics_hour_label(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour} {suffix}"


def _seed_analytics_events() -> List[dict]:
    now = _analytics_now().replace(minute=0, second=0, microsecond=0)
    events: List[dict] = []
    users = [f"demo-{i:02d}" for i in range(1, 19)]
    for index, user in enumerate(users):
        registered_at = now - timedelta(days=34 - index)
        events.append({
            "participant_id": user,
            "event_type": "registration",
            "timestamp": registered_at.isoformat(),
            "metadata": {},
        })
        if index < 16:
            events.append({
                "participant_id": user,
                "event_type": "onboarding_completed",
                "timestamp": (registered_at + timedelta(hours=4)).isoformat(),
                "metadata": {},
            })
        if index < 14:
            first_training = registered_at + timedelta(days=1, hours=index % 6)
            events.append({
                "participant_id": user,
                "event_type": "training_started",
                "timestamp": first_training.isoformat(),
                "metadata": {"lesson_id": (index % 3) + 1},
            })
            if index < 12:
                events.append({
                    "participant_id": user,
                    "event_type": "training_completed",
                    "timestamp": (first_training + timedelta(minutes=6)).isoformat(),
                    "metadata": {"lesson_id": (index % 3) + 1},
                })
        if index < 11:
            events.append({
                "participant_id": user,
                "event_type": "training_started",
                "timestamp": (registered_at + timedelta(days=8, hours=10 + index % 5)).isoformat(),
                "metadata": {"lesson_id": ((index + 1) % 3) + 1},
            })
        if index < 8:
            events.append({
                "participant_id": user,
                "event_type": "active_learning_session_completed",
                "timestamp": (registered_at + timedelta(days=31, hours=9 + index % 8)).isoformat(),
                "metadata": {"duration_seconds": 420 + index * 30},
            })

    for day_offset in range(0, 30):
        day = now - timedelta(days=day_offset)
        active_count = max(3, 15 - day_offset // 3)
        for index, user in enumerate(users[:active_count]):
            hour = [8, 10, 14, 16, 19][(index + day_offset) % 5]
            lesson_id = ((index + day_offset) % 3) + 1
            event_time = day.replace(hour=hour)
            events.append({
                "participant_id": user,
                "event_type": "training_started",
                "timestamp": event_time.isoformat(),
                "metadata": {"lesson_id": lesson_id},
            })
            if (index + day_offset) % 4 != 0:
                events.append({
                    "participant_id": user,
                    "event_type": "training_completed",
                    "timestamp": (event_time + timedelta(minutes=5)).isoformat(),
                    "metadata": {"lesson_id": lesson_id},
                })
    return events


def _load_analytics_events() -> List[dict]:
    if not _analytics_store_path.exists():
        return _seed_analytics_events()
    try:
        with _analytics_store_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else _seed_analytics_events()
    except Exception as e:
        print(f"[Server] Failed to read analytics store: {e}", flush=True)
        return _seed_analytics_events()


def _save_analytics_events(events: List[dict]):
    tmp_path = _analytics_store_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, sort_keys=True)
    tmp_path.replace(_analytics_store_path)


def _record_analytics_event(event_type: str, participant_id: str = "", metadata: Optional[Dict[str, Any]] = None):
    if event_type not in ANALYTICS_ALLOWED_EVENTS:
        return
    normalized_id = (participant_id or "anonymous").strip() or "anonymous"
    event = {
        "participant_id": normalized_id,
        "event_type": event_type,
        "timestamp": _analytics_now().isoformat(),
        "metadata": metadata or {},
    }
    with _analytics_lock:
        events = _load_analytics_events()
        events.append(event)
        _save_analytics_events(events)


def _parse_event_time(event: dict) -> datetime:
    try:
        return datetime.fromisoformat(event.get("timestamp", ""))
    except ValueError:
        return _analytics_now()


def _count_users_with(events: List[dict], event_type: str, since: Optional[datetime] = None) -> int:
    users = set()
    for event in events:
        if event.get("event_type") != event_type:
            continue
        if since and _parse_event_time(event) < since:
            continue
        users.add(event.get("participant_id", "anonymous"))
    return len(users)


def _analytics_summary(events: List[dict]) -> dict:
    now = _analytics_now()
    all_activity = [
        event for event in events
        if event.get("event_type") in {
            "onboarding_completed",
            "training_started",
            "training_completed",
            "active_learning_session_started",
            "active_learning_session_completed",
        }
    ]
    active_since = lambda days: {
        event.get("participant_id", "anonymous")
        for event in all_activity
        if _parse_event_time(event) >= now - timedelta(days=days)
    }

    registrations = {
        event.get("participant_id", "anonymous"): _parse_event_time(event)
        for event in events
        if event.get("event_type") == "registration"
    }
    onboarded_users = {
        event.get("participant_id", "anonymous")
        for event in events
        if event.get("event_type") == "onboarding_completed"
    }
    first_training_users = {
        event.get("participant_id", "anonymous")
        for event in events
        if event.get("event_type") == "training_started"
    }
    week_one_users = set()
    month_one_users = set()
    for user, registered_at in registrations.items():
        user_events = [event for event in events if event.get("participant_id") == user]
        if any(_parse_event_time(event) >= registered_at + timedelta(days=7) for event in user_events):
            week_one_users.add(user)
        if any(_parse_event_time(event) >= registered_at + timedelta(days=30) for event in user_events):
            month_one_users.add(user)

    total_registrations = max(1, len(registrations))
    total_onboarded = max(1, len(onboarded_users))
    total_first_training = max(1, len(first_training_users))
    total_week_one = max(1, len(week_one_users))

    started = sum(1 for event in events if event.get("event_type") == "training_started")
    completed = sum(1 for event in events if event.get("event_type") == "training_completed")
    completion_rate = round((completed / started) * 100, 1) if started else 0

    daily_counts = []
    for day_offset in range(29, -1, -1):
        day = now - timedelta(days=day_offset)
        key = _analytics_date_key(day)
        users = {
            event.get("participant_id", "anonymous")
            for event in all_activity
            if _analytics_date_key(_parse_event_time(event)) == key
        }
        daily_counts.append({"date": key, "active_users": len(users)})

    weekday_counts: Dict[str, int] = {}
    hour_counts: Dict[int, int] = {}
    for event in all_activity:
        event_time = _parse_event_time(event)
        weekday = event_time.strftime("%a")
        weekday_counts[weekday] = weekday_counts.get(weekday, 0) + 1
        hour_counts[event_time.hour] = hour_counts.get(event_time.hour, 0) + 1

    weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heatmap = [
        {"day": day, "activity": weekday_counts.get(day, 0)}
        for day in weekday_order
    ]
    active_times = [
        {"hour": _analytics_hour_label(hour), "activity": count}
        for hour, count in sorted(hour_counts.items())
    ]

    session_frequency: Dict[str, int] = {}
    for event in events:
        if event.get("event_type") != "active_learning_session_completed":
            continue
        user = event.get("participant_id", "anonymous")
        session_frequency[user] = session_frequency.get(user, 0) + 1
    frequency_patterns = [
        {"bucket": "1 session", "users": sum(1 for count in session_frequency.values() if count == 1)},
        {"bucket": "2-3 sessions", "users": sum(1 for count in session_frequency.values() if 2 <= count <= 3)},
        {"bucket": "4+ sessions", "users": sum(1 for count in session_frequency.values() if count >= 4)},
    ]

    return {
        "activity": {
            "dau": len(active_since(1)),
            "wau": len(active_since(7)),
            "mau": len(active_since(30)),
            "growth_trend": daily_counts,
        },
        "journey": {
            "registration_to_onboarding": round((len(onboarded_users) / total_registrations) * 100, 1),
            "onboarding_to_first_training": round((len(first_training_users & onboarded_users) / total_onboarded) * 100, 1),
            "first_training_to_week_one": round((len(week_one_users & first_training_users) / total_first_training) * 100, 1),
            "week_one_to_month_one": round((len(month_one_users & week_one_users) / total_week_one) * 100, 1),
        },
        "engagement": {
            "most_active_days": heatmap,
            "most_active_times": active_times,
            "session_frequency_patterns": frequency_patterns,
        },
        "training": {
            "sessions_started": started,
            "sessions_completed": completed,
            "average_completion_rate": completion_rate,
            "drop_off_rate": round(100 - completion_rate, 1),
        },
        "demo_notes": [
            "Seed data is used until analytics_events.json is created.",
            "Firebase can replace participant_id with authenticated user IDs later.",
            "Admin role checks can wrap the /admin and /analytics endpoints when Firebase access is available.",
        ],
    }


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


# ── Active Learning access control ───────────────────────────

@app.get("/active-learning/access/{participant_id}")
async def active_learning_access(participant_id: str):
    try:
        normalized_id = _normalize_participant_id(participant_id)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, normalized_id)
        _save_access_store(store)
        return _serialize_access_record(record)


@app.post("/active-learning/requests")
async def active_learning_request(req: ActiveLearningRequest):
    try:
        participant_id = _normalize_participant_id(req.participant_id)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    now = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, participant_id)
        if record.get("request_status") != "approved":
            record["request_status"] = "pending"
            record["requested_at"] = record.get("requested_at") or now
            record["reviewed_at"] = None
        _save_access_store(store)
        return _serialize_access_record(record)


@app.get("/admin/active-learning/requests")
async def admin_active_learning_requests():
    with _access_lock:
        store = _load_access_store()
        users = store.setdefault("users", {})
        return {
            "users": [
                _serialize_access_record(record)
                for record in sorted(users.values(), key=lambda item: item.get("participant_id", ""))
            ]
        }


@app.post("/admin/active-learning/requests/{participant_id}")
async def admin_active_learning_decision(participant_id: str, req: ActiveLearningDecisionRequest):
    try:
        normalized_id = _normalize_participant_id(participant_id)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    status = req.status.strip().lower()
    if status not in ACTIVE_LEARNING_REQUEST_STATUSES:
        return JSONResponse({"error": "Status must be pending, approved, or rejected."}, status_code=400)

    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, normalized_id)
        record["request_status"] = status
        record["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
        record["enabled"] = status == "approved"
        _save_access_store(store)
        return _serialize_access_record(record)


@app.post("/admin/active-learning/users/{participant_id}/enabled")
async def admin_active_learning_enabled(participant_id: str, req: ActiveLearningEnabledRequest):
    try:
        normalized_id = _normalize_participant_id(participant_id)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    with _access_lock:
        store = _load_access_store()
        record = _get_access_record(store, normalized_id)
        record["enabled"] = bool(req.enabled)
        if req.enabled and record.get("request_status") == "none":
            record["request_status"] = "approved"
            record["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
        _save_access_store(store)
        return _serialize_access_record(record)


# ── Demo analytics ───────────────────────────────────────────

@app.get("/analytics/dashboard")
async def analytics_dashboard():
    with _analytics_lock:
        events = _load_analytics_events()
        if not _analytics_store_path.exists():
            _save_analytics_events(events)
    return _analytics_summary(events)


@app.post("/analytics/events")
async def analytics_event(req: AnalyticsEventRequest):
    event_type = req.event_type.strip()
    if event_type not in ANALYTICS_ALLOWED_EVENTS:
        return JSONResponse({"error": "Unsupported analytics event type."}, status_code=400)
    participant_id = (req.participant_id or "anonymous").strip() or "anonymous"
    _record_analytics_event(event_type, participant_id, req.metadata)
    with _analytics_lock:
        return _analytics_summary(_load_analytics_events())


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
    global _preview_mode, _researcher_notes, _client_camera_mode, _active_learning_participant_id, _daily_session_start_time
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    try:
        participant_id = _normalize_participant_id(req.participant_id)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    access_error = _validate_active_learning_start(participant_id)
    if access_error is not None:
        return access_error

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
    _active_learning_participant_id = participant_id
    _daily_session_start_time = time.time()
    _preview_mode = False  # Now in session mode

    # Extract session_id from info string
    session_id = "unknown"
    if "Session ID:" in info:
        for line in info.strip().split("\n"):
            if "Session ID:" in line:
                session_id = line.split("Session ID:")[-1].strip()
                break

    _record_analytics_event("active_learning_session_started", participant_id, {"session_id": session_id})

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
        "participant_id": participant_id,
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
    global _preview_mode, _client_camera_mode, _active_learning_participant_id, _daily_session_start_time
    if wizard is None:
        return JSONResponse({"error": "Server not ready"}, status_code=503)

    participant_id = _active_learning_participant_id
    elapsed_for_limits = int(max(0, time.time() - _daily_session_start_time)) if _daily_session_start_time else 0
    summary_text, has_data = wizard.stop_session()
    _record_active_learning_session(participant_id, elapsed_for_limits)
    _record_analytics_event(
        "active_learning_session_completed",
        participant_id or "anonymous",
        {"duration_seconds": elapsed_for_limits},
    )
    _active_learning_participant_id = None
    _daily_session_start_time = 0
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
    """Push state to all connected clients at ~30Hz for low-lag pose overlay."""
    global _state_ws_clients
    while True:
        try:
            if wizard and wizard.session_manager.is_active:
                elapsed_for_limits = int(max(0, time.time() - _daily_session_start_time)) if _daily_session_start_time else 0
                if (
                    _active_learning_access_revoked(_active_learning_participant_id)
                    or _daily_limit_reached(_active_learning_participant_id, elapsed_for_limits)
                ):
                    await asyncio.to_thread(_finish_active_learning_session_for_limits)

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
        await asyncio.sleep(1 / 30)


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
        body_landmarks = wizard._latest_body_landmarks
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
        "body_landmarks": body_landmarks,
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
