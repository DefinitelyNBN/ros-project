"""
=============================================================================
 ROS Attendance Bot — Headless CLI Mode
 For running on a Raspberry Pi without a display (SSH / ROS node).
 Marks attendance and auto-exports Excel every N minutes.
=============================================================================
Usage:
    python headless.py [--export-interval 10] [--cam 0]
=============================================================================
"""

import argparse
import logging
import time
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import config
from encoder import encode_faces
from attendance import AttendanceManager
from recognition_engine import RecognitionEngine
from tft_display import TFTDisplay
from audio_announcer import AudioAnnouncer

Path(config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.LOGS_DIR, "headless.log")),
    ],
)
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Headless attendance runner")
    parser.add_argument("--export-interval", type=int, default=10,
                        help="Auto-export Excel every N minutes (default: 10)")
    parser.add_argument("--cam", type=int, default=config.CAMERA_INDEX,
                        help="Camera index")
    parser.add_argument("--no-tft", action="store_true",
                        help="Disable TFT display output")
    args = parser.parse_args()

    config.CAMERA_INDEX = args.cam

    log.info("═══════════════════════════════════════════")
    log.info("  ROS Attendance Bot — Headless Mode")
    log.info("  Date: %s", datetime.now().strftime("%Y-%m-%d"))
    log.info("  Camera: %d", config.CAMERA_INDEX)
    log.info("  Export interval: %d min", args.export_interval)
    log.info("  TFT Feedback: %s", "Disabled" if args.no_tft else "Active")
    log.info("═══════════════════════════════════════════")

    # Ensure encodings exist
    encode_faces(rebuild=False)

    att = AttendanceManager()

    # Initialize audio announcer (USB speaker)
    audio = AudioAnnouncer(enabled=True)
    audio.announce_startup()

    # Initialize TFT display feedback
    tft = None
    if config.TFT_ENABLED and not args.no_tft:
        try:
            tft = TFTDisplay()
            tft.show_idle(total_count=att.get_count())
        except Exception as e:
            log.warning("Could not initialize TFT display: %s", e)

    def on_face_detected(name, sid, frame, boxes):
        log.info("✅ MARKED: %s (ID: %s)", name, sid)
        audio.announce_recognised(name)
        if tft:
            tft.show_success(name, sid)

    def on_unknown_detected(frame, boxes):
        log.warning("❌ UNKNOWN PERSON DETECTED — Not in database!")
        audio.announce_unknown()
        if tft:
            tft.show_unknown()

    def on_status(s):
        log.info("STATUS: %s", s)
        if tft:
            tft.update_status(s)

    engine = RecognitionEngine(
        attendance_manager=att,
        on_face_detected=on_face_detected,
        on_unknown_detected=on_unknown_detected,
        on_status=on_status,
    )
    engine.start()

    # Graceful shutdown
    def _shutdown(sig, frame):
        log.info("Shutting down…")
        engine.stop()
        audio.announce_shutdown()
        audio.shutdown()
        if tft:
            tft.close()
        path = att.export_excel()
        log.info("Final Excel exported → %s", path)
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    last_export = time.time()
    try:
        while True:
            time.sleep(5)
            elapsed = time.time() - last_export
            if elapsed >= args.export_interval * 60:
                path = att.export_excel()
                log.info("📊 Auto-exported → %s", path)
                last_export = time.time()
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()
