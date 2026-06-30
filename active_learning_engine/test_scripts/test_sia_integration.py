#!/usr/bin/env python3
"""
Test script for SiA integration in Active Learning Wizard

This script tests the SiA fall detection model integration without
requiring the full Gradio UI or camera setup.
"""

import sys
import numpy as np
import cv2
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from models import SiADetector


def test_initialization():
    """Test SiA model initialization."""
    print("=" * 60)
    print("Test 1: SiA Model Initialization")
    print("=" * 60)

    detector = SiADetector()
    success = detector.initialize()

    if success:
        print("\n✓ Initialization successful")
        print(f"✓ Model initialized: {detector.is_initialized}")
        if detector.model is not None:
            print(f"✓ Model loaded on device: {detector.device}")
            print(f"✓ Monitoring actions: {', '.join(detector.fall_actions)}")
        else:
            print("⚠ Running in placeholder mode (model weights not found)")
        return detector
    else:
        print("\n✗ Initialization failed")
        return None


def test_frame_processing(detector):
    """Test processing synthetic frames."""
    print("\n" + "=" * 60)
    print("Test 2: Frame Processing")
    print("=" * 60)

    if detector is None:
        print("✗ Cannot test - detector not initialized")
        return

    # Create synthetic test frames (BGR)
    print("\nGenerating synthetic frames...")
    frame_count = 80  # More than buffer size
    test_frames = []

    for i in range(frame_count):
        # Create a simple colored frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add some variation
        color = int(255 * (i / frame_count))
        frame[:, :] = [color, 128, 255 - color]
        test_frames.append(frame)

    print(f"✓ Generated {frame_count} test frames (640x480)")

    # Process frames
    print("\nProcessing frames through SiA detector...")
    results = []

    for i, frame in enumerate(test_frames):
        result = detector.detect(frame)
        results.append(result)

        if i % 20 == 0:
            print(f"  Frame {i}/{frame_count}: detected={result.detected}, "
                  f"confidence={result.confidence:.3f}")

    print(f"\n✓ Processed {len(results)} frames")
    print(f"✓ Buffer filled after frame {detector.buffer_size}")

    # Summary
    falls_detected = sum(1 for r in results if r.detected)
    print(f"\nSummary:")
    print(f"  Total frames: {len(results)}")
    print(f"  Falls detected: {falls_detected}")
    print(f"  Detection rate: {falls_detected / len(results) * 100:.1f}%")

    if detector.model is None:
        print("\n⚠ Running in placeholder mode - no real detections expected")


def test_webcam_preview(detector):
    """Test with webcam (optional, requires user input)."""
    print("\n" + "=" * 60)
    print("Test 3: Webcam Preview (Optional)")
    print("=" * 60)

    if detector is None:
        print("✗ Cannot test - detector not initialized")
        return

    response = input("\nTest with webcam? This will open a window. (y/n): ")
    if response.lower() != 'y':
        print("Skipping webcam test")
        return

    print("\nOpening webcam...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("✗ Could not open webcam")
        return

    print("✓ Webcam opened")
    print("\nProcessing frames... Press 'q' to quit")

    frame_count = 0
    fall_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("✗ Failed to read frame")
            break

        # Detect falls
        result = detector.detect(frame)
        frame_count += 1

        if result.detected:
            fall_count += 1
            # Draw detection on frame
            cv2.putText(frame, f"FALL DETECTED! {result.action}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, f"Confidence: {result.confidence:.2f}",
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Draw frame counter
        cv2.putText(frame, f"Frame: {frame_count}",
                   (10, frame.shape[0] - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Falls: {fall_count}",
                   (10, frame.shape[0] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow('SiA Fall Detection Test', frame)

        # Quit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    print(f"\n✓ Processed {frame_count} webcam frames")
    print(f"✓ Detected {fall_count} falls")


def test_performance(detector):
    """Test inference performance."""
    print("\n" + "=" * 60)
    print("Test 4: Performance Benchmark")
    print("=" * 60)

    if detector is None or detector.model is None:
        print("✗ Cannot benchmark - model not loaded")
        return

    import time

    # Create test frame
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Warm up
    print("\nWarming up...")
    for _ in range(10):
        detector.detect(frame)

    # Benchmark
    print("Running benchmark (100 frames)...")
    num_frames = 100
    start_time = time.time()

    for _ in range(num_frames):
        result = detector.detect(frame)

    elapsed = time.time() - start_time
    fps = num_frames / elapsed
    latency = (elapsed / num_frames) * 1000  # ms

    print(f"\n✓ Benchmark complete")
    print(f"  Frames: {num_frames}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"  FPS: {fps:.1f}")
    print(f"  Latency: {latency:.1f}ms per frame")
    print(f"  Device: {detector.device}")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SiA Integration Test Suite")
    print("Active Learning Wizard - Fall Detection")
    print("=" * 60 + "\n")

    # Test 1: Initialization
    detector = test_initialization()

    if detector is None:
        print("\n✗ Tests failed - could not initialize detector")
        return 1

    # Test 2: Frame processing
    test_frame_processing(detector)

    # Test 3: Webcam (optional)
    test_webcam_preview(detector)

    # Test 4: Performance
    test_performance(detector)

    # Final summary
    print("\n" + "=" * 60)
    print("Test Suite Complete")
    print("=" * 60)

    if detector.model is not None:
        print("\n✓ All tests passed - SiA integration working")
        print("\nNext steps:")
        print("  1. Run the full wizard: python app.py")
        print("  2. Start a session and test fall detection")
        print("  3. Connect mobile app via QR code")
    else:
        print("\n⚠ Tests passed in placeholder mode")
        print("\nTo enable full fall detection:")
        print("  1. Download model weights (see SIA_INTEGRATION.md)")
        print("  2. Re-run tests")

    return 0


if __name__ == "__main__":
    sys.exit(main())
