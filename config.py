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
BASE_DIR                = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR             = os.path.join(BASE_DIR, "dataset")
ENCODINGS_FILE          = os.path.join(BASE_DIR, "encodings", "face_encodings.pkl")
ATTENDANCE_DIR          = os.path.join(BASE_DIR, "security_records")
SECURITY_DIR            = os.path.join(BASE_DIR, "security_records")
INTRUDER_SNAPSHOTS_DIR  = os.path.join(SECURITY_DIR, "intruders")
LOGS_DIR                = os.path.join(BASE_DIR, "logs")
ASSETS_DIR              = os.path.join(BASE_DIR, "assets")

# ── Security Patrol System ───────────────────────────────────────────────────
SYSTEM_NAME             = "ROS Security Patrol Bot"
SYSTEM_VERSION          = "v2.0-SECURITY"
PATROL_FORWARD_SPEED    = 0.35       # Base linear speed along perimeter (0.0 to 1.0)
PATROL_TURN_SPEED       = 0.30       # Angular speed for perimeter corner turns
PATROL_LEG_DURATION     = 5.0        # Seconds to patrol along each boundary leg
PATROL_TURN_DURATION    = 2.2        # Seconds to turn 90 degrees at perimeter corners
INTRUDER_HOLD_SECONDS   = 6.0        # Cooldown & siren duration on intruder detection
GREETING_HOLD_SECONDS   = 4.0        # Cooldown when greeting verified familiar personnel

# ── Camera Settings ──────────────────────────────────────────────────────────
CAMERA_INDEX        = 0          # 0 = default cam; change to 1 or 2 if external USB cam
FRAME_WIDTH         = 640        # 640x480 is the gold standard for Pi 4B USB cameras
FRAME_HEIGHT        = 480
FPS_TARGET          = 30
USE_MJPG            = True       # Hardware MJPG decoding (prevents USB bandwidth throttling on Pi)

# ── Raspberry Pi 4B Optimization Tuning ─────────────────────────────────────
PROCESS_SCALE         = 0.33     # Scale factor for detection (0.33x = 213x160; 5x faster on Pi 4B)
PROCESS_EVERY_N       = 1        # Process face recognition every N frames (1 = every frame)
UPSAMPLE_TIMES        = 0        # 0 = fastest (recommended on Pi 4B); 1 = detect smaller faces
DETECTION_MODEL       = "hog"    # "hog" is CPU-optimized for ARM Cortex-A72; never use "cnn" on Pi CPU
RECOGNITION_TOLERANCE = 0.50     # lower = stricter (0.45–0.52 recommended)
MIN_FACE_SIZE         = 30       # px in scaled frame — ignore distant noise

# ── TFT Display Settings ─────────────────────────────────────────────────────
TFT_ENABLED          = True       # Enable TFT display output
TFT_BACKEND          = "auto"     # "auto" | "arduino" | "framebuffer" (/dev/fb1) | "window"
TFT_WIDTH            = 320        # TFT screen width in pixels
TFT_HEIGHT           = 240        # TFT screen height in pixels
TFT_FB_DEVICE        = "/dev/fb1" # Framebuffer device (Waveshare/Adafruit PiTFT)
TFT_LIVE_STREAM      = True       # Stream live camera feed with HUD overlay onto TFT
TFT_FEEDBACK_HOLD    = 4.0        # Seconds to hold alert/welcome banner
TFT_ROTATION         = 0          # Screen rotation: 0, 90, 180, 270 degrees

# ── Arduino Uno Shield TFT Serial Settings ──────────────────────────────────
ARDUINO_TFT_ENABLED  = True       # Auto-detect and send commands to Arduino Uno TFT Shield
ARDUINO_TFT_PORT     = "auto"     # "auto" (scans /dev/ttyACM* and /dev/ttyUSB*) or explicit e.g. "/dev/ttyACM0"
ARDUINO_TFT_BAUD     = 115200     # Serial baud rate

# ── Security & Verification Logic ───────────────────────────────────────────
COOLDOWN_SECONDS      = 20       # prevent duplicate logs within N seconds
CONFIRMED_FRAMES      = 2        # consecutive confirmations to lock face
SECURITY_SHEET_NAME   = "SecurityLog"
ATTENDANCE_SHEET_NAME = "SecurityLog"

# ── UI Theme ─────────────────────────────────────────────────────────────────
THEME = {
    "bg_dark":      "#0A0E14",
    "bg_card":      "#12171F",
    "bg_panel":     "#1B222D",
    "accent":       "#388BFD",
    "accent2":      "#2EA043",
    "warning":      "#FA7A18",
    "danger":       "#DA3633",
    "text_primary": "#F0F6FC",
    "text_muted":   "#8B949E",
    "border":       "#30363D",
    "success":      "#238636",
    "font_head":    ("Helvetica", 20, "bold"),
    "font_title":   ("Helvetica", 14, "bold"),
    "font_body":    ("Helvetica", 11),
    "font_small":   ("Helvetica", 9),
    "font_code":    ("Courier", 10),
}
