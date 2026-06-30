"""Tests for SessionDataExporter — JSON/CSV export, relative timestamps, autosave."""

import csv
import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

# Import the module directly to avoid pulling in the full services package
# (which requires PIL/qrcode that may not be installed in test environments)
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from session_data_exporter import SessionDataExporter


# Minimal stub matching SessionManager.SessionStats / FallRecord interface
@dataclass
class FallRecord:
    timestamp: float
    technique_score: int
    feedback: str
    pose_angles: Dict[str, float] = field(default_factory=dict)


@dataclass
class FakeStats:
    duration_seconds: int = 120
    total_falls: int = 0
    average_technique_score: float = 0.0
    best_technique_score: int = 0
    total_feedback_count: int = 0
    fall_records: List[FallRecord] = field(default_factory=list)


class TestSessionDataExporter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.exporter = SessionDataExporter(
            output_dir=self.tmpdir, autosave_interval=0  # disable autosave for tests
        )

    def test_basic_export_creates_files(self):
        """Export should create JSON + 2 CSV files."""
        self.exporter.start_session("P001", "sess123", start_time=1000000.0)
        self.exporter.record_feedback("Good form!", "success", 85)
        self.exporter.record_feedback("Tuck your chin", "warning", 60)

        stats = FakeStats(
            duration_seconds=120,
            total_falls=1,
            average_technique_score=75.0,
            best_technique_score=75,
            total_feedback_count=2,
            fall_records=[
                FallRecord(
                    timestamp=1000045.0,
                    technique_score=75,
                    feedback="Keep arms bent",
                    pose_angles={"left_elbow": 140.5},
                )
            ],
        )

        paths = self.exporter.export_session(stats, {"camera": "ready"})

        self.assertIn("json", paths)
        self.assertIn("falls_csv", paths)
        self.assertIn("feedback_csv", paths)

        for key, path in paths.items():
            self.assertTrue(os.path.exists(path), f"{key} file missing: {path}")

    def test_json_contains_study_id_and_relative_timestamps(self):
        """JSON should use study ID and relative (not wall-clock) timestamps."""
        start = 1000000.0
        self.exporter.start_session("P002", "s1", start_time=start)
        self.exporter.record_feedback("msg1", "info", 70)

        stats = FakeStats(
            duration_seconds=60,
            total_falls=1,
            fall_records=[
                FallRecord(timestamp=start + 30.0, technique_score=80,
                           feedback="Nice", pose_angles={})
            ],
        )
        paths = self.exporter.export_session(stats)

        with open(paths["json"]) as f:
            data = json.load(f)

        self.assertEqual(data["study_id"], "P002")
        self.assertEqual(data["session_id"], "s1")
        # Fall timestamp should be relative (30.0), not absolute
        self.assertAlmostEqual(data["falls"][0]["relative_timestamp"], 30.0, places=1)

    def test_feedback_csv_is_valid(self):
        """Feedback CSV should have correct headers and rows."""
        self.exporter.start_session("P003", "s2", start_time=1000000.0)
        self.exporter.record_feedback("first", "info", 50)
        self.exporter.record_feedback("second", "warning", 60)

        stats = FakeStats(total_feedback_count=2)
        paths = self.exporter.export_session(stats)

        with open(paths["feedback_csv"], newline="") as f:
            reader = list(csv.reader(f))

        self.assertEqual(reader[0], [
            "study_id", "session_id", "relative_timestamp",
            "message", "severity", "pose_score",
        ])
        self.assertEqual(len(reader), 3)  # header + 2 rows
        self.assertEqual(reader[1][0], "P003")  # study_id in first column
        self.assertEqual(reader[1][3], "first")  # message

    def test_falls_csv_is_valid(self):
        """Falls CSV should include pose_angles as JSON string."""
        start = 1000000.0
        self.exporter.start_session("P004", "s3", start_time=start)

        stats = FakeStats(
            total_falls=1,
            fall_records=[
                FallRecord(timestamp=start + 10.0, technique_score=65,
                           feedback="bend knees", pose_angles={"left_knee": 170.0})
            ],
        )
        paths = self.exporter.export_session(stats)

        with open(paths["falls_csv"], newline="") as f:
            reader = list(csv.reader(f))

        self.assertEqual(len(reader), 2)  # header + 1 fall
        pose_angles = json.loads(reader[1][5])  # last column
        self.assertAlmostEqual(pose_angles["left_knee"], 170.0)

    def test_autosave_creates_file(self):
        """Autosave should write a partial JSON file."""
        exporter = SessionDataExporter(output_dir=self.tmpdir, autosave_interval=0.1)
        exporter.start_session("P005", "s4", start_time=1000000.0)
        exporter.record_feedback("test", "info", 50)

        # Wait for autosave to fire
        time.sleep(0.3)

        autosave_path = Path(self.tmpdir) / "P005_s4_autosave.json"
        self.assertTrue(autosave_path.exists(), "Autosave file not created")

        with open(autosave_path) as f:
            data = json.load(f)
        self.assertEqual(data["study_id"], "P005")
        self.assertEqual(data["feedback_count"], 1)

        # Clean up: export session removes autosave
        paths = exporter.export_session(FakeStats())
        self.assertFalse(autosave_path.exists(), "Autosave should be removed after export")

    def test_no_export_without_start(self):
        """Export without start_session should return empty dict."""
        result = self.exporter.export_session(FakeStats())
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
