# 🤖 ROS Attendance Bot (Raspberry Pi 4B Optimized)

> Autonomous face recognition attendance system designed for Raspberry Pi robots with an external USB camera.

📖 **Complete Hardware & Pinout Handbooks**:
- [HARDWARE_AND_OPERATIONS_GUIDE.md](file:///Users/nbn/Desktop/rosprojectattendance/HARDWARE_AND_OPERATIONS_GUIDE.md) — Step-by-step robot assembly, software setup, and systemd boot service.
- [CIRCUIT_AND_PINOUT_GUIDE.md](file:///Users/nbn/Desktop/rosprojectattendance/CIRCUIT_AND_PINOUT_GUIDE.md) — Master circuit schematic, 40-pin GPIO pinout, power distribution, and L298N motor driver wiring.

---

## ⚡ Raspberry Pi 4B Optimizations

Running neural face embeddings and live video simultaneously on a moving Raspberry Pi 4B robot introduces hardware constraints:
1. **Decoupled Zero-Latency Pipeline**: Camera capture runs in a dedicated thread (`CamGrabber`), so OpenCV's frame buffer never lags behind real-time. Robot telemetry stays butter-smooth at 30 FPS even when the robot navigates or turns quickly.
2. **V4L2 + MJPG Hardware Decoding**: Automatically selects Linux `V4L2` driver and requests compressed `MJPG` from the USB webcam to avoid saturating the USB 2.0/3.0 bus (which otherwise limits raw YUYV video to 5-10 FPS).
3. **0.33x Sub-sampling (`PROCESS_SCALE = 0.33`)**: Downsamples frame to ~213x160 for the HOG detector, delivering a **~5x speedup** on the Cortex-A72 CPU while maintaining high recognition accuracy.
4. **Zero-Upsample (`UPSAMPLE_TIMES = 0`)**: Prevents dlib's costly multi-scale pyramid from ballooning CPU load and causing thermal throttling.
5. **Auto-Capped Training**: Resizes dataset photos during encoding to max 640px so student registration completes in seconds instead of minutes.

---

## Architecture

```
rosprojectattendance/
├── main.py                  ← Unified master runner (GUI, ROS 2 FSM, TFT, Excel)
├── headless.py              ← Autonomous CLI runner for Pi without screen
├── ros_attendance_node.py   ← ROS 2 Humble node broadcasting to /cmd_vel & /attendance/*
├── recognition_engine.py    ← Multi-threaded zero-latency camera & HOG engine
├── tft_display.py           ← TFT display feedback driver (Checkmark / Red X)
├── attendance.py            ← Attendance logic + Excel (.xlsx) / CSV export
├── encoder.py               ← 128-d face embedding generator from dataset/
├── config.py                ← Central parameters & Pi 4B tuning profile
├── pi_setup.sh              ← One-click Pi 4B environment & swap setup script
├── setup_check.py           ← System dependency validator
├── CIRCUIT_AND_PINOUT_GUIDE.md      ← Master circuit schematic & 40-pin pinout
├── HARDWARE_AND_OPERATIONS_GUIDE.md ← Full robot assembly & operations manual
├── requirements.txt
│
├── dataset/                 ← Student training images (FirstName_LastName_ID/)
├── encodings/               ← Saved embeddings (face_encodings.pkl)
├── attendance_records/      ← Excel (.xlsx) reports + CSV logs
└── logs/                    ← System execution logs
```

---

## 🚀 Quick Setup on Raspberry Pi 4B

### Step 1: Automated Pi Setup (One-Click)
Run the automated optimizer script on your Pi 4B:
```bash
chmod +x pi_setup.sh
./pi_setup.sh
```
*What this script does:*
- Increases Pi swap space to 2048MB (required so `dlib` doesn't OOM during compile).
- Installs BLAS / LAPACK accelerators (`libopenblas-dev`, `libatlas-base-dev`).
- Installs V4L2 camera tools and builds Python dependencies.

---

## 🎮 Unified Execution (All Features in One File)

Run everything cooperatively with a single command:
```bash
python3 main.py
```

### What `python3 main.py` runs simultaneously:
1. **0-Latency Camera Pipeline**: Streams 30 FPS video with multi-threaded HOG face recognition.
2. **ROS 2 Navigation State Machine**:
   - Publishes velocity on `/cmd_vel` (`SEARCHING`: rotates with `angular.z = 0.3`).
   - Automatically halts (`LOCKED`: `0.0` vel) for 5 seconds when attendance is marked.
3. **TFT Display Feedback**:
   - Displays **Green Checkmark (✔)** with student name/ID on verified attendance.
   - Displays **Red X Mark (✖)** on unregistered persons.
   - Displays animated radar reticle & attendance counter during scanning.
4. **Display Auto-Detection**:
   - If a monitor/VNC is connected, launches the full **Dark-Themed GUI Dashboard**.
   - If run over headless SSH or no display is detected, automatically runs in **Headless Robot Mode**.
5. **Excel & CSV Reporting**: Logs attendance in real-time and auto-exports styled `.xlsx` workbooks.

### Optional CLI Flags:
```bash
python3 main.py --headless      # Force headless robot mode even if display attached
python3 main.py --no-nav        # Run attendance & camera without /cmd_vel movement
python3 main.py --no-tft        # Run without TFT screen output
python3 main.py --cam 1         # Select external USB camera index 1
```
Implements an autonomous Navigation Finite State Machine (FSM):
- **`/cmd_vel` (`geometry_msgs/msg/Twist`)**:
  - `'SEARCHING'`: Robot rotates in place (`angular.z = 0.3`) scanning the environment for faces.
  - `'LOCKED'`: Halts robot (`linear.x = 0.0`, `angular.z = 0.0`), holds position for 5 seconds while logging attendance and flashing the green TFT checkmark, then resumes `'SEARCHING'`.
- **Attendance Topics**:
  - `/attendance/student_id` (`std_msgs/msg/String`)
  - `/attendance/student_name` (`std_msgs/msg/String`)
  - `/attendance/total_count` (`std_msgs/msg/Int32`)
  - `/attendance/state` (`std_msgs/msg/String` -> `SEARCHING` | `LOCKED`)
  - `/attendance/unknown_alert` (`std_msgs/msg/String`)

---

## ⚙️ Configuration Tuning (`config.py`)

| Parameter | Recommended for Pi 4B | Purpose |
|---|---|---|
| `CAMERA_INDEX` | `0` (or `1` for external USB) | Video capture device index |
| `FRAME_WIDTH` / `HEIGHT` | `640` x `480` | Optimal USB resolution on Pi 4B |
| `USE_MJPG` | `True` | Hardware compressed webcam stream |
| `PROCESS_SCALE` | `0.33` | 5x faster face detection |
| `PROCESS_EVERY_N` | `3` | Run inference every 3rd frame (cool CPU) |
| `UPSAMPLE_TIMES` | `0` | Prevents CPU throttling |
| `CONFIRMED_FRAMES` | `3` | Confirmations needed before marking |
| `COOLDOWN_SECONDS` | `30` | Prevents duplicate marks |
| `TFT_ENABLED` | `True` | Activates TFT visual feedback |
| `TFT_BACKEND` | `"auto"` | `"auto"`, `"framebuffer"` (`/dev/fb1`), or `"window"` |
| `TFT_FEEDBACK_HOLD` | `3.5` | Seconds to hold checkmark / X before returning to idle |

---

## 🖥️ TFT Display Feedback System

The robot features real-time visual feedback on an onboard SPI/Framebuffer TFT display (e.g. Waveshare 2.8"/3.5", Adafruit PiTFT, or ST7789/ILI9341):

| Display State | Visual Output | Condition |
|---|---|---|
| **Verified & Marked** | **Green Checkmark (✔)** with student name, ID badge & timestamp | Person is found in database & attendance is recorded |
| **Unregistered Person** | **Red X Mark (✖)** with "ACCESS DENIED / NOT REGISTERED" | Unknown face detected |
| **Idle Scanning** | Animated radar reticle with total attendance counter & clock | Robot navigating and searching for faces |

- Automatically writes to the Linux Framebuffer device (`/dev/fb1` or `/dev/fb0`) in hardware 16-bit RGB565.
- Automatically falls back to desktop preview window when testing without physical SPI hardware connected.

---

## 📊 Excel Output Format

Exported to `attendance_records/attendance_YYYY-MM-DD.xlsx`:
1. **Attendance Sheet**: Styled table containing S.No, Student ID, Name, Date, Time, and Status (highlighted green).
2. **Summary Sheet**: Key session metrics, total present count, and timestamp.

---

## License
MIT — Open for educational and robotics research projects.
