"""
=============================================================================
 ROS Attendance Bot — TFT Display Controller
 Hardware & Simulated TFT Display Driver for Raspberry Pi Robots.
 
 Displays:
   ✅ GREEN CHECKMARK : When a person in database is recognized & attendance marked
   ❌ RED X MARK      : When an unknown / unregistered person is detected
   📡 IDLE / SCANNING : Animated scanning radar & attendance counter
 
 Supported Backends:
   - Linux Framebuffer (/dev/fb1 or /dev/fb0) for Waveshare, Adafruit PiTFT
   - ST7789 / ILI9341 SPI drivers (if luma / adafruit libraries installed)
   - Desktop / X11 Window Preview (for testing on monitor or development PC)
=============================================================================
"""

import os
import sys
import time
import math
import logging
import threading
import platform
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config

log = logging.getLogger(__name__)


def _load_font(size: int, bold: bool = False):
    """Load a TrueType font if available, with graceful fallback to default."""
    candidates = [
        # Linux / Raspberry Pi OS fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        # macOS fonts
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


class TFTDisplay:
    """
    Manages visual feedback on TFT displays attached to Raspberry Pi robots.
    Thread-safe and non-blocking with automatic return-to-idle timeouts.
    """

    def __init__(self, width: int = None, height: int = None, backend: str = None):
        self.width   = width   or config.TFT_WIDTH
        self.height  = height  or config.TFT_HEIGHT
        self.backend = backend or config.TFT_BACKEND

        self._lock         = threading.Lock()
        self._running      = True
        self._current_mode = "idle"     # "idle" | "success" | "unknown"
        self._total_count  = 0
        self._status_text  = "Robot Scanning..."
        self._revert_timer = None

        # Hardware handles
        self._fb_file      = None
        self._is_fb        = False
        self._cv2_preview  = False
        self._arduino_ser  = None

        # Preload fonts
        self.font_title    = _load_font(max(14, int(self.height * 0.075)), bold=True)
        self.font_sub      = _load_font(max(11, int(self.height * 0.055)), bold=False)
        self.font_name     = _load_font(max(16, int(self.height * 0.085)), bold=True)
        self.font_badge    = _load_font(max(11, int(self.height * 0.052)), bold=True)
        self.font_tiny     = _load_font(max(9,  int(self.height * 0.045)), bold=False)

        self._init_backend()
        self._init_arduino()

        # Initial screen
        self.show_idle()

    # ── Backend Initialization ───────────────────────────────────────────────

    def _init_arduino(self):
        """Connect to Arduino Uno TFT Shield over USB serial if available."""
        if not getattr(config, "ARDUINO_TFT_ENABLED", True):
            return

        port = getattr(config, "ARDUINO_TFT_PORT", "auto")
        baud = getattr(config, "ARDUINO_TFT_BAUD", 115200)

        candidates = []
        if port != "auto":
            candidates.append(port)
        else:
            # Common Linux/Pi Arduino device paths
            import glob
            candidates.extend(sorted(glob.glob("/dev/ttyACM*")))
            candidates.extend(sorted(glob.glob("/dev/ttyUSB*")))
            # macOS testing paths
            candidates.extend(sorted(glob.glob("/dev/cu.usbmodem*")))
            candidates.extend(sorted(glob.glob("/dev/cu.usbserial*")))

        for p in candidates:
            try:
                import serial
                ser = serial.Serial(p, baud, timeout=1)
                ser.dtr = False
                ser.rts = False
                time.sleep(2.0) # Allow Arduino bootloader auto-reset to settle
                # Drain initial buffer
                if ser.in_waiting:
                    ser.read(ser.in_waiting)
                self._arduino_ser = ser
                log.info("TFT Display: Connected to Arduino Uno TFT Shield on %s @ %d baud", p, baud)
                break
            except Exception as e:
                log.debug("Could not connect to serial port %s: %s", p, e)

    def _send_arduino(self, command: str):
        """Send command string to Arduino Uno TFT Shield."""
        if self._arduino_ser:
            try:
                line = (command.strip() + "\n").encode("utf-8")
                self._arduino_ser.write(line)
                self._arduino_ser.flush()
                log.debug("Sent to Arduino: %s", command.strip())
            except Exception as e:
                log.warning("Error writing to Arduino TFT Serial: %s", e)

    def _init_backend(self):
        """Detect and initialize the display output target."""
        fb_path = config.TFT_FB_DEVICE

        # Check if a graphical window environment (X11 / Wayland) is actually available
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if platform.system() == "Darwin":
            has_display = True

        if self.backend == "auto":
            if os.path.exists(fb_path):
                self._backend_type = "framebuffer"
            elif has_display:
                self._backend_type = "window"
            else:
                # Running headless (SSH / Robot without HDMI monitor)
                self._backend_type = "headless"
        else:
            self._backend_type = self.backend

        if self._backend_type == "framebuffer":
            try:
                self._fb_file = open(fb_path, "wb")
                self._is_fb   = True
                log.info("TFT Display connected to Framebuffer: %s (%dx%d)",
                         fb_path, self.width, self.height)
            except Exception as e:
                log.warning("Could not open %s (%s). Falling back to headless mode.", fb_path, e)
                self._backend_type = "headless"

        if self._backend_type == "window":
            if has_display:
                log.info("TFT Display using Window preview mode (%dx%d)", self.width, self.height)
                self._cv2_preview = True
            else:
                log.info("TFT Display: No graphical display detected. Running in headless mode.")
                self._backend_type = "headless"

        if self._backend_type == "headless":
            log.info("TFT Display: Hardware headless mode active (Arduino / Serial visual feedback).")

    # ── Public API ────────────────────────────────────────────────────────────

    def show_live_frame(self, frame_bgr: np.ndarray, status_overlay: str = None, alert_mode: str = None, target_name: str = None):
        """
        Renders the real-time live camera feed onto the TFT display (framebuffer or preview)
        with futuristic Security Patrol HUD overlays.
        """
        with self._lock:
            # If in an active alert lock, keep showing alert mode overlay
            active_alert = alert_mode or (self._current_mode if self._current_mode in ("intruder", "success") else None)

            try:
                import cv2
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb).resize((self.width, self.height), Image.Resampling.BILINEAR)
                draw = ImageDraw.Draw(pil_img)

                w, h = self.width, self.height

                if active_alert == "intruder":
                    # Flashing Red Alert HUD
                    draw.rectangle([(0, 0), (w, 24)], fill=(190, 20, 20))
                    draw.text((w // 2, 12), "🚨 INTRUDER ALERT! UNVERIFIED 🚨", fill=(255, 255, 255), font=self.font_tiny, anchor="mm")
                    draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(230, 40, 40), width=3)
                    draw.rectangle([(0, h - 22), (w, h)], fill=(40, 10, 10))
                    draw.text((w // 2, h - 11), f"UNFAMILIAR FACE • {datetime.now().strftime('%H:%M:%S')}", fill=(255, 120, 120), font=self.font_tiny, anchor="mm")
                elif active_alert == "success" or active_alert == "authorized":
                    # Green Authorized HUD
                    name_str = target_name or "Authorized Personnel"
                    draw.rectangle([(0, 0), (w, 24)], fill=(20, 120, 40))
                    draw.text((w // 2, 12), f"✅ ACCESS GRANTED: {name_str[:16]}", fill=(255, 255, 255), font=self.font_tiny, anchor="mm")
                    draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(40, 200, 60), width=2)
                    draw.rectangle([(0, h - 22), (w, h)], fill=(10, 30, 15))
                    draw.text((w // 2, h - 11), f"IDENTITY VERIFIED • {datetime.now().strftime('%H:%M:%S')}", fill=(100, 255, 120), font=self.font_tiny, anchor="mm")
                else:
                    # Normal Patrol HUD overlay
                    draw.rectangle([(0, 0), (w, 20)], fill=(10, 14, 20))
                    stat = status_overlay or self._status_text or "PERIMETER PATROL ACTIVE"
                    draw.text((w // 2, 10), f"[SEC-BOT] {stat[:26]}", fill=(56, 139, 253), font=self.font_tiny, anchor="mm")
                    # Center targeting crosshair
                    cx, cy = w // 2, h // 2
                    draw.line([(cx - 10, cy), (cx + 10, cy)], fill=(56, 139, 253), width=1)
                    draw.line([(cx, cy - 10), (cx, cy + 10)], fill=(56, 139, 253), width=1)
                    # Bottom bar
                    draw.rectangle([(0, h - 18), (w, h)], fill=(10, 14, 20))
                    draw.text((w // 2, h - 9), f"LIVE CAMERA • {datetime.now().strftime('%H:%M:%S')}", fill=(139, 148, 158), font=self.font_tiny, anchor="mm")

                self._output(pil_img)
            except Exception as e:
                log.debug("TFT live frame stream error: %s", e)

    def show_idle(self, total_count: int = None):
        """Renders the idle / scanning telemetry screen."""
        with self._lock:
            if total_count is not None:
                self._total_count = total_count
            self._current_mode = "idle"
            img = self._render_idle()
            self._output(img)
            self._send_arduino(f"IDLE:{self._total_count}")

    def show_success(self, name: str, student_id: str = None, time_str: str = None):
        """
        Displays a bright GREEN VERIFICATION for familiar person.
        Reverts to live patrol feed after TFT_FEEDBACK_HOLD seconds.
        """
        with self._lock:
            self._cancel_timer()
            self._current_mode = "success"
            t_str = time_str or datetime.now().strftime("%H:%M:%S")
            sid = student_id or "AUTHORIZED"
            img = self._render_success(name, sid, t_str)
            self._output(img)
            self._send_arduino(f"OK:{name}:{sid}")
            log.info("TFT: Displaying [AUTHORIZED PERSONNEL] for %s", name)
            self._schedule_revert()

    def show_unknown(self, time_str: str = None):
        """
        Displays a prominent RED INTRUDER ALERT for unfamiliar person.
        Reverts to live patrol feed after TFT_FEEDBACK_HOLD seconds.
        """
        with self._lock:
            self._cancel_timer()
            self._current_mode = "intruder"
            t_str = time_str or datetime.now().strftime("%H:%M:%S")
            img = self._render_unknown(t_str)
            self._output(img)
            self._send_arduino("INTRUDER")
            log.info("TFT: Displaying [RED INTRUDER ALERT] - Unfamiliar face")
            self._schedule_revert()

    def update_status(self, text: str):
        """Update status message."""
        self._status_text = text

    def close(self):
        """Clean up display buffers."""
        self._running = False
        self._cancel_timer()
        if self._arduino_ser:
            try:
                self._arduino_ser.close()
            except Exception:
                pass
        if self._fb_file:
            try:
                self._fb_file.close()
            except Exception:
                pass
        if self._cv2_preview:
            try:
                import cv2
                cv2.destroyWindow("TFT Display")
            except Exception:
                pass

    # ── Rendering: Green Checkmark ───────────────────────────────────────────

    def _render_success(self, name: str, student_id: str, time_str: str) -> Image.Image:
        w, h = self.width, self.height
        # Deep dark emerald background with subtle border
        img  = Image.new("RGB", (w, h), (10, 24, 16))
        draw = ImageDraw.Draw(img)

        # Outer success border glow
        draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(63, 185, 80), width=2)

        # Top pill header
        header_text = "VERIFIED • ATTENDANCE MARKED"
        draw.text((w // 2, int(h * 0.10)), header_text, fill=(63, 185, 80),
                  font=self.font_tiny, anchor="mm")

        # ── Green Checkmark Circle ──
        cx = w // 2
        cy = int(h * 0.40)
        radius = int(min(w, h) * 0.22)

        # Outer soft glow circle
        draw.ellipse([cx - radius - 3, cy - radius - 3, cx + radius + 3, cy + radius + 3],
                     fill=(20, 50, 32), outline=(46, 160, 67), width=1)

        # Main solid emerald circle
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     fill=(35, 134, 54), outline=(63, 185, 80), width=2)

        # Vectorized thick white checkmark inside circle
        p1 = (cx - radius * 0.44, cy - radius * 0.05)
        p2 = (cx - radius * 0.08, cy + radius * 0.42)
        p3 = (cx + radius * 0.48, cy - radius * 0.40)
        check_width = max(3, int(radius * 0.20))

        draw.line([p1, p2, p3], fill=(255, 255, 255), width=check_width, joint="curve")

        # ── Student Name & ID ──
        # Truncate long names gracefully
        display_name = name if len(name) <= 20 else name[:18] + "…"
        draw.text((w // 2, int(h * 0.72)), display_name, fill=(240, 246, 252),
                  font=self.font_name, anchor="mm")

        # Student ID badge
        id_badge = f"ID: {student_id}  •  {time_str}"
        draw.text((w // 2, int(h * 0.88)), id_badge, fill=(126, 231, 135),
                  font=self.font_badge, anchor="mm")

        return img

    # ── Rendering: Red X Mark ────────────────────────────────────────────────

    def _render_unknown(self, time_str: str) -> Image.Image:
        w, h = self.width, self.height
        # Deep dark crimson background with warning border
        img  = Image.new("RGB", (w, h), (26, 12, 14))
        draw = ImageDraw.Draw(img)

        # Outer warning border glow
        draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(248, 81, 73), width=2)

        # Top pill header
        header_text = "ACCESS DENIED • NOT REGISTERED"
        draw.text((w // 2, int(h * 0.10)), header_text, fill=(248, 81, 73),
                  font=self.font_tiny, anchor="mm")

        # ── Red X Circle ──
        cx = w // 2
        cy = int(h * 0.40)
        radius = int(min(w, h) * 0.22)

        # Outer soft glow circle
        draw.ellipse([cx - radius - 3, cy - radius - 3, cx + radius + 3, cy + radius + 3],
                     fill=(60, 20, 25), outline=(218, 54, 51), width=1)

        # Main solid crimson circle
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     fill=(180, 36, 42), outline=(248, 81, 73), width=2)

        # Vectorized thick white X inside circle
        offset = radius * 0.38
        x_width = max(3, int(radius * 0.20))
        # Top-left to bottom-right
        draw.line([(cx - offset, cy - offset), (cx + offset, cy + offset)],
                  fill=(255, 255, 255), width=x_width)
        # Top-right to bottom-left
        draw.line([(cx + offset, cy - offset), (cx - offset, cy + offset)],
                  fill=(255, 255, 255), width=x_width)

        # ── Warning Labels ──
        draw.text((w // 2, int(h * 0.72)), "UNKNOWN PERSON", fill=(248, 81, 73),
                  font=self.font_name, anchor="mm")

        draw.text((w // 2, int(h * 0.88)), "Not Found in Database", fill=(255, 160, 160),
                  font=self.font_badge, anchor="mm")

        return img

    # ── Rendering: Idle / Scanning Screen ────────────────────────────────────

    def _render_idle(self) -> Image.Image:
        w, h = self.width, self.height
        img  = Image.new("RGB", (w, h), (13, 17, 23))
        draw = ImageDraw.Draw(img)

        # Subtle dark border
        draw.rectangle([(1, 1), (w - 2, h - 2)], outline=(48, 54, 61), width=1)

        # Header Title
        draw.text((w // 2, int(h * 0.12)), "🤖 ROS ATTENDANCE BOT", fill=(88, 166, 255),
                  font=self.font_title, anchor="mm")

        # Center Radar / Face Target Reticle
        cx = w // 2
        cy = int(h * 0.44)
        r  = int(min(w, h) * 0.18)

        # Concentric radar rings
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(48, 54, 61), width=1)
        draw.ellipse([cx - r * 0.6, cy - r * 0.6, cx + r * 0.6, cy + r * 0.6],
                     outline=(33, 38, 45), width=1)

        # Target crosshairs
        draw.line([(cx - r - 8, cy), (cx - r + 8, cy)], fill=(88, 166, 255), width=2)
        draw.line([(cx + r - 8, cy), (cx + r + 8, cy)], fill=(88, 166, 255), width=2)
        draw.line([(cx, cy - r - 8), (cx, cy - r + 8)], fill=(88, 166, 255), width=2)
        draw.line([(cx, cy + r - 8), (cx, cy + r + 8)], fill=(88, 166, 255), width=2)

        # Center pulse dot
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(88, 166, 255))

        # Status text
        draw.text((w // 2, int(h * 0.70)), "SCANNING FOR FACES", fill=(139, 148, 158),
                  font=self.font_sub, anchor="mm")

        # Bottom stats bar
        stats = f"Present: {self._total_count}  •  {datetime.now().strftime('%H:%M')}"
        draw.text((w // 2, int(h * 0.88)), stats, fill=(63, 185, 80),
                  font=self.font_badge, anchor="mm")

        return img

    # ── Output Driver ─────────────────────────────────────────────────────────

    def _output(self, img: Image.Image):
        """Sends the PIL Image to the hardware framebuffer or window preview."""
        # Handle screen rotation if specified
        if config.TFT_ROTATION in (90, 180, 270):
            img = img.rotate(config.TFT_ROTATION, expand=False)

        # 1. Output to Linux Framebuffer (/dev/fb1 / /dev/fb0)
        if self._is_fb and self._fb_file:
            try:
                arr = np.array(img, dtype=np.uint16)
                # Convert RGB888 to RGB565 (16-bit format standard on Pi SPI TFTs)
                r = (arr[:, :, 0] >> 3) << 11
                g = (arr[:, :, 1] >> 2) << 5
                b = (arr[:, :, 2] >> 3)
                rgb565 = (r | g | b).astype(np.uint16)
                self._fb_file.seek(0)
                self._fb_file.write(rgb565.tobytes())
                self._fb_file.flush()
                return
            except Exception as e:
                log.warning("Framebuffer write error: %s", e)

        # 2. Output to Desktop / OpenCV Window Preview
        if self._cv2_preview:
            try:
                import cv2
                bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                cv2.imshow("TFT Display [Robot Feedback]", bgr)
                cv2.waitKey(1)
            except Exception:
                pass

    # ── Non-Blocking Revert Timer ─────────────────────────────────────────────

    def _schedule_revert(self):
        """Schedule automatic return to idle screen after TFT_FEEDBACK_HOLD seconds."""
        hold = config.TFT_FEEDBACK_HOLD
        self._revert_timer = threading.Timer(hold, self.show_idle)
        self._revert_timer.daemon = True
        self._revert_timer.start()

    def _cancel_timer(self):
        if self._revert_timer and self._revert_timer.is_alive():
            self._revert_timer.cancel()
            self._revert_timer = None


# ── Quick Standalone Test ────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing TFT Display Controller...")
    tft = TFTDisplay(320, 240, backend="window")

    print("Showing Idle Screen (2s)...")
    tft.show_idle(total_count=3)
    time.sleep(2)

    print("Showing Green Checkmark [Verified] (3.5s)...")
    tft.show_success("Niyanth B", "AM.SC.U4AIE24163")
    time.sleep(4)

    print("Showing Red X Mark [Unknown Person] (3.5s)...")
    tft.show_unknown()
    time.sleep(4)

    print("Test complete!")
    tft.close()
