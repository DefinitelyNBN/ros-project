"""
=============================================================================
 ROS Attendance Bot — Configuration
 Central config for paths, tuning parameters, and system settings.
=============================================================================
"""

import os

# Prevent macOS AVFoundation camera thread authorization hang
os.environ["OPENCV_AVFOUNDATION_SKIP_AUTH"] = "1"

# ── Root Paths ──────────────────────────────────────────────────────────────
BASE_DIR            = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR         = os.path.join(BASE_DIR, "dataset")
ENCODINGS_FILE      = os.path.join(BASE_DIR, "encodings", "face_encodings.pkl")
ATTENDANCE_DIR      = os.path.join(BASE_DIR, "attendance_records")
LOGS_DIR            = os.path.join(BASE_DIR, "logs")
ASSETS_DIR          = os.path.join(BASE_DIR, "assets")

# ── Camera Settings ──────────────────────────────────────────────────────────
CAMERA_INDEX        = 0          # 0 = default cam; change to 1 or 2 if external USB cam
FRAME_WIDTH         = 640        # 640x480 is the gold standard for Pi 4B USB cameras
FRAME_HEIGHT        = 480
FPS_TARGET          = 30
USE_MJPG            = True       # Hardware MJPG decoding (prevents USB bandwidth throttling on Pi)

# ── Raspberry Pi 4B Optimization Tuning ─────────────────────────────────────
PROCESS_SCALE         = 0.33     # Scale factor for detection (0.33x = 213x160; 5x faster on Pi 4B)
PROCESS_EVERY_N       = 3        # Process face recognition every N frames (prevents CPU thermal throttling)
UPSAMPLE_TIMES        = 0        # 0 = fastest (recommended on Pi 4B); 1 = detect smaller faces (slower)
DETECTION_MODEL       = "hog"    # "hog" is CPU-optimized for ARM Cortex-A72; never use "cnn" on Pi CPU
RECOGNITION_TOLERANCE = 0.50     # lower = stricter (0.45–0.52 recommended)
MIN_FACE_SIZE         = 30       # px in scaled frame — ignore distant noise

# ── TFT Display Settings ─────────────────────────────────────────────────────
TFT_ENABLED          = True       # Enable TFT display output
TFT_BACKEND          = "auto"     # "auto" | "framebuffer" (/dev/fb1) | "window" (desktop preview)
TFT_WIDTH            = 320        # TFT screen width in pixels
TFT_HEIGHT           = 240        # TFT screen height in pixels
TFT_FB_DEVICE        = "/dev/fb1" # Framebuffer device (Waveshare/Adafruit PiTFT)
TFT_FEEDBACK_HOLD    = 3.5        # Seconds to hold Checkmark / Red X on screen
TFT_ROTATION         = 0          # Screen rotation: 0, 90, 180, 270 degrees

# ── Attendance Logic ─────────────────────────────────────────────────────────
COOLDOWN_SECONDS      = 30       # prevent duplicate entries within N seconds
CONFIRMED_FRAMES      = 3        # 3 consecutive confirmations (responsive on moving robot)
ATTENDANCE_SHEET_NAME = "Attendance"

# ── UI Theme ─────────────────────────────────────────────────────────────────
THEME = {
    "bg_dark":      "#0D1117",
    "bg_card":      "#161B22",
    "bg_panel":     "#21262D",
    "accent":       "#58A6FF",
    "accent2":      "#3FB950",
    "warning":      "#F78166",
    "text_primary": "#E6EDF3",
    "text_muted":   "#8B949E",
    "border":       "#30363D",
    "success":      "#238636",
    "font_head":    ("Helvetica", 20, "bold"),
    "font_title":   ("Helvetica", 14, "bold"),
    "font_body":    ("Helvetica", 11),
    "font_small":   ("Helvetica", 9),
    "font_code":    ("Courier", 10),
}
