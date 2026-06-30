#!/usr/bin/env python3
"""
Test script to verify all bug fixes without requiring GPU dependencies.
"""

import ast
import re

def test_llm_provider_fixes():
    """Test that all llm_provider.py fixes are in place."""
    print("Testing llm_provider.py fixes...")

    with open('models/llm_provider.py', 'r') as f:
        content = f.read()

    fixes = {
        '_vram_threshold_gb': content.count('_vram_threshold_gb') >= 2,
        '_dependencies_available': '_dependies_available' not in content,
        '_persistent_mode': '_persistent_mmode' not in content,
        'pose_angles.items()': 'pose_angles.items()' in content and 'pose_angles.item()' not in content,
        'detected (not deteced)': 'deteced' not in content,
        'environment (not eviroment)': 'eviroment' not in content,
        'proximity (not proximinity)': 'proximinity' not in content,
    }

    passed = all(fixes.values())
    for fix, status in fixes.items():
        symbol = '✓' if status else '✗'
        print(f"  {symbol} {fix}")

    return passed


def test_sia_detector_fixes():
    """Test that sia_detector.py buffer fix is in place."""
    print("\nTesting sia_detector.py fixes...")

    with open('models/sia_detector.py', 'r') as f:
        content = f.read()

    # Check for the correct buffer condition
    correct = 'if len(self.buffer) < self.buffer_size:' in content
    incorrect = 'if len(self.buffer) <= self.buffer_size:' in content

    passed = correct and not incorrect
    symbol = '✓' if passed else '✗'
    print(f"  {symbol} Buffer boundary condition fixed (< instead of <=)")

    return passed


def test_feedback_generator_fixes():
    """Test that feedback_generator.py fixes are in place."""
    print("\nTesting feedback_generator.py fixes...")

    with open('models/feedback_generator.py', 'r') as f:
        content = f.read()

    fixes = {
        'pose_score parameter added': 'pose_score = technique_score,' in content,
        '_get_fall_suggestion method exists': 'def _get_fall_suggestion' in content,
    }

    passed = all(fixes.values())
    for fix, status in fixes.items():
        symbol = '✓' if status else '✗'
        print(f"  {symbol} {fix}")

    return passed


def test_app_fixes():
    """Test that app.py frame resolution fix is in place."""
    print("\nTesting app.py fixes...")

    with open('app.py', 'r') as f:
        content = f.read()

    # Check for frame normalization code
    has_resize = 'cv2.resize(f, (640, 480)' in content
    has_normalized_var = 'normalized_pre_fall' in content

    passed = has_resize and has_normalized_var
    symbol = '✓' if passed else '✗'
    print(f"  {symbol} Frame resolution normalization implemented")

    return passed


def test_attribute_consistency():
    """Test that all attribute names are consistent."""
    print("\nTesting attribute name consistency...")

    with open('models/llm_provider.py', 'r') as f:
        content = f.read()

    # Count occurrences
    threshold_correct = content.count('_vram_threshold_gb')
    threshold_typo = content.count('_vram_threshhold_gb')
    dependencies_correct = content.count('_dependencies_available')
    dependencies_typo = content.count('_dependies_available')
    mode_correct = content.count('_persistent_mode')
    mode_typo = content.count('_persistent_mmode')

    tests = {
        f'_vram_threshold_gb: {threshold_correct} uses, 0 typos': threshold_correct > 0 and threshold_typo == 0,
        f'_dependencies_available: {dependencies_correct} uses, 0 typos': dependencies_correct > 0 and dependencies_typo == 0,
        f'_persistent_mode: {mode_correct} uses, 0 typos': mode_correct > 0 and mode_typo == 0,
    }

    passed = all(tests.values())
    for test, status in tests.items():
        symbol = '✓' if status else '✗'
        print(f"  {symbol} {test}")

    return passed


def main():
    """Run all tests."""
    print("=" * 60)
    print("Active Learning Wizard - Bug Fix Verification")
    print("=" * 60)

    results = []

    results.append(("llm_provider.py", test_llm_provider_fixes()))
    results.append(("sia_detector.py", test_sia_detector_fixes()))
    results.append(("feedback_generator.py", test_feedback_generator_fixes()))
    results.append(("app.py", test_app_fixes()))
    results.append(("Attribute consistency", test_attribute_consistency()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = all(result[1] for result in results)

    for name, passed in results:
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"{name:30} {status}")

    print("=" * 60)

    if all_passed:
        print("✓ ALL TESTS PASSED! All critical bugs have been fixed.")
        return 0
    else:
        print("✗ SOME TESTS FAILED. Review the fixes above.")
        return 1


if __name__ == '__main__':
    exit(main())
