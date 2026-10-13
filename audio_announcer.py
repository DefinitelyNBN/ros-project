"""
=============================================================================
 ROS Attendance Bot — Audio Announcer
 Speaks recognition results through USB speakers using espeak (offline TTS).
 Runs announcements in a background thread so it never blocks the camera.
=============================================================================
 Requirements (install on Pi):
     sudo apt-get install -y espeak espeak-ng
 No Python packages needed — uses subprocess to call espeak directly.
=============================================================================
"""

import subprocess
import threading
import queue
import logging
import time

log = logging.getLogger(__name__)

# ── Announcement Templates ────────────────────────────────────────────────────
MSG_RECOGNISED   = "Welcome, {name}. Attendance marked."
MSG_UNKNOWN      = "Unknown person detected. Access not granted."
MSG_STARTUP      = "Attendance system online. Ready to scan."
MSG_SHUTDOWN     = "Attendance system shutting down."

# ── espeak settings ───────────────────────────────────────────────────────────
ESPEAK_SPEED     = 155      # words per minute (120–180 recommended)
ESPEAK_AMPLITUDE = 200      # volume 0–200 (200 = maximum)
ESPEAK_PITCH     = 55       # pitch 0–99
ESPEAK_VOICE     = "en"     # "en" | "en-us" | "en-gb" | "en+m3" for male voice


class AudioAnnouncer:
    """
    Non-blocking audio announcer. Queues speech requests and plays them
    sequentially in a daemon thread, so recognition is never slowed down.
    USB speakers on Raspberry Pi are auto-detected by ALSA — no config needed.
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._queue   = queue.Queue(maxsize=4)   # cap: drop if robot is very busy
        self._thread  = None
        self._running = False

        if enabled:
            self._check_espeak()
            self._start_worker()

    # ── Public API ─────────────────────────────────────────────────────────────

    def announce_recognised(self, name: str):
        """Call when a registered face is confirmed."""
        msg = MSG_RECOGNISED.format(name=name)
        self._enqueue(msg)

    def announce_unknown(self):
        """Call when an unregistered face is detected."""
        self._enqueue(MSG_UNKNOWN)

    def announce_startup(self):
        """Call once at system boot."""
        self._enqueue(MSG_STARTUP)

    def announce_shutdown(self):
        """Call on clean exit — drains queue first."""
        self._enqueue(MSG_SHUTDOWN)
        # Give the worker a moment to speak the message before process exits
        time.sleep(3.5)

    def speak(self, text: str):
        """Speak arbitrary text (e.g., status messages)."""
        self._enqueue(text)

    def shutdown(self):
        """Stop the worker thread cleanly."""
        self._running = False
        try:
            self._queue.put_nowait(None)   # unblock the worker
        except queue.Full:
            pass

    # ── Internal ───────────────────────────────────────────────────────────────

    def _enqueue(self, text: str):
        if not self._enabled:
            return
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            log.debug("[AudioAnnouncer] Queue full — dropping: %s", text)

    def _start_worker(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="AudioWorker"
        )
        self._thread.start()
        log.info("[AudioAnnouncer] Worker started (espeak, USB audio)")

    def _worker(self):
        while self._running:
            try:
                text = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if text is None:
                break

            self._speak_blocking(text)
            self._queue.task_done()

    def _speak_blocking(self, text: str):
        """Invoke espeak synchronously (called from worker thread only)."""
        cmd = [
            "espeak",
            "-v", ESPEAK_VOICE,
            "-s", str(ESPEAK_SPEED),
            "-a", str(ESPEAK_AMPLITUDE),
            "-p", str(ESPEAK_PITCH),
            text
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                log.warning("[AudioAnnouncer] espeak error: %s", result.stderr.decode())
        except FileNotFoundError:
            log.error("[AudioAnnouncer] espeak not found. Install: sudo apt-get install espeak")
            self._enabled = False   # disable to stop spamming errors
        except subprocess.TimeoutExpired:
            log.warning("[AudioAnnouncer] espeak timed out for: %s", text)
        except Exception as e:
            log.warning("[AudioAnnouncer] Unexpected error: %s", e)

    def _check_espeak(self):
        """Warn early if espeak is not installed."""
        try:
            subprocess.run(["espeak", "--version"],
                           capture_output=True, timeout=3)
            log.info("[AudioAnnouncer] espeak found ✓")
        except FileNotFoundError:
            log.error(
                "[AudioAnnouncer] espeak NOT installed! "
                "Run: sudo apt-get install -y espeak  then restart."
            )
            self._enabled = False
        except Exception:
            pass
