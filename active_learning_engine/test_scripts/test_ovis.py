"""
Quick test script for Ovis2.5-2B on NVIDIA GPU.
Run: python test_ovis.py
"""
import time
import sys
from pathlib import Path
import numpy as np
import torch

# Add project root to path so llm_providers is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_gpu_info():
    """Step 1: Check GPU and CUDA availability."""
    print("=" * 60)
    print("STEP 1: GPU Info")
    print("=" * 60)
    try:
        import torch
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"Total VRAM: {total:.2f} GB")
            cap = torch.cuda.get_device_capability(0)
            print(f"Compute capability: {cap[0]}.{cap[1]}")
            print(f"bfloat16 support: {'Yes' if cap[0] >= 8 else 'No'}")
        else:
            print("ERROR: No CUDA GPU detected. Cannot test Ovis.")
            sys.exit(1)
    except ImportError:
        print("ERROR: PyTorch not installed. Run: pip install torch --index-url " \
        "       https://download.pytorch.org/whl/cu121")
        sys.exit(1)
    print()


def test_initialize():
    """Step 2: Initialize OvisProvider (downloads model on first run)."""
    print("=" * 60)
    print("STEP 2: Initialize OvisProvider")
    print("=" * 60)
    from llm_providers import OvisProvider

    provider = OvisProvider()
    start = time.time()
    success = provider.initialize()
    elapsed = time.time() - start

    print(f"Initialize result: {'SUCCESS' if success else 'FAILED'}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Mode: {provider.name}")
    if not success:
        print("ERROR: OvisProvider failed to initialize.")
        sys.exit(1)
    print()
    return provider


def test_text_only(provider):
    """Step 3: Test text-only feedback (no images)."""
    print("=" * 60)
    print("STEP 3: Text-only feedback (no frames)")
    print("=" * 60)
    pose_angles = {
        "left_knee": 45.0,
        "right_knee": 50.0,
        "trunk_lean": 15.0,
        "chin_tuck": 20.0,
    }

    start = time.time()
    result = provider.generate_feedback(
        pose_angles=pose_angles,
        technique_score=65,
        fall_detected=True,
        frames=None,
    )
    elapsed = time.time() - start

    if result:
        print(f"Severity: {result.severity}")
        print(f"Score: {result.pose_score}")
        print(f"Message: {result.message}")
        print(f"Inference time: {elapsed:.2f}s")
    else:
        print("WARNING: No result returned (model may have errored)")
    print()
    return result


def test_with_frames(provider):
    """Step 4: Test with synthetic image frames (simulates real usage)."""
    print("=" * 60)
    print("STEP 4: Feedback with 5 synthetic frames")
    print("=" * 60)
    # Create 5 dummy 480x640 BGR frames (like webcam captures)
    frames = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(5)]
    print(f"Created {len(frames)} synthetic frames (480x640 BGR)")

    pose_angles = {
        "left_knee": 30.0,
        "right_knee": 35.0,
        "trunk_lean": 25.0,
        "chin_tuck": 10.0,
    }

    start = time.time()
    result = provider.generate_feedback(
        pose_angles=pose_angles,
        technique_score=45,
        fall_detected=True,
        frames=frames,
    )
    elapsed = time.time() - start

    if result:
        print(f"Severity: {result.severity}")
        print(f"Score: {result.pose_score}")
        print(f"Message: {result.message}")
        print(f"Inference time: {elapsed:.2f}s")
    else:
        print("WARNING: No result returned")
    print()
    return result


def test_vram_usage():
    """Step 5: Report final VRAM usage."""
    print("=" * 60)
    print("STEP 5: VRAM Usage")
    print("=" * 60)
    import torch
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"Allocated: {allocated:.2f} GB")
        print(f"Reserved:  {reserved:.2f} GB")
        print(f"Total:     {total:.2f} GB")
        print(f"Usage:     {allocated / total * 100:.1f}%")
    print()


def test_unload(provider):
    """Step 6: Test unloading (for lazy mode verification)."""
    print("=" * 60)
    print("STEP 6: Unload model")
    print("=" * 60)
    import torch
    before = torch.cuda.memory_allocated() / 1024**3
    provider.unload_model()
    after = torch.cuda.memory_allocated() / 1024**3
    print(f"VRAM before: {before:.2f} GB")
    print(f"VRAM after:  {after:.2f} GB")
    print(f"Freed:       {before - after:.2f} GB")
    print()


if __name__ == "__main__":
    print(f"\n*** Ovis2.5-2B Test on {torch.cuda.get_device_name(0)} ***\n")

    test_gpu_info()
    provider = test_initialize()
    test_text_only(provider)
    test_with_frames(provider)
    test_vram_usage()
    test_unload(provider)

    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
