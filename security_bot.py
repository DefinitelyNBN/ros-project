"""
=============================================================================
 ROS Security Patrol Bot — Master Security Runner
 Autonomous perimeter security robot with face analysis:
   - Roams around perimeter boundary
   - Analyzes all faces in real-time (Pi 4B 0-latency HOG pipeline)
   - Unfamiliar / Unrecognized face:
       -> Sounds loud siren & verbal warning alert over speakers
       -> Locks robot & triggers perimeter intruder defense state
       -> Streams live camera feed with glowing Red Intruder Alert HUD to TFT
       -> Saves timestamped snapshot photo to security_records/intruders/
   - Familiar / Trained face:
       -> Welcomes the person warmly by name: "Welcome, {name}!"
       -> Pauses robot & displays Green Access Granted HUD on TFT
       -> Resumes perimeter patrol after greeting cooldown
=============================================================================
 Usage:
     python3 security_bot.py                # Auto-detects display (GUI or Headless)
     python3 security_bot.py --headless     # Headless robot mode for pure SSH
     python3 security_bot.py --no-nav       # Stationary guard mode (no wheel movement)
     python3 security_bot.py --cam 0        # Select camera index
=============================================================================
"""

import sys
import argparse
import logging
from main import main as run_main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ROS Security Patrol Bot")
    parser.add_argument("--headless", action="store_true", help="Force headless robot mode")
    parser.add_argument("--no-nav", action="store_true", help="Stationary guard mode (no movement)")
    parser.add_argument("--no-tft", action="store_true", help="Disable TFT screen output")
    parser.add_argument("--cam", type=int, default=0, help="Camera index (default 0)")
    args = parser.parse_args()

    # Pass through to unified application
    sys.argv = [sys.argv[0]]
    if args.headless: sys.argv.append("--headless")
    if args.no_nav:   sys.argv.append("--no-nav")
    if args.no_tft:   sys.argv.append("--no-tft")
    if args.cam:      sys.argv.extend(["--cam", str(args.cam)])

    run_main()
