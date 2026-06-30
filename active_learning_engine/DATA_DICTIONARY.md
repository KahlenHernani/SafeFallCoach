# SafeFall Active Learning — Data Dictionary

**Version:** 1.0
**Date:** 2026-03-25
**Export Format:** JSON summary + Falls CSV + Feedback CSV + Researcher Notes JSON

This document describes every data field captured and exported by the SafeFall Active Learning Engine during participant practice sessions. All participant-facing data is de-identified: NO names, emails, or other PII are collected. Timestamps are relative to session start (seconds) to prevent re-identification through scheduling correlation.

---

## 1. Session Summary (JSON)

**File naming:** `{study_id}_{session_id}_{YYYYMMDD_HHMMSS}.json`

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `study_id` | string | De-identified participant code assigned by researcher | `"P001"` |
| `session_id` | string | Auto-generated unique session identifier (UUID fragment) | `"a1b2c3d4"` |
| `start_time_iso` | string | ISO 8601 wall-clock timestamp of session start (metadata only) | `"2026-03-25T14:30:00+00:00"` |
| `duration_seconds` | integer | Active session duration in seconds (excludes paused time) | `720` |
| `total_falls` | integer | Number of falls detected and recorded during the session | `5` |
| `average_technique_score` | float | Mean technique score across all recorded falls (0–100 scale) | `78.5` |
| `best_technique_score` | integer | Highest technique score achieved in a single fall | `92` |
| `total_feedback_count` | integer | Total number of feedback messages generated (rule-based + AI) | `12` |
| `component_health` | object | Status of each ML component at time of export (see Section 5) | `{"pose_estimator": "ready", ...}` |
| `falls` | array | List of fall event records (see Section 2) | `[...]` |
| `feedback` | array | List of all feedback events (see Section 3) | `[...]` |

---

## 2. Fall Records (CSV + embedded in JSON)

**CSV file naming:** `{study_id}_{session_id}_{YYYYMMDD_HHMMSS}_falls.csv`

| Field | Type | Unit | Description | Example |
|-------|------|------|-------------|---------|
| `study_id` | string | — | De-identified participant code | `"P001"` |
| `session_id` | string | — | Unique session identifier | `"a1b2c3d4"` |
| `relative_timestamp` | float | seconds | Time of fall detection relative to session start | `145.23` |
| `technique_score` | integer | 0–100 | AI-assessed quality score for the fall technique. Higher is better. Based on body positioning, speed of descent, and landing safety. | `78` |
| `feedback` | string | — | AI-generated coaching feedback about the fall technique | `"Good chin tuck. Try bending knees more before descent."` |
| `pose_angles` | JSON string | degrees | Body joint angles at time of fall detection. Keys are joint names (e.g., `knee_l`, `elbow_r`, `hip_l`). Values are angles in degrees. | `{"knee_l": 45.2, "hip_l": 89.1}` |

### Technique Score Interpretation

| Range | Interpretation |
|-------|---------------|
| 90–100 | Excellent technique — safe, controlled fall |
| 70–89 | Good technique — minor corrections needed |
| 50–69 | Fair technique — significant areas for improvement |
| 0–49 | Needs practice — potential injury risk if performed in real scenario |

---

## 3. Feedback Records (CSV + embedded in JSON)

**CSV file naming:** `{study_id}_{session_id}_{YYYYMMDD_HHMMSS}_feedback.csv`

| Field | Type | Unit | Description | Example |
|-------|------|------|-------------|---------|
| `study_id` | string | — | De-identified participant code | `"P001"` |
| `session_id` | string | — | Unique session identifier | `"a1b2c3d4"` |
| `relative_timestamp` | float | seconds | Time of feedback relative to session start | `145.50` |
| `message` | string | — | The coaching feedback text shown to participant | `"FALL DETECTED! Good chin tuck..."` |
| `severity` | string | enum | Feedback severity level (see below) | `"fall"` |
| `pose_score` | integer | 0–100 | Pose quality score at time of feedback | `78` |

### Severity Levels

| Value | Meaning |
|-------|---------|
| `"neutral"` | Informational — no action required |
| `"info"` | Positive reinforcement or general guidance |
| `"warn"` | Correction needed — technique concern |
| `"error"` | Fall detected — post-fall analysis in progress |
| `"fall"` | Fall analysis complete — technique feedback delivered |

---

## 4. Researcher Notes (JSON)

**File naming:** `{study_id}_{session_id}_{YYYYMMDD_HHMMSS}_notes.json`

Notes are entered manually by the researcher during the session via the desktop app's Notes tab. They are observational annotations not shown to the participant.

| Field | Type | Unit | Description | Example |
|-------|------|------|-------------|---------|
| `relative_timestamp` | float | seconds | Time the note was created relative to session start | `200.5` |
| `text` | string | — | Free-text researcher observation | `"Participant hesitated before attempting side fall"` |

---

## 5. Component Health Status

Captured at export time. Documents system state during the session for data quality assessment.

| Component | Possible Values | Description |
|-----------|----------------|-------------|
| `pose_estimator` | `ready`, `placeholder`, `error: <msg>`, `not_initialized` | RTMLib pose estimation model status |
| `fall_detector` | `ready`, `placeholder`, `error: <msg>`, `not_initialized` | SiA fall detection model status |
| `feedback_generator` | `ready`, `error`, `not_initialized` | LLM feedback system status (Ovis2.5-2B or Gemini) |
| `websocket` | `ready`, `error`, `not_initialized` | Mobile app WebSocket server status |
| `camera` | `ready`, `idle`, `disconnected` | USB camera capture status |

### Interpreting Component Health for Data Quality

- If `pose_estimator` = `placeholder`: pose angles will be empty, technique scores are default (70)
- If `fall_detector` = `placeholder`: no falls will be detected (all data is rule-based feedback only)
- If `feedback_generator` = `error`: feedback is rule-based only (no AI-generated coaching text)
- If `camera` = `disconnected` at export: some session time may have been recorded without video

---

## 6. Autosave Recovery File

**File naming:** `{study_id}_{session_id}_autosave.json`

Written every 60 seconds during an active session for crash recovery. Automatically deleted after successful export or discard. Contains the feedback log accumulated so far.

| Field | Type | Description |
|-------|------|-------------|
| `study_id` | string | De-identified participant code |
| `session_id` | string | Unique session identifier |
| `start_time_iso` | string | ISO 8601 session start time |
| `autosave_time_iso` | string | ISO 8601 time of this autosave |
| `feedback_count` | integer | Number of feedback events saved |
| `feedback` | array | Array of feedback records (same schema as Section 3) |

---

## 7. Data Collection Flow

```
Session Start
  → Camera captures video at 30fps
  → RTMLib extracts pose keypoints per frame
  → SiA analyzes 72-frame sliding window for falls
  → On fall detected:
      1. 3 pre-fall + 2 post-fall frames sent to Ovis2.5-2B LLM
      2. LLM generates technique feedback + score
      3. Fall record + feedback recorded
      4. 15-second cooldown before next fall can be detected
  → Researcher can add notes at any time
  → Autosave every 60 seconds
Session End
  → Summary dialog shows stats
  → Researcher exports or discards data
  → Files written to session_data/ directory
```

---

## 8. File Organization

All exports are written to the `session_data/` directory (configurable via `SESSION_DATA_DIR` environment variable).

```
session_data/
├── P001_a1b2c3d4_20260325_143000.json          # Session summary
├── P001_a1b2c3d4_20260325_143000_falls.csv      # Fall events
├── P001_a1b2c3d4_20260325_143000_feedback.csv   # Feedback events
├── P001_a1b2c3d4_20260325_143000_notes.json     # Researcher notes
├── P002_b5c6d7e8_20260325_150000.json           # Another session...
└── ...
```

---

## 9. De-identification Notes

- **No PII collected:** The system does not collect participant names, emails, phone numbers, or any personally identifiable information
- **Study ID:** Assigned by the researcher (e.g., `P001`); mapping to participant identity is maintained separately by the research team
- **Timestamps:** All event timestamps are relative to session start (seconds). The `start_time_iso` field contains wall-clock time for file metadata only
- **No video recording:** The system processes video frames in real-time but does not save video files by default
- **Camera frames sent to LLM:** 5 frames per fall are sent to the local Ovis2.5-2B model for analysis; these frames are not persisted to disk
