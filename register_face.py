#!/usr/bin/env python3
"""
=============================================================================
 CLI Face Registration Tool (Headless & Interactive)
 Easily register new students/faces from the terminal over SSH.
 Takes 5-10 photos from camera, saves to dataset/, and retrains encodings.
=============================================================================
Usage:
    python3 register_face.py
    python3 register_face.py --first John --last Doe --id 101 --num-photos 8
=============================================================================
"""

import os
import sys
import time
import argparse
from pathlib import Path

import cv2
import config
from encoder import encode_faces

def capture_faces_cli(first_name: str, last_name: str, student_id: str, num_photos: int = 6):
    folder_name = f"{first_name}_{last_name}_{student_id}"
    save_dir = Path(config.DATASET_DIR) / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"  REGISTERING NEW FACE: {first_name} {last_name} (ID: {student_id})")
    print("=" * 60)
    print(f"[*] Target directory: {save_dir}")
    print(f"[*] Opening camera index {config.CAMERA_INDEX}...")

    # Open camera with V4L2 on Pi / AVFoundation on macOS
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    if not cap.isOpened():
        print("[!] ERROR: Could not open camera device!")
        return False

    print("\n[!] Please look directly at the camera.")
    print("    Slightly tilt your head (front, left, right, smile) between captures.")
    print("    Capturing starts in 3 seconds...\n")
    for sec in range(3, 0, -1):
        print(f"    Starting in {sec}...")
        time.sleep(1)

    captured = 0
    while captured < num_photos:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.1)
            continue

        captured += 1
        img_name = f"img_{captured:03d}.jpg"
        img_path = save_dir / img_name
        cv2.imwrite(str(img_path), frame)
        print(f"  [✓] Captured photo {captured}/{num_photos} -> {img_name}")
        time.sleep(1.0) # 1 second interval between shots so user can change angle

    cap.release()

    print("\n" + "=" * 60)
    print("  ENCODING & TRAINING FACE RECOGNITION MODEL")
    print("=" * 60)
    print("[*] Generating 128-d face encodings (this takes ~5-10 seconds)...")

    try:
        encode_faces(rebuild=True)
        print("\n[✓] SUCCESS: Model retrained! New face registered successfully.")
        print(f"    Student: {first_name} {last_name} ({student_id})")
        print("    You can now run 'python3 main.py' to test recognition!")
        return True
    except Exception as e:
        print(f"[!] Error while encoding faces: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="CLI Face Registration Tool")
    parser.add_argument("--first", type=str, help="First Name")
    parser.add_argument("--last",  type=str, help="Last Name")
    parser.add_argument("--id",    type=str, help="Student Roll / ID")
    parser.add_argument("--num-photos", type=int, default=6, help="Number of photos to capture (default: 6)")
    args = parser.parse_args()

    first = args.first
    last  = args.last
    sid   = args.id

    # If not provided via CLI flags, prompt interactively
    if not (first and last and sid):
        print("=" * 60)
        print("  STUDENT FACE REGISTRATION")
        print("=" * 60)
        first = input("Enter First Name (e.g. Rahul): ").strip()
        last  = input("Enter Last Name  (e.g. Sharma): ").strip()
        sid   = input("Enter Student ID / Roll No (e.g. AM.EN.U4AIE21050): ").strip()

    if not (first and last and sid):
        print("[!] Error: First Name, Last Name, and Student ID are all required.")
        sys.exit(1)

    # Clean strings
    first = first.replace(" ", "_")
    last  = last.replace(" ", "_")
    sid   = sid.replace(" ", "_")

    success = capture_faces_cli(first, last, sid, num_photos=args.num_photos)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
