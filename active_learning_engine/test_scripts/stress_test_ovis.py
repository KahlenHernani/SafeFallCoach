"""
Comprehensive stress tests for Ovis2.5-2B on high VRAM GPUs (16GB+).
Tests throughput, memory limits, concurrent processing, and edge cases.

Run: python stress_test_ovis.py [--test <test_name>]

Available tests:
  all           - Run all tests (default)
  batch         - Batch processing (multiple fall events)
  frames        - Large frame counts (5, 10, 20, 50, 100)
  resolution    - High-resolution frames (720p, 1080p, 4K)
  concurrent    - Parallel inference requests
  continuous    - Extended runtime (memory leak detection)
  throughput    - Measure max frames/second
  memory_limit  - Find VRAM ceiling
"""
import time
import sys
import argparse
from pathlib import Path
import numpy as np
import torch
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Add project root to path so llm_providers is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class StressTestRunner:
    """Orchestrates Ovis stress tests."""

    def __init__(self):
        self.provider = None
        self.results = {}
        self.print_lock = Lock()

    def setup(self):
        """Initialize OvisProvider."""
        print("=" * 80)
        print("SETUP: Initializing Ovis2.5-2B")
        print("=" * 80)
        from llm_providers import OvisProvider

        self.provider = OvisProvider()
        if not self.provider.initialize():
            print("ERROR: Failed to initialize OvisProvider")
            sys.exit(1)

        print(f"Mode: {self.provider.name}")
        print(f"VRAM: {torch.cuda.memory_allocated() / 1024**3:.2f} GB allocated")
        print()

    def _create_frames(self, count, height=480, width=640):
        """Generate synthetic BGR frames."""
        return [np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
                for _ in range(count)]

    def _print_result(self, test_name, metric, value, unit=""):
        """Thread-safe result printing."""
        with self.print_lock:
            print(f"  {metric:30s}: {value:8.2f} {unit}")
            self.results[f"{test_name}_{metric}"] = value

    # ============================================================================
    # TEST 1: Batch Processing (Multiple Fall Events)
    # ============================================================================
    def test_batch_processing(self, batch_sizes=[1, 5, 10, 20]):
        """Process multiple fall events sequentially."""
        print("=" * 80)
        print("TEST 1: Batch Processing (Sequential Fall Events)")
        print("=" * 80)
        print("Simulates processing a queue of fall detection events.\n")

        for batch_size in batch_sizes:
            print(f"Batch size: {batch_size} events")
            frames_per_event = 5

            start_time = time.time()
            vram_peak = 0

            for i in range(batch_size):
                frames = self._create_frames(frames_per_event)
                pose_angles = {
                    "left_knee": np.random.uniform(20, 60),
                    "right_knee": np.random.uniform(20, 60),
                    "trunk_lean": np.random.uniform(10, 30),
                    "chin_tuck": np.random.uniform(5, 25),
                }

                result = self.provider.generate_feedback(
                    pose_angles=pose_angles,
                    technique_score=np.random.randint(30, 80),
                    fall_detected=True,
                    frames=frames,
                )

                vram = torch.cuda.memory_allocated() / 1024**3
                vram_peak = max(vram_peak, vram)

            elapsed = time.time() - start_time
            events_per_sec = batch_size / elapsed

            self._print_result("batch", f"batch_{batch_size}_time", elapsed, "s")
            self._print_result("batch", f"batch_{batch_size}_throughput", events_per_sec, "events/s")
            self._print_result("batch", f"batch_{batch_size}_vram_peak", vram_peak, "GB")
            print()

    # ============================================================================
    # TEST 2: Large Frame Counts
    # ============================================================================
    def test_large_frame_counts(self, frame_counts=[5, 10, 20, 50, 100]):
        """Test inference with increasing frame counts."""
        print("=" * 80)
        print("TEST 2: Large Frame Counts")
        print("=" * 80)
        print("Measures inference time and VRAM scaling with frame count.\n")

        pose_angles = {
            "left_knee": 35.0,
            "right_knee": 40.0,
            "trunk_lean": 20.0,
            "chin_tuck": 15.0,
        }

        for count in frame_counts:
            print(f"Frame count: {count}")
            frames = self._create_frames(count)

            torch.cuda.reset_peak_memory_stats()
            start_time = time.time()

            result = self.provider.generate_feedback(
                pose_angles=pose_angles,
                technique_score=55,
                fall_detected=True,
                frames=frames,
            )

            elapsed = time.time() - start_time
            vram_peak = torch.cuda.max_memory_allocated() / 1024**3

            self._print_result("frames", f"frames_{count}_time", elapsed, "s")
            self._print_result("frames", f"frames_{count}_vram", vram_peak, "GB")
            if result:
                print(f"  Output length: {len(result.message)} chars")
            print()

    # ============================================================================
    # TEST 3: High Resolution Frames
    # ============================================================================
    def test_high_resolution(self, resolutions=[
        (480, 640, "VGA"),
        (720, 1280, "720p"),
        (1080, 1920, "1080p"),
        (2160, 3840, "4K"),
    ]):
        """Test with different frame resolutions."""
        print("=" * 80)
        print("TEST 3: High Resolution Frames")
        print("=" * 80)
        print("Tests VRAM impact of high-resolution inputs.\n")

        frame_count = 5
        pose_angles = {
            "left_knee": 35.0,
            "right_knee": 40.0,
            "trunk_lean": 20.0,
            "chin_tuck": 15.0,
        }

        for height, width, label in resolutions:
            print(f"Resolution: {label} ({height}x{width})")
            frames = self._create_frames(frame_count, height, width)

            torch.cuda.reset_peak_memory_stats()
            start_time = time.time()

            try:
                result = self.provider.generate_feedback(
                    pose_angles=pose_angles,
                    technique_score=55,
                    fall_detected=True,
                    frames=frames,
                )

                elapsed = time.time() - start_time
                vram_peak = torch.cuda.max_memory_allocated() / 1024**3

                self._print_result("resolution", f"res_{label}_time", elapsed, "s")
                self._print_result("resolution", f"res_{label}_vram", vram_peak, "GB")
                print(f"  Status: SUCCESS")
            except RuntimeError as e:
                print(f"  Status: FAILED ({str(e)[:50]}...)")
            print()

    # ============================================================================
    # TEST 4: Concurrent Inference
    # ============================================================================
    def test_concurrent_inference(self, num_workers=[2, 4, 8]):
        """Test parallel inference requests (if model supports threading)."""
        print("=" * 80)
        print("TEST 4: Concurrent Inference")
        print("=" * 80)
        print("Tests multi-threaded inference (if supported by model).\n")
        print("WARNING: Ovis may not support true parallelism (GIL + model lock).")
        print("This tests overhead and potential speedup.\n")

        def run_inference(worker_id, num_inferences=3):
            """Worker function for concurrent testing."""
            frames = self._create_frames(5)
            pose_angles = {
                "left_knee": 35.0,
                "right_knee": 40.0,
                "trunk_lean": 20.0,
                "chin_tuck": 15.0,
            }

            for i in range(num_inferences):
                result = self.provider.generate_feedback(
                    pose_angles=pose_angles,
                    technique_score=55,
                    fall_detected=True,
                    frames=frames,
                )

            return worker_id

        for workers in num_workers:
            print(f"Workers: {workers} (3 inferences each = {workers * 3} total)")

            start_time = time.time()
            torch.cuda.reset_peak_memory_stats()

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(run_inference, i) for i in range(workers)]
                for future in as_completed(futures):
                    future.result()

            elapsed = time.time() - start_time
            vram_peak = torch.cuda.max_memory_allocated() / 1024**3
            throughput = (workers * 3) / elapsed

            self._print_result("concurrent", f"workers_{workers}_time", elapsed, "s")
            self._print_result("concurrent", f"workers_{workers}_throughput", throughput, "infer/s")
            self._print_result("concurrent", f"workers_{workers}_vram", vram_peak, "GB")
            print()

    # ============================================================================
    # TEST 5: Continuous Operation (Memory Leak Detection)
    # ============================================================================
    def test_continuous_operation(self, duration_minutes=5, interval_sec=10):
        """Run continuous inference to detect memory leaks."""
        print("=" * 80)
        print(f"TEST 5: Continuous Operation ({duration_minutes} min)")
        print("=" * 80)
        print("Monitors VRAM over time to detect memory leaks.\n")

        end_time = time.time() + (duration_minutes * 60)
        iteration = 0
        vram_samples = []

        print(f"{'Time':<8} {'Iter':<6} {'VRAM (GB)':<12} {'Allocated':<12} {'Reserved':<12}")
        print("-" * 80)

        while time.time() < end_time:
            frames = self._create_frames(5)
            pose_angles = {
                "left_knee": np.random.uniform(20, 60),
                "right_knee": np.random.uniform(20, 60),
                "trunk_lean": np.random.uniform(10, 30),
                "chin_tuck": np.random.uniform(5, 25),
            }

            result = self.provider.generate_feedback(
                pose_angles=pose_angles,
                technique_score=np.random.randint(30, 80),
                fall_detected=True,
                frames=frames,
            )

            iteration += 1
            vram_alloc = torch.cuda.memory_allocated() / 1024**3
            vram_res = torch.cuda.memory_reserved() / 1024**3
            vram_samples.append(vram_alloc)

            elapsed = int(time.time() - (end_time - duration_minutes * 60))
            print(f"{elapsed:6d}s {iteration:<6d} {vram_alloc:>8.2f} GB   "
                  f"{vram_alloc:>8.2f} GB   {vram_res:>8.2f} GB")

            time.sleep(interval_sec)

        print()
        vram_mean = np.mean(vram_samples)
        vram_std = np.std(vram_samples)
        vram_min = np.min(vram_samples)
        vram_max = np.max(vram_samples)
        vram_drift = vram_max - vram_min

        self._print_result("continuous", "iterations", iteration, "")
        self._print_result("continuous", "vram_mean", vram_mean, "GB")
        self._print_result("continuous", "vram_std", vram_std, "GB")
        self._print_result("continuous", "vram_drift", vram_drift, "GB")
        print(f"  Memory leak: {'DETECTED' if vram_drift > 1.0 else 'None detected'}")
        print()

    # ============================================================================
    # TEST 6: Throughput Benchmark
    # ============================================================================
    def test_throughput(self, test_duration_sec=60):
        """Measure maximum throughput (inferences/sec)."""
        print("=" * 80)
        print(f"TEST 6: Throughput Benchmark ({test_duration_sec}s)")
        print("=" * 80)
        print("Measures max sustained inference rate.\n")

        frames = self._create_frames(5)
        pose_angles = {
            "left_knee": 35.0,
            "right_knee": 40.0,
            "trunk_lean": 20.0,
            "chin_tuck": 15.0,
        }

        end_time = time.time() + test_duration_sec
        count = 0
        times = []

        while time.time() < end_time:
            start = time.time()
            result = self.provider.generate_feedback(
                pose_angles=pose_angles,
                technique_score=55,
                fall_detected=True,
                frames=frames,
            )
            elapsed = time.time() - start
            times.append(elapsed)
            count += 1

        total_time = sum(times)
        throughput = count / total_time
        mean_latency = np.mean(times)
        p50 = np.percentile(times, 50)
        p95 = np.percentile(times, 95)
        p99 = np.percentile(times, 99)

        print(f"Completed {count} inferences in {total_time:.1f}s")
        self._print_result("throughput", "inferences_per_sec", throughput, "infer/s")
        self._print_result("throughput", "mean_latency", mean_latency, "s")
        self._print_result("throughput", "p50_latency", p50, "s")
        self._print_result("throughput", "p95_latency", p95, "s")
        self._print_result("throughput", "p99_latency", p99, "s")
        print()

    # ============================================================================
    # TEST 7: Memory Limit (Find VRAM Ceiling)
    # ============================================================================
    def test_memory_limit(self):
        """Find max frame count before OOM."""
        print("=" * 80)
        print("TEST 7: Memory Limit (VRAM Ceiling)")
        print("=" * 80)
        print("Increases frame count until OOM error.\n")

        pose_angles = {
            "left_knee": 35.0,
            "right_knee": 40.0,
            "trunk_lean": 20.0,
            "chin_tuck": 15.0,
        }

        max_frames = 5
        step = 20

        while True:
            frames = self._create_frames(max_frames)
            print(f"Testing {max_frames} frames... ", end="", flush=True)

            torch.cuda.reset_peak_memory_stats()
            try:
                result = self.provider.generate_feedback(
                    pose_angles=pose_angles,
                    technique_score=55,
                    fall_detected=True,
                    frames=frames,
                )
                vram = torch.cuda.max_memory_allocated() / 1024**3
                print(f"SUCCESS ({vram:.2f} GB)")
                max_frames += step
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    print(f"OOM (limit reached)")
                    self._print_result("memory_limit", "max_frames", max_frames - step, "frames")
                    break
                else:
                    print(f"ERROR: {e}")
                    break

        print()

    # ============================================================================
    # Run Tests
    # ============================================================================
    def run(self, test_names=None):
        """Run specified tests (or all if None)."""
        self.setup()

        test_map = {
            "batch": self.test_batch_processing,
            "frames": self.test_large_frame_counts,
            "resolution": self.test_high_resolution,
            "concurrent": self.test_concurrent_inference,
            "continuous": self.test_continuous_operation,
            "throughput": self.test_throughput,
            "memory_limit": self.test_memory_limit,
        }

        if test_names is None or "all" in test_names:
            test_names = list(test_map.keys())

        for test_name in test_names:
            if test_name in test_map:
                test_map[test_name]()
            else:
                print(f"WARNING: Unknown test '{test_name}', skipping.")

        print("=" * 80)
        print("ALL STRESS TESTS COMPLETE")
        print("=" * 80)
        print(f"Final VRAM: {torch.cuda.memory_allocated() / 1024**3:.2f} GB allocated")
        print()

        return self.results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress test Ovis2.5-2B on high VRAM GPUs")
    parser.add_argument(
        "--test",
        nargs="+",
        default=["all"],
        help="Tests to run (default: all). Options: batch, frames, resolution, "
             "concurrent, continuous, throughput, memory_limit, all",
    )
    args = parser.parse_args()

    print("\n*** Ovis2.5-2B Stress Tests (RTX 4090) ***\n")

    # Check GPU
    if not torch.cuda.is_available():
        print("ERROR: No CUDA GPU detected. Cannot run stress tests.")
        sys.exit(1)

    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Total VRAM: {total:.2f} GB\n")

    runner = StressTestRunner()
    results = runner.run(args.test)
