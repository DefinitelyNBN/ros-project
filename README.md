# 🛡️ ROS Security Patrol Bot (Raspberry Pi 4B Autonomous Defense)

> Autonomous perimeter security and surveillance robot for Raspberry Pi with live face analysis, speaker alarms, and live TFT camera streaming.

📖 **Hardware & Pinout Handbooks**:
- [HARDWARE_AND_OPERATIONS_GUIDE.md](file:///Users/nbn/Desktop/rosprojectattendance/HARDWARE_AND_OPERATIONS_GUIDE.md) — Robot assembly, motor drivers, and systemd boot service.
- [CIRCUIT_AND_PINOUT_GUIDE.md](file:///Users/nbn/Desktop/rosprojectattendance/CIRCUIT_AND_PINOUT_GUIDE.md) — Master circuit schematic, 40-pin GPIO pinout, power distribution, and BTS7960/L298N wiring.

---

## ⚡ Core Security Capabilities

1. **Perimeter Roaming**:
   - Autonomously traverses perimeter boundaries (`PATROL_FORWARD`), executing perimeter corner turns (`PATROL_TURN`).
2. **Real-Time Face Analysis**:
   - Uses optimized 0-latency HOG neural embeddings pipeline on Raspberry Pi 4B Cortex-A72 CPU.
3. **🚨 Intruder Detection & Alarm**:
   - When an **unfamiliar person** enters the perimeter:
     - Halts robot immediately and locks onto target.
     - Sounds high-urgency **alarm sirens & verbal warnings** over speakers: *"Warning! Intruder alert! Unfamiliar person detected in secure perimeter!"*
     - **Streams live camera feed** with glowing Red Intruder Alert HUD to the TFT display.
     - Saves timestamped snapshot photo to `security_records/intruders/`.
4. **✅ Familiar Personnel Welcome**:
   - When a **trained / authorized person** is recognized:
     - Greets them warmly by name: *"Welcome, {name}! Identity verified. Access granted."*
     - Displays Green Access Granted HUD on live TFT stream.
     - Pauses briefly, then resumes autonomous perimeter patrol.
5. **📺 Live Camera Feed on TFT Screen**:
   - Real-time video stream rendered directly on the robot's TFT display (`/dev/fb1` or preview window) with futuristic HUD overlays.

---

## 🚀 Quick Launch Commands

### 1. Run Autonomous Security Patrol Bot:
```bash
python3 security_bot.py
# Or pure headless mode over SSH:
python3 security_bot.py --headless
```

### 2. Stationary Guard Mode (Camera & Alarms Active, No Wheel Movement):
```bash
python3 security_bot.py --no-nav
```

### 3. Test Speakers & Security Alarms:
```bash
python3 test_speaker.py
```

### 4. Live Camera Telemetry in Web Browser:
```bash
python3 camera_diagnostic.py
# Open http://<pi-ip>:5000 in your browser
```

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
