# 🤖 ROS Attendance Robot — Hardware Integration & Operations Guide

> A complete end-to-end handbook for integrating, wiring, configuring, and operating the autonomous face recognition attendance bot on a **Raspberry Pi 4B**.

---

## 📑 Table of Contents
1. [System Architecture Diagram](#1-system-architecture-diagram)
2. [Hardware Bill of Materials (BOM)](#2-hardware-bill-of-materials-bom)
3. [Wiring & Pinout Guide](#3-wiring--pinout-guide)
4. [Power Management & Grounding for Mobile Robots](#4-power-management--grounding-for-mobile-robots)
5. [Raspberry Pi OS Configuration](#5-raspberry-pi-os-configuration)
6. [Software Installation & Optimization](#6-software-installation--optimization)
7. [Operational Workflows](#7-operational-workflows)
8. [Autostart on Boot (Systemd Service)](#8-autostart-on-boot-systemd-service)
9. [Robot Navigation & Optical Tuning Tips](#9-robot-navigation--optical-tuning-tips)
10. [Troubleshooting Matrix](#10-troubleshooting-matrix)

---

## 1. System Architecture Diagram

```
                     ┌───────────────────────────────────┐
                     │    Robot Battery (7.4V - 12V)     │
                     └─┬───────────────────────────────┬─┘
                       │                               │
            ┌──────────▼───────────┐       ┌───────────▼───────────┐
            │ 5V / 3.5A Step-Down  │       │  Motor Driver / MCU   │
            │  Buck Converter      │       │ (e.g. L298N / Arduino)│
            └──────────┬───────────┘       └───────────┬───────────┘
                       │ USB-C                         │
                       ▼                               ▼
       ┌───────────────────────────────┐          Robot Chassis &
       │       Raspberry Pi 4B         │◄─────────Motors (Encoders)
       │      (4GB / 8GB RAM)          │   Common GND
       └───┬───────────────────────┬───┘
           │ USB 2.0 / 3.0         │ 40-Pin GPIO (SPI)
           ▼                       ▼
     ┌─────────────┐       ┌───────────────┐
     │ External    │       │ 2.8" - 3.5"   │
     │ USB Camera  │       │ TFT Display   │
     │ (Wide-Angle)│       │ (ILI9341 /    │
     └─────────────┘       │  ST7789)      │
                           │  [✔] Green    │
                           │  [✖] Red      │
                           └───────────────┘
```

---

## 2. Hardware Bill of Materials (BOM)

| Component | Recommended Specification | Purpose |
|---|---|---|
| **SBC** | Raspberry Pi 4B (4GB or 8GB recommended) | Computer vision inference & robot logic |
| **Camera** | USB Web Camera (1080p/720p, 90°–120° FOV, MJPG support) | Real-time face detection stream |
| **TFT Display** | 2.8" or 3.5" SPI TFT (ST7789 or ILI9341 controller, 320×240) | Visual feedback (Checkmark / Red X) |
| **Power Supply** | 5V 3.5A Buck Converter (LM2596 or XL4015) + LiPo/Li-Ion (2S/3S) | Stable mobile power to avoid undervoltage |
| **Robot Base** | Differential drive / Mecanum chassis + ROS navigation stack | Autonomous hallway/classroom mobility |

---

## 3. Wiring & Pinout Guide

### A. TFT Display (SPI) to Raspberry Pi 4B Pinout

Standard 8-pin SPI TFT modules (e.g., ST7789, ILI9341, Waveshare LCD) connect directly to the Pi's 40-pin GPIO header:

```
Raspberry Pi 4B GPIO Header (Top View):
   3V3  (Pin 1)  [●] [ ] (Pin 2)  5V
                [ ] [ ] (Pin 6)  GND
   MOSI (Pin 19) [●] [ ]
   MISO (Pin 21) [ ] [ ]
   SCLK (Pin 23) [●] [●] (Pin 24) CE0 / CS
   DC   (Pin 22) [●] [ ]
   RST  (Pin 18) [●] [ ]
   BL   (Pin 12) [●] [ ] (PWM Backlight)
```

#### Detailed Pin Connection Table:

| TFT Module Pin | Function | Raspberry Pi 4B Physical Pin | BCM GPIO | Notes |
|---|---|---|---|---|
| **VCC** | Power | **Pin 1** (or Pin 17) | 3.3V Power | Use 3.3V for logic level compatibility |
| **GND** | Ground | **Pin 6** (or Pin 9, 14, 20) | Ground | Connect to common ground |
| **DIN / MOSI** | SPI Data | **Pin 19** | GPIO 10 (MOSI) | Master Out Slave In |
| **CLK / SCLK** | SPI Clock | **Pin 23** | GPIO 11 (SCLK) | High-speed clock line |
| **CS / CE0** | Chip Select | **Pin 24** | GPIO 8 (CE0) | Active low slave select |
| **DC / RS** | Data/Command | **Pin 22** | GPIO 25 | Distinguishes data from commands |
| **RST / RES** | Reset | **Pin 18** | GPIO 24 | Hardware reset line |
| **BL / LED** | Backlight | **Pin 12** | GPIO 18 (PWM) | Can tie to 3.3V for always-on |

> [!NOTE]
> If you are using a **HAT-style TFT screen** (e.g., Waveshare 3.5" LCD Hat), simply snap it directly onto the 40-pin GPIO header. No jumper wires required!

---

### B. External USB Camera Connection

1. Plug the external USB camera into one of the **Black USB 2.0 ports** on the Raspberry Pi 4B.
   * *Why USB 2.0?* USB 3.0 ports on single-board computers emit broadband RF noise in the 2.4 GHz band, which can degrade Wi-Fi and Bluetooth communication on autonomous robots. USB 2.0 provides more than enough bandwidth for 640×480 MJPG video at 30 FPS.
2. Confirm the camera is recognized:
   ```bash
   ls -l /dev/video*
   ```
   You should see `/dev/video0` and `/dev/video1`.

---

## 4. Power Management & Grounding for Mobile Robots

A leading cause of Raspberry Pi crashes on robots is **motor surge voltage drops (brownouts)**.

### Best Practices:
1. **Isolate Pi Power from Motor Power**:
   - Use a dedicated **high-current 5V 3.5A Step-Down Buck Converter** exclusively for the Raspberry Pi USB-C power input.
   - Do **NOT** power the Pi from the 5V output pin of an L298N motor driver (it is limited to 500mA and will brownout immediately).
2. **Common Ground**:
   - Tie the **GND** of the Pi power supply and the **GND** of the motor controller together. This ensures signal reference consistency without ground loops.
3. **Mounting Vibration Isolation**:
   - Mount the camera with a rubber dampener or gimbal to prevent motor vibration from causing blurry images while the robot navigates.

---

## 5. Raspberry Pi OS Configuration

Log into your Raspberry Pi via SSH or monitor:

### Step 1: Enable SPI & I2C Interfaces
```bash
sudo raspi-config
```
- Navigate to **Interface Options** → **SPI** → **Enable (Yes)**.
- Navigate to **Interface Options** → **I2C** → **Enable (Yes)**.
- Finish and reboot.

### Step 2: Configure Framebuffer (If using Waveshare/SPI TFT)
Add your display overlay to `/boot/firmware/config.txt` (or `/boot/config.txt` on older OS):
```ini
# Example for Waveshare 3.5" or ST7789 TFT:
dtoverlay=waveshare35a:rotate=90
```
Reboot:
```bash
sudo reboot
```
Verify the framebuffer device `/dev/fb1` exists:
```bash
ls -l /dev/fb*
# Output should show: /dev/fb0 and /dev/fb1
```

---

## 6. Software Installation & Optimization

Clone or copy the project into your Pi's home directory:
```bash
cd ~
git clone <your-repo-url> rosprojectattendance
cd rosprojectattendance
```

Run the automated one-click optimizer script:
```bash
chmod +x pi_setup.sh
./pi_setup.sh
```

### What this script configures:
- ⚡ **Expands Swap Memory to 2048 MB**: Crucial for compiling `dlib` without crashing the Pi 4B RAM.
- 📦 **Installs BLAS & LAPACK Hardware Accelerators**: Maximizes vector math speed on the Cortex-A72 CPU.
- 🐍 **Installs Python Packages**: Sets up OpenCV, dlib, face_recognition, openpyxl, Pillow.
- 📷 **Checks V4L2 Device Permissions**: Ensures the camera is accessible without root.

---

## 7. Operational Workflows

### 📋 Phase 1: Enrolling Students into Database

You can register students either with the interactive GUI or in bulk:

#### Option A: In-App Camera Registration (GUI)
1. Launch the GUI on a monitor or via VNC:
   ```bash
   python3 main.py
   ```
2. Click **"➕ Register Student"**.
3. Enter First Name, Last Name, and Student ID (e.g. `John`, `Doe`, `001`).
4. Stand in front of the robot's camera and click **"📸 Capture Photo"** 5 times from slightly different angles.
5. Click **"💾 Save & Train"**. The model will encode the embeddings in ~2 seconds!

#### Option B: Bulk Enrollment (Headless / Remote)
Organize portrait photos into `dataset/` following this naming convention:
```
dataset/
├── Alice_Walker_CS101/
│   ├── img_001.jpg
│   └── img_002.jpg
└── Bob_Miller_CS102/
    ├── img_001.jpg
    └── img_002.jpg
```
Then run the encoder:
```bash
python3 encoder.py --rebuild
```

---

### 🤖 Phase 2: Autonomous Attendance Operation

Depending on how your robot is operated, pick one of the following:

#### Workflow A: Autonomous Headless Mode (Robot Moving Around)
*Best for robots with a TFT display and no large HDMI monitor:*
```bash
python3 headless.py --cam 0 --export-interval 10
```
- The camera runs smoothly in the background.
- When an enrolled student approaches the robot:
  - The TFT flashes a **glowing Green Checkmark (✔)** with their Name and ID.
  - The student's attendance is marked in memory and appended to `attendance_YYYY-MM-DD.csv`.
- When an unrecognized person steps in front of the robot:
  - The TFT flashes a **bold Red X Mark (✖)** with "ACCESS DENIED / NOT REGISTERED".
- Excel report is automatically updated every 10 minutes in `attendance_records/`.

#### Workflow B: ROS 2 Humble Autonomous Navigation & Attendance Node
*For mobile robots running ROS 2 Humble with `/cmd_vel` motor control:*
```bash
python3 ros_attendance_node.py
```
This node implements an autonomous Navigation Finite State Machine (FSM):
1. **State `'SEARCHING'`**:
   - Publishes rotational velocity on `/cmd_vel` (`geometry_msgs/msg/Twist`: `angular.z = 0.3`, `linear.x = 0.0`).
   - The robot slowly rotates in place to scan the classroom/hallway for student faces.
2. **State `'LOCKED'`**:
   - When a student face in the database is verified, the node **instantly halts all robot movement** (`angular.z = 0.0`, `linear.x = 0.0`).
   - Holds position for **5 seconds** while attendance is logged and the **Green Checkmark (✔)** is displayed on the TFT screen.
   - Publishes attendance data to `/attendance/student_id`, `/attendance/student_name`, `/attendance/total_count`, and `/attendance/state`.
   - After the 5-second cooldown elapses, the FSM automatically transitions back to `'SEARCHING'` to continue patrolling.

---

## 8. Autostart on Boot (Systemd Service)

To make the attendance system start automatically when the robot is powered on:

### 1. Create a Systemd Service File
```bash
sudo nano /etc/systemd/system/attendance_robot.service
```

Paste the following configuration:
```ini
[Unit]
Description=ROS Attendance Robot Autonomous Service
After=network.target multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/rosprojectattendance
ExecStart=/usr/bin/python3 /home/pi/rosprojectattendance/main.py --headless --export-interval 5
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/pi/rosprojectattendance/logs/service.log
StandardError=append:/home/pi/rosprojectattendance/logs/service.log

[Install]
WantedBy=multi-user.target
```
*(Replace `/home/pi` with your actual username path if different, e.g. `/home/ubuntu`)*

### 2. Enable and Start the Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable attendance_robot.service
sudo systemctl start attendance_robot.service
```

### 3. Check Service Status
```bash
sudo systemctl status attendance_robot.service
```
The robot will now autonomously boot, initialize the camera, power the TFT screen, and mark attendance whenever turned on!

---

## 9. Robot Navigation & Optical Tuning Tips

For reliable face recognition while a robot moves autonomously through classrooms or corridors:

1. **Camera Height & Pitch Angle**:
   - Mount the camera at **1.1m to 1.3m (3.5 to 4.2 feet)** from the ground.
   - Tilt the camera upwards by **10°–15°** so it naturally frames faces of both standing and seated students.
2. **Motion Blur Mitigation**:
   - In `config.py`, `FPS_TARGET = 30` and `USE_MJPG = True` maintain low camera exposure times.
   - Program your robot's navigation script to **decelerate or pause for 1.5 seconds** when obstacles/people are detected by sonar or LiDAR to allow a sharp, blur-free frame capture.
3. **Lighting Compensation**:
   - Avoid pointing the robot's camera directly toward bright windows (backlighting washes out facial landmarks).
   - If operating in dimly lit spaces, add two 5V white LED diffuser pods beside the camera lens.
4. **Distance & Tolerance in `config.py`**:
   - `RECOGNITION_TOLERANCE = 0.50` is optimal for 1.5m to 2.5m distance.
   - If you want the robot to only register people very close (<1m), set `RECOGNITION_TOLERANCE = 0.44`.

---

## 10. Troubleshooting Matrix

| Symptom | Root Cause | Solution |
|---|---|---|
| **Camera not opening (`[ERROR] Camera 0 not accessible`)** | Camera index mismatch or permission issue | Run `ls -l /dev/video*`. If external camera is index 1, change `CAMERA_INDEX = 1` in `config.py`. Add user to group: `sudo usermod -aG video $USER`. |
| **TFT screen stays completely white / black** | SPI interface disabled or wrong device path | Run `sudo raspi-config` → Interface → Enable SPI. Check if `/dev/fb1` exists. Ensure `TFT_FB_DEVICE = "/dev/fb1"` in `config.py`. |
| **Video feed is laggy or delayed by several seconds** | Framebuffer queue backlog | The project already incorporates decoupled `CamGrabber` threads. Verify `USE_MJPG = True` and `PROCESS_SCALE = 0.33` in `config.py`. |
| **Pi freezes during pip install / dlib build** | Out of memory during C++ compile | Run `./pi_setup.sh` to expand swap to 2048 MB. Do not compile with `-j4` on a 2GB Pi model. |
| **Face labeled "Unknown" even when registered** | High facial angle deviation or lighting discrepancy | Add 2–3 photos taken under room lighting with slight head rotation to `dataset/` and run `python3 encoder.py --rebuild`. |
| **Excel file is empty on robot shutdown** | Robot was powered off abruptly by battery switch | Always allow graceful shutdown via `Ctrl+C` or systemd service stop. The system auto-exports incrementally to CSV after every single mark. |

---

## 🏁 Summary Checklist Before Deploying Robot

- [ ] USB Camera securely fastened at 10°–15° upward angle.
- [ ] TFT display connected to SPI pins (or LCD hat mounted).
- [ ] `./pi_setup.sh` completed successfully.
- [ ] Students registered and `face_encodings.pkl` generated.
- [ ] Quick test run: `python3 tft_display.py` displays Green Checkmark and Red X.
- [ ] Launch `python3 headless.py` or enable `attendance_robot.service`.
- [ ] Verify generated Excel report in `attendance_records/`.
