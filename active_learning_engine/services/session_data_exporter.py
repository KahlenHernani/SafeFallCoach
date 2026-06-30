"""
Session Data Exporter for IRB Clinical Testing

Framework-agnostic (no Gradio imports). Exports de-identified session data
as JSON + CSV for research use. All timestamps are relative to session start.

Output directory configurable via SESSION_DATA_DIR env var (default: ./session_data).
"""

import csv
import json
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

_UTC = timezone.utc
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class FeedbackRecord:
    """A single feedback event recorded during a session."""
    relative_timestamp: float  # seconds since session start
    message: str
    severity: str
    pose_score: int


@dataclass
class FallExportRecord:
    """A single fall event for export (mirrors SessionManager.FallRecord)."""
    relative_timestamp: float
    technique_score: int
    feedback: str
    pose_angles: Dict[str, float] = field(default_factory=dict)


@dataclass
class SessionExportData:
    """Complete session data for export."""
    study_id: str
    session_id: str
    start_time_iso: str  # wall-clock ISO for file metadata only
    duration_seconds: int
    total_falls: int
    average_technique_score: float
    best_technique_score: int
    total_feedback_count: int
    component_health: Dict[str, str] = field(default_factory=dict)
    falls: List[FallExportRecord] = field(default_factory=list)
    feedback: List[FeedbackRecord] = field(default_factory=list)


class SessionDataExporter:
    """
    Thread-safe session data exporter for IRB clinical testing.

    Records feedback events in real-time, then exports JSON + CSV on
    session end. Autosaves every 60s for crash recovery.
    """

    def __init__(self, output_dir: Optional[str] = None, autosave_interval: float = 60.0):
        """
        Args:
            output_dir: Directory for exports. Defaults to SESSION_DATA_DIR env var
                        or ./session_data.
            autosave_interval: Seconds between autosaves (0 to disable).
        """
        self._output_dir = Path(
            output_dir
            or os.environ.get("SESSION_DATA_DIR", "./session_data")
        )
        self._autosave_interval = autosave_interval

        self._lock = threading.Lock()
        self._study_id: Optional[str] = None
        self._session_id: Optional[str] = None
        self._session_start: float = 0.0
        self._start_time_iso: str = ""
        self._feedback_log: List[FeedbackRecord] = []
        self._active = False

        # Autosave
        self._autosave_timer: Optional[threading.Timer] = None

    def start_session(self, study_id: str, session_id: str,
                      start_time: Optional[float] = None):
        """Begin tracking a new session."""
        with self._lock:
            self._study_id = study_id
            self._session_id = session_id
            self._session_start = start_time or time.time()
            self._start_time_iso = datetime.fromtimestamp(self._session_start, tz=_UTC).isoformat()
            self._feedback_log = []
            self._active = True

        # Ensure output directory exists
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Start autosave timer
        if self._autosave_interval > 0:
            self._schedule_autosave()

    def record_feedback(self, message: str, severity: str, pose_score: int):
        """Append a feedback event with relative timestamp."""
        with self._lock:
            if not self._active:
                return
            relative_ts = time.time() - self._session_start
            self._feedback_log.append(FeedbackRecord(
                relative_timestamp=round(relative_ts, 2),
                message=message,
                severity=severity,
                pose_score=pose_score,
            ))

    def stop_recording(self):
        """Stop recording new feedback without exporting. Data stays in memory."""
        with self._lock:
            self._active = False
            self._cancel_autosave()

    def discard(self):
        """Discard all collected session data without writing any files."""
        with self._lock:
            self._active = False
            self._cancel_autosave()
            autosave_path = (
                self._output_dir / f"{self._study_id}_{self._session_id}_autosave.json"
                if self._study_id and self._session_id else None
            )
            self._feedback_log = []
            self._study_id = None
            self._session_id = None

        if autosave_path and autosave_path.exists():
            try:
                autosave_path.unlink()
            except Exception:
                pass

    def export_session(self, stats, component_health: Optional[Dict[str, str]] = None
                       ) -> Dict[str, str]:
        """
        Export session data to JSON + CSVs.

        Args:
            stats: SessionStats from SessionManager (has fall_records, totals, etc.)
            component_health: Dict of component name → status string

        Returns:
            Dict of {'json': path, 'falls_csv': path, 'feedback_csv': path}
        """
        with self._lock:
            self._active = False
            self._cancel_autosave()

            if not self._study_id or not self._session_id:
                return {}

            # Build export data
            session_start = self._session_start
            falls = []
            for fr in stats.fall_records:
                falls.append(FallExportRecord(
                    relative_timestamp=round(fr.timestamp - session_start, 2),
                    technique_score=fr.technique_score,
                    feedback=fr.feedback,
                    pose_angles=fr.pose_angles,
                ))

            export = SessionExportData(
                study_id=self._study_id,
                session_id=self._session_id,
                start_time_iso=self._start_time_iso,
                duration_seconds=stats.duration_seconds,
                total_falls=stats.total_falls,
                average_technique_score=round(stats.average_technique_score, 1),
                best_technique_score=stats.best_technique_score,
                total_feedback_count=stats.total_feedback_count,
                component_health=component_health or {},
                falls=falls,
                feedback=list(self._feedback_log),
            )

            # Generate file paths
            ts_str = datetime.fromtimestamp(session_start, tz=_UTC).strftime("%Y%m%d_%H%M%S")
            base = f"{self._study_id}_{self._session_id}_{ts_str}"

            json_path = self._output_dir / f"{base}.json"
            falls_csv_path = self._output_dir / f"{base}_falls.csv"
            feedback_csv_path = self._output_dir / f"{base}_feedback.csv"

            # Write JSON
            json_path.write_text(json.dumps(asdict(export), indent=2, default=str))

            # Write falls CSV
            with open(falls_csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "study_id", "session_id", "relative_timestamp",
                    "technique_score", "feedback", "pose_angles"
                ])
                for fall in falls:
                    writer.writerow([
                        self._study_id, self._session_id,
                        fall.relative_timestamp, fall.technique_score,
                        fall.feedback, json.dumps(fall.pose_angles),
                    ])

            # Write feedback CSV
            with open(feedback_csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "study_id", "session_id", "relative_timestamp",
                    "message", "severity", "pose_score"
                ])
                for fb in self._feedback_log:
                    writer.writerow([
                        self._study_id, self._session_id,
                        fb.relative_timestamp, fb.message,
                        fb.severity, fb.pose_score,
                    ])

            # Remove autosave file if it exists
            autosave_path = self._output_dir / f"{self._study_id}_{self._session_id}_autosave.json"
            if autosave_path.exists():
                autosave_path.unlink()

            return {
                "json": str(json_path),
                "falls_csv": str(falls_csv_path),
                "feedback_csv": str(feedback_csv_path),
            }

    def _autosave(self):
        """Write current feedback log to an autosave JSON file."""
        with self._lock:
            if not self._active or not self._study_id:
                return

            autosave_path = self._output_dir / f"{self._study_id}_{self._session_id}_autosave.json"
            data = {
                "study_id": self._study_id,
                "session_id": self._session_id,
                "start_time_iso": self._start_time_iso,
                "autosave_time_iso": datetime.now(tz=_UTC).isoformat(),
                "feedback_count": len(self._feedback_log),
                "feedback": [asdict(fb) for fb in self._feedback_log],
            }

        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            autosave_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            print(f"[DataExporter] Autosave failed: {e}")

        # Schedule next autosave
        if self._active:
            self._schedule_autosave()

    def _schedule_autosave(self):
        """Schedule the next autosave."""
        self._cancel_autosave()
        self._autosave_timer = threading.Timer(self._autosave_interval, self._autosave)
        self._autosave_timer.daemon = True
        self._autosave_timer.start()

    def _cancel_autosave(self):
        """Cancel pending autosave timer."""
        if self._autosave_timer:
            self._autosave_timer.cancel()
            self._autosave_timer = None

    @property
    def is_active(self) -> bool:
        return self._active
