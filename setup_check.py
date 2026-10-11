#!/usr/bin/env python3
"""
=============================================================================
 ROS Attendance Bot — Setup Script
 Checks dependencies, creates dirs, and optionally runs first encoding.
=============================================================================
"""

import os
import sys
import subprocess
from pathlib import Path

REQUIRED = [
    "face_recognition", "cv2", "numpy", "PIL",
    "openpyxl", "pandas", "imutils",
]

DIRS = ["dataset", "encodings", "attendance_records", "assets", "logs"]


def check_python():
    v = sys.version_info
    print(f"Python {v.major}.{v.minor}.{v.micro}", end="")
    if v.major < 3 or (v.major == 3 and v.minor < 9):
        print("  ❌ — requires Python 3.9+")
        sys.exit(1)
    print("  ✅")


def check_deps():
    print("\nChecking dependencies…")
    missing = []
    for pkg in REQUIRED:
        try:
            __import__(pkg)
            print(f"  {pkg:20s} ✅")
        except ImportError:
            print(f"  {pkg:20s} ❌  MISSING")
            missing.append(pkg)
    return missing


def create_dirs():
    print("\nCreating directories…")
    base = Path(__file__).parent
    for d in DIRS:
        p = base / d
        p.mkdir(parents=True, exist_ok=True)
        print(f"  {d}/ ✅")


def main():
    print("=" * 50)
    print("  ROS Attendance Bot — Setup Check")
    print("=" * 50)

    check_python()
    missing = check_deps()
    create_dirs()

    if missing:
        print(f"\n⚠️  Missing: {', '.join(missing)}")
        answer = input("Install via pip now? [y/N]: ").strip().lower()
        if answer == "y":
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    else:
        print("\n✅ All dependencies satisfied.")

    print("\nSetup complete. Run `python main.py` to launch the GUI.")
    print("Or `python headless.py` for Raspberry Pi headless mode.")
    print("=" * 50)


if __name__ == "__main__":
    main()
