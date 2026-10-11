"""
=============================================================================
 ROS Attendance Bot — Unified Master Application
 Runs all robot features cooperatively from this single file:
   1. Real-time Face Recognition & Confirmation Engine (Pi 4B 0-latency)
   2. ROS 2 Humble Navigation State Machine (/cmd_vel: SEARCHING & LOCKED)
   3. Hardware / Simulated TFT Display (Green Checkmark, Red X, Radar)
   4. Live Dark-Themed GUI Dashboard (with fallback to Headless mode)
   5. Real-Time CSV Logging & Formatted Excel Workbooks (.xlsx)
   6. In-App Student Registration Wizard & Model Re-training
=============================================================================
Usage:
    python3 main.py                 # Auto-detects display; runs GUI or Headless
    python3 main.py --headless      # Forces autonomous headless robot mode
    python3 main.py --no-nav        # Runs without /cmd_vel navigation commands
    python3 main.py --no-tft        # Disables TFT display feedback
    python3 main.py --cam 1         # Uses external USB camera at index 1
=============================================================================
"""

import os
import sys
import time
import signal
import platform
import logging
import argparse
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from tkinter import (
    Tk, Frame, Label, Button, Canvas, Entry, StringVar,
    LabelFrame, ttk, messagebox, filedialog, PhotoImage, Toplevel,
    scrolledtext
)
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2
import numpy as np

import config
from encoder import encode_faces
from attendance import AttendanceManager
from recognition_engine import RecognitionEngine
from tft_display import TFTDisplay

# ── Logging ──────────────────────────────────────────────────────────────────
Path(config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.LOGS_DIR, "app.log")),
    ],
)
log = logging.getLogger(__name__)

T = config.THEME


# ─────────────────────────────────────────────────────────────────────────────
# ROS 2 Humble Autonomous Navigation State Machine Controller
# ─────────────────────────────────────────────────────────────────────────────
class RobotNavigationFSM:
    """
    Manages autonomous movement and state transitions:
      - 'SEARCHING' : Rotates in place (angular.z = 0.3) to scan environment
      - 'LOCKED'    : Freezes all movement (0.0 vel) for 5s cooldown when attendance is verified
    Publishes to /cmd_vel and /attendance/* topics.
    """

    STATE_SEARCHING = "SEARCHING"
    STATE_LOCKED    = "LOCKED"
    LOCKED_COOLDOWN = 5.0  # seconds to hold position after face recognition

    def __init__(self, on_state_changed=None, enabled=True):
        self.enabled = enabled
        self.on_state_changed = on_state_changed or (lambda s: None)
        self._state_lock       = threading.Lock()
        self._state            = self.STATE_SEARCHING
        self._locked_timestamp = 0.0
        self._running          = True

        self._ros2_node        = None
        self._cmd_vel_pub      = None
        self._pub_state        = None
        self._pub_student_id   = None
        self._pub_student_name = None
        self._pub_total_count  = None
        self._pub_unknown      = None

        if self.enabled:
            self._init_ros2()
            self._timer_thread = threading.Thread(target=self._control_loop, daemon=True, name="NavFSM")
            self._timer_thread.start()

    def _init_ros2(self):
        try:
            import rclpy
            from geometry_msgs.msg import Twist
            from std_msgs.msg import String, Int32

            if not rclpy.ok():
                rclpy.init()
            self._ros2_node = rclpy.create_node("attendance_navigation_node")
            self._cmd_vel_pub      = self._ros2_node.create_publisher(Twist, "/cmd_vel", 10)
            self._pub_state        = self._ros2_node.create_publisher(String, "/attendance/state", 10)
            self._pub_student_id   = self._ros2_node.create_publisher(String, "/attendance/student_id", 10)
            self._pub_student_name = self._ros2_node.create_publisher(String, "/attendance/student_name", 10)
            self._pub_total_count  = self._ros2_node.create_publisher(Int32, "/attendance/total_count", 10)
            self._pub_unknown      = self._ros2_node.create_publisher(String, "/attendance/unknown_alert", 10)

            # Spin in background thread so ROS 2 callbacks & publishers run smoothly
            self._spin_thread = threading.Thread(
                target=lambda: rclpy.spin(self._ros2_node),
                daemon=True, name="ROS2Spin"
            )
            self._spin_thread.start()
            log.info("ROS 2 Humble /cmd_vel and /attendance/* topics initialized")
        except ImportError:
            log.info("ROS 2 (rclpy) not found in environment. Running Navigation FSM in standalone mode.")
        except Exception as e:
            log.warning("Could not initialize ROS 2 node: %s", e)

    def _control_loop(self):
        rate = 0.1  # 10 Hz
        while self._running:
            start_t = time.time()
            with self._state_lock:
                now = time.time()
                if self._state == self.STATE_LOCKED:
                    if now - self._locked_timestamp >= self.LOCKED_COOLDOWN:
                        self._state = self.STATE_SEARCHING
                        log.info("🔄 [FSM -> SEARCHING] 5s cooldown elapsed. Resuming rotational scan.")
                        self._publish_state_str(self.STATE_SEARCHING)
                        try:
                            self.on_state_changed(self.STATE_SEARCHING)
                        except Exception:
                            pass
                    else:
                        self._publish_stop()
                elif self._state == self.STATE_SEARCHING:
                    self._publish_search_spin()

            elapsed = time.time() - start_t
            time.sleep(max(0.01, rate - elapsed))

    def lock_target(self, name: str, sid: str, count: int = 0):
        """Switches FSM into LOCKED state, stops robot movement, and holds for 5s."""
        if not self.enabled:
            return
        with self._state_lock:
            self._state = self.STATE_LOCKED
            self._locked_timestamp = time.time()
            self._publish_stop()
            self._publish_state_str(self.STATE_LOCKED)
            log.info("🔒 [FSM -> LOCKED] Target '%s' (%s) verified. Stopping robot for 5s cooldown.", name, sid)

        self._publish_attendance_topics(sid, name, count)
        try:
            self.on_state_changed(self.STATE_LOCKED)
        except Exception:
            pass

    def broadcast_unknown(self):
        """Publishes alert when an unregistered face is seen."""
        if not self.enabled or not self._pub_unknown:
            return
        try:
            from std_msgs.msg import String
            msg = String()
            msg.data = "Unregistered face detected"
            self._pub_unknown.publish(msg)
        except Exception:
            pass

    def _publish_search_spin(self):
        if self._cmd_vel_pub:
            try:
                from geometry_msgs.msg import Twist
                t = Twist()
                t.angular.z = 0.3
                self._cmd_vel_pub.publish(t)
            except Exception:
                pass

    def _publish_stop(self):
        if self._cmd_vel_pub:
            try:
                from geometry_msgs.msg import Twist
                t = Twist()
                self._cmd_vel_pub.publish(t)
            except Exception:
                pass

    def _publish_state_str(self, s: str):
        if self._pub_state:
            try:
                from std_msgs.msg import String
                msg = String()
                msg.data = s
                self._pub_state.publish(msg)
            except Exception:
                pass

    def _publish_attendance_topics(self, sid: str, name: str, count: int):
        if self._pub_student_id:
            try:
                from std_msgs.msg import String, Int32
                m_sid   = String(); m_sid.data   = sid
                m_name  = String(); m_name.data  = name
                m_count = Int32();  m_count.data = count
                self._pub_student_id.publish(m_sid)
                self._pub_student_name.publish(m_name)
                self._pub_total_count.publish(m_count)
            except Exception:
                pass

    def stop(self):
        self._running = False
        self._publish_stop()
        if self._ros2_node:
            try:
                self._ros2_node.destroy_node()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Helper: styled button factory
# ─────────────────────────────────────────────────────────────────────────────
def make_btn(parent, text, cmd, bg=None, fg=None, width=18, padx=8, pady=6, font=None):
    return Button(
        parent, text=text, command=cmd,
        bg=bg or T["accent"], fg=fg or T["bg_dark"],
        activebackground=T["accent2"], activeforeground=T["bg_dark"],
        font=font or T["font_body"],
        relief="flat", cursor="hand2",
        width=width, padx=padx, pady=pady,
        bd=0, highlightthickness=0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Register-Student Dialog
# ─────────────────────────────────────────────────────────────────────────────
class RegisterDialog(Toplevel):
    """Modal dialog: capture N photos for a new student from camera."""

    def __init__(self, parent, engine: RecognitionEngine, on_done=None):
        super().__init__(parent)
        self.engine   = engine
        self.on_done  = on_done or (lambda: None)
        self._cap     = None
        self._running = False
        self._captures: list[np.ndarray] = []

        self.title("Register New Student")
        self.configure(bg=T["bg_dark"])
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._start_preview()

    def _build_ui(self):
        hdr = Frame(self, bg=T["bg_card"])
        hdr.pack(fill="x")
        Label(hdr, text="📷  Register New Student",
              bg=T["bg_card"], fg=T["accent"],
              font=T["font_title"]).pack(pady=12, padx=20, anchor="w")

        body = Frame(self, bg=T["bg_dark"])
        body.pack(padx=20, pady=10)

        # Camera preview
        self.canvas = Canvas(body, width=480, height=360,
                              bg=T["bg_panel"], highlightthickness=1,
                              highlightbackground=T["border"])
        self.canvas.grid(row=0, column=0, rowspan=8, padx=(0, 16))

        # Form
        frm = Frame(body, bg=T["bg_dark"])
        frm.grid(row=0, column=1, sticky="nw")

        def lbl(text):
            return Label(frm, text=text, bg=T["bg_dark"],
                         fg=T["text_muted"], font=T["font_small"])

        def ent():
            return Entry(frm, bg=T["bg_panel"], fg=T["text_primary"],
                         insertbackground=T["accent"], relief="flat",
                         font=T["font_body"], width=20)

        lbl("First Name").pack(anchor="w", pady=(0, 2))
        self.e_first = ent(); self.e_first.pack(pady=(0, 8))

        lbl("Last Name").pack(anchor="w", pady=(0, 2))
        self.e_last  = ent(); self.e_last.pack(pady=(0, 8))

        lbl("Student ID").pack(anchor="w", pady=(0, 2))
        self.e_id    = ent(); self.e_id.pack(pady=(0, 8))

        self.status_var = StringVar(value="Position face in frame, then capture.")
        Label(frm, textvariable=self.status_var, bg=T["bg_dark"],
              fg=T["accent2"], font=T["font_small"], wraplength=180,
              justify="left").pack(pady=(8, 4))

        self.progress_var = StringVar(value="Photos: 0 / 5")
        Label(frm, textvariable=self.progress_var, bg=T["bg_dark"],
              fg=T["text_primary"], font=T["font_body"]).pack(pady=4)

        make_btn(frm, "📸  Capture Photo", self._capture,
                 width=20).pack(pady=4, fill="x")
        make_btn(frm, "💾  Save & Train", self._save,
                 bg=T["accent2"], width=20).pack(pady=4, fill="x")
        make_btn(frm, "✖  Cancel", self.destroy,
                 bg=T["warning"], width=20).pack(pady=4, fill="x")

    def _start_preview(self):
        self.engine.pause()
        if platform.system() == "Linux":
            try:
                self._cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_V4L2)
                if config.USE_MJPG:
                    self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            except Exception:
                self._cap = cv2.VideoCapture(config.CAMERA_INDEX)
        else:
            self._cap = cv2.VideoCapture(config.CAMERA_INDEX)

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self._running = True
        threading.Thread(target=self._preview_loop, daemon=True).start()

    def _preview_loop(self):
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.03)
                continue
            frame = cv2.flip(frame, 1)
            img   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = cv2.resize(img, (480, 360))
            pil   = Image.fromarray(img)
            photo = ImageTk.PhotoImage(pil)
            try:
                self.canvas.create_image(0, 0, anchor="nw", image=photo)
                self.canvas._photo = photo
            except Exception:
                break
            time.sleep(0.03)  # Throttle to 30 FPS

    def _capture(self):
        ret, frame = self._cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            self._captures.append(frame)
            n = len(self._captures)
            self.progress_var.set(f"Photos: {n} / 5")
            self.status_var.set(f"✅ Captured {n} photo(s). {'Ready to save!' if n >= 3 else 'Take more.'}")

    def _save(self):
        first = self.e_first.get().strip()
        last  = self.e_last.get().strip()
        sid   = self.e_id.get().strip()

        if not (first and last and sid):
            messagebox.showerror("Missing Info", "Please fill in all fields.", parent=self)
            return
        if len(self._captures) < 3:
            messagebox.showwarning("Not Enough Photos", "Capture at least 3 photos.", parent=self)
            return

        folder_name = f"{first}_{last}_{sid}"
        save_dir    = Path(config.DATASET_DIR) / folder_name
        save_dir.mkdir(parents=True, exist_ok=True)

        for i, cap in enumerate(self._captures):
            cv2.imwrite(str(save_dir / f"img_{i+1:03d}.jpg"), cap)

        self.status_var.set("⚙️ Training model… please wait.")
        self.update()

        threading.Thread(target=self._retrain, daemon=True).start()

    def _retrain(self):
        try:
            encode_faces(rebuild=True)
            self.after(0, self._finish_training)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Encoding Error", str(e), parent=self))

    def _finish_training(self):
        self._running = False
        self._cap.release()
        self.engine.reload_encodings()
        self.engine.resume()
        messagebox.showinfo("Success", "Student registered and model updated! ✅", parent=self)
        self.on_done()
        self.destroy()

    def destroy(self):
        self._running = False
        if self._cap:
            self._cap.release()
        self.engine.resume()
        super().destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Main Application Window (GUI Mode)
# ─────────────────────────────────────────────────────────────────────────────
class AttendanceApp(Tk):
    def __init__(self, nav_enabled=True, tft_enabled=True):
        super().__init__()
        self.title("🤖  ROS Attendance Bot")
        self.configure(bg=T["bg_dark"])
        try:
            self.state("zoomed")
        except Exception:
            self.geometry("1200x800")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Core Services ──
        self.att_mgr = AttendanceManager()

        # TFT Display Controller
        self.tft = None
        if tft_enabled and config.TFT_ENABLED:
            try:
                self.tft = TFTDisplay()
                self.tft.show_idle(total_count=self.att_mgr.get_count())
            except Exception as e:
                log.warning("Could not initialize TFT display: %s", e)

        # Autonomous Navigation FSM (/cmd_vel)
        self.nav_fsm = RobotNavigationFSM(
            on_state_changed=self._on_nav_state_changed,
            enabled=nav_enabled
        )

        # Recognition Engine
        self.engine  = RecognitionEngine(
            attendance_manager=self.att_mgr,
            on_face_detected=self._on_face_detected,
            on_unknown_detected=self._on_unknown_detected,
            on_frame=self._on_new_frame,
            on_status=self._on_status,
        )

        self._last_frame: np.ndarray | None = None
        self._notification_ids: list[str]   = []

        self._build_ui()
        self.engine.start()

        # Periodic UI refreshes & auto-export
        self._refresh_table()
        self._tick_clock()
        self._schedule_auto_export()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()

        content = Frame(self, bg=T["bg_dark"])
        content.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self._build_camera_panel(content)
        self._build_right_panel(content)

    def _build_topbar(self):
        bar = Frame(self, bg=T["bg_card"], height=60)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Title
        Label(bar, text="🤖  ROS Attendance Bot",
              bg=T["bg_card"], fg=T["accent"],
              font=T["font_head"]).pack(side="left", padx=20, pady=10)

        # Live clock
        self.clock_var = StringVar()
        Label(bar, textvariable=self.clock_var,
              bg=T["bg_card"], fg=T["text_muted"],
              font=T["font_body"]).pack(side="right", padx=16)

        # Navigation State Badge
        self.nav_var = StringVar(value="NAV: SEARCHING 🔄")
        self.nav_badge = Label(bar, textvariable=self.nav_var,
                               bg="#1C2D42", fg="#58A6FF",
                               font=T["font_small"], padx=8, pady=3)
        self.nav_badge.pack(side="right", padx=10)

        # Status badge
        self.status_var = StringVar(value="Ready")
        Label(bar, textvariable=self.status_var,
              bg=T["bg_card"], fg=T["accent2"],
              font=T["font_small"]).pack(side="right", padx=12)

        # Count badge
        self.count_var = StringVar(value="Present: 0")
        Label(bar, textvariable=self.count_var,
              bg=T["bg_card"], fg=T["text_primary"],
              font=T["font_title"]).pack(side="right", padx=16)

    def _build_camera_panel(self, parent):
        cam_frame = Frame(parent, bg=T["bg_dark"])
        cam_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        cam_frame.rowconfigure(0, weight=1)
        cam_frame.columnconfigure(0, weight=1)

        self.cam_canvas = Canvas(cam_frame, bg=T["bg_panel"],
                                  highlightthickness=2,
                                  highlightbackground=T["border"])
        self.cam_canvas.grid(row=0, column=0, sticky="nsew")

        self.cam_canvas.create_text(
            400, 300, text="📷  Connecting to Camera…",
            fill=T["text_muted"], font=T["font_title"], tags="placeholder"
        )

        self.notif_frame = Frame(cam_frame, bg=T["bg_dark"])
        self.notif_frame.grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _build_right_panel(self, parent):
        right = Frame(parent, bg=T["bg_dark"])
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Controls card
        ctrl = Frame(right, bg=T["bg_card"])
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        Label(ctrl, text="⚙️  Controls", bg=T["bg_card"],
              fg=T["accent"], font=T["font_title"]).pack(pady=(12, 6), padx=12, anchor="w")

        btns = Frame(ctrl, bg=T["bg_card"])
        btns.pack(padx=12, pady=(0, 12), fill="x")

        make_btn(btns, "➕  Register Student",
                 self._open_register, width=22).pack(fill="x", pady=2)

        make_btn(btns, "🔄  Re-train Model",
                 self._retrain_model, bg=T["bg_panel"],
                 fg=T["accent"], width=22).pack(fill="x", pady=2)

        self.pause_btn = make_btn(btns, "⏸  Pause Camera",
                                   self._toggle_pause,
                                   bg=T["bg_panel"], fg=T["text_primary"],
                                   width=22)
        self.pause_btn.pack(fill="x", pady=2)

        make_btn(btns, "📊  Export Excel",
                 self._export_excel, bg=T["accent2"], width=22).pack(fill="x", pady=2)

        make_btn(btns, "📂  Open Records",
                 self._open_records_folder, bg=T["bg_panel"],
                 fg=T["text_muted"], width=22).pack(fill="x", pady=2)

        # Attendance Table
        tbl_frame = Frame(right, bg=T["bg_card"])
        tbl_frame.grid(row=1, column=0, sticky="nsew")
        tbl_frame.rowconfigure(1, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        Label(tbl_frame, text="📋  Today's Attendance",
              bg=T["bg_card"], fg=T["accent"],
              font=T["font_title"]).grid(row=0, column=0, pady=(12, 6), padx=12, sticky="w")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Att.Treeview",
                         background=T["bg_panel"],
                         foreground=T["text_primary"],
                         fieldbackground=T["bg_panel"],
                         rowheight=28,
                         font=T["font_small"])
        style.configure("Att.Treeview.Heading",
                         background=T["bg_card"],
                         foreground=T["accent"],
                         font=T["font_body"],
                         relief="flat")
        style.map("Att.Treeview",
                  background=[("selected", T["accent"])],
                  foreground=[("selected", T["bg_dark"])])

        cols = ("id", "name", "time", "status")
        self.tree = ttk.Treeview(tbl_frame, columns=cols,
                                  show="headings", style="Att.Treeview")

        col_conf = {
            "id":     ("ID",     70,  "center"),
            "name":   ("Name",   140, "w"),
            "time":   ("Time",   80,  "center"),
            "status": ("Status", 70,  "center"),
        }
        for col, (hdr, w, anc) in col_conf.items():
            self.tree.heading(col, text=hdr)
            self.tree.column(col, width=w, anchor=anc, stretch=True)

        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        sb.grid(row=1, column=1, sticky="ns", pady=(0, 12), padx=(0, 4))

        # Log box
        log_frame = Frame(right, bg=T["bg_card"])
        log_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        Label(log_frame, text="📝  System Log", bg=T["bg_card"],
              fg=T["accent"], font=T["font_small"]).pack(anchor="w", padx=12, pady=(8, 2))

        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=5, bg=T["bg_panel"],
            fg=T["text_muted"], font=T["font_code"],
            relief="flat", insertbackground=T["accent"],
            state="disabled",
        )
        self.log_box.pack(fill="x", padx=12, pady=(0, 10))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_new_frame(self, frame: np.ndarray):
        self._last_frame = frame
        self.after(0, self._draw_frame)

    def _draw_frame(self):
        if self._last_frame is None:
            return
        frame = self._last_frame
        w = self.cam_canvas.winfo_width()
        h = self.cam_canvas.winfo_height()
        if w < 2 or h < 2:
            return

        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (w, h))
        pil   = Image.fromarray(img)
        photo = ImageTk.PhotoImage(pil)
        self.cam_canvas.delete("placeholder")
        self.cam_canvas.create_image(0, 0, anchor="nw", image=photo)
        self.cam_canvas._photo = photo

    def _on_face_detected(self, name: str, sid: str, frame: np.ndarray, boxes):
        """Triggered when student is verified in database."""
        # 1. Update TFT with Green Checkmark
        if self.tft:
            self.tft.show_success(name, sid)

        # 2. Trigger Navigation FSM to halt robot
        self.nav_fsm.lock_target(name, sid, self.att_mgr.get_count())

        # 3. GUI feedback
        self.after(0, lambda: self._show_notification(name, sid))
        self.after(0, self._refresh_table)
        self._log(f"✅ Marked: {name} (ID: {sid})")

    def _on_unknown_detected(self, frame: np.ndarray, boxes):
        """Triggered when an unregistered face is observed."""
        if self.tft:
            self.tft.show_unknown()
        self.nav_fsm.broadcast_unknown()
        self.after(0, self._show_unknown_notification)
        self._log("⚠️ Unknown person detected (Not in database)")

    def _on_nav_state_changed(self, state: str):
        """Updates Navigation State Badge in GUI topbar."""
        def _update():
            if state == RobotNavigationFSM.STATE_LOCKED:
                self.nav_var.set("NAV: LOCKED 🔒 (Halted)")
                self.nav_badge.config(bg="#3D201A", fg="#F78166")
            else:
                self.nav_var.set("NAV: SEARCHING 🔄")
                self.nav_badge.config(bg="#1C2D42", fg="#58A6FF")
        self.after(0, _update)

    def _show_notification(self, name: str, sid: str):
        banner = Frame(self.notif_frame, bg=T["success"])
        banner.pack(fill="x", pady=1)
        Label(banner,
              text=f"✅  {name}  (ID: {sid})  marked Present at {datetime.now().strftime('%H:%M:%S')}",
              bg=T["success"], fg="white",
              font=T["font_body"]).pack(pady=4, padx=12)
        self.after(4000, banner.destroy)

    def _show_unknown_notification(self):
        banner = Frame(self.notif_frame, bg=T["warning"])
        banner.pack(fill="x", pady=1)
        Label(banner,
              text=f"❌  Unknown person detected — Not in database!",
              bg=T["warning"], fg="white",
              font=T["font_body"]).pack(pady=4, padx=12)
        self.after(4000, banner.destroy)

    def _on_status(self, msg: str):
        self.after(0, lambda: self.status_var.set(msg))
        if self.tft:
            self.tft.update_status(msg)
        self._log(msg)

    # ── Table & Helpers ───────────────────────────────────────────────────────

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for rec in self.att_mgr.get_records():
            tag = "present" if rec["status"] == "Present" else "absent"
            self.tree.insert("", "end", values=(
                rec["id"], rec["name"], rec["time"], rec["status"]
            ), tags=(tag,))
        self.tree.tag_configure("present", foreground=T["accent2"])
        self.count_var.set(f"Present: {self.att_mgr.get_count()}")

    def _open_register(self):
        RegisterDialog(self, self.engine, on_done=self._refresh_table)

    def _retrain_model(self):
        if not messagebox.askyesno("Re-train", "Rebuild face encodings from dataset/?"):
            return
        self._log("⚙️ Re-training model…")
        def _do():
            encode_faces(rebuild=True)
            self.engine.reload_encodings()
            self.after(0, lambda: [
                self._log("✅ Model re-trained"),
                messagebox.showinfo("Done", "Model re-trained successfully!")
            ])
        threading.Thread(target=_do, daemon=True).start()

    _paused = False
    def _toggle_pause(self):
        if self._paused:
            self.engine.resume()
            self.pause_btn.config(text="⏸  Pause Camera")
            self._paused = False
        else:
            self.engine.pause()
            self.pause_btn.config(text="▶  Resume Camera")
            self._paused = True

    def _export_excel(self):
        init_file = f"attendance_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialfile=init_file,
            initialdir=config.ATTENDANCE_DIR,
        )
        if not path:
            return
        try:
            out = self.att_mgr.export_excel(path)
            self._log(f"📊 Excel exported → {out}")
            if messagebox.askyesno("Open File?", f"Exported!\n\nOpen {out}?"):
                _open_file(out)
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
            log.exception("Excel export failed")

    def _schedule_auto_export(self):
        """Auto-export snapshot every 5 minutes in background."""
        try:
            self.att_mgr.export_excel()
        except Exception:
            pass
        self.after(300000, self._schedule_auto_export)

    def _open_records_folder(self):
        _open_file(config.ATTENDANCE_DIR)

    def _log(self, msg: str):
        def _do():
            self.log_box.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_box.insert("end", f"[{ts}]  {msg}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _do)

    def _tick_clock(self):
        self.clock_var.set(datetime.now().strftime("📅 %a, %d %b   🕐 %H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _on_close(self):
        if messagebox.askyesno("Quit", "Stop attendance session and exit?"):
            self.engine.stop()
            self.nav_fsm.stop()
            if self.tft:
                self.tft.close()
            final_p = self.att_mgr.export_excel()
            log.info("Final Excel snapshot saved -> %s", final_p)
            self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Unified Headless Runner (Autonomous Robot Mode without Display)
# ─────────────────────────────────────────────────────────────────────────────
def run_headless(nav_enabled=True, tft_enabled=True, export_interval=10):
    """
    Executes all robot features in unified headless mode:
      - 0-latency camera thread
      - HOG recognition engine
      - ROS 2 /cmd_vel navigation state machine (SEARCHING / LOCKED)
      - TFT visual feedback (Green Checkmark / Red X / Radar)
      - Periodic Excel auto-export & incremental CSV logging
    """
    log.info("══════════════════════════════════════════════════════════════════")
    log.info("  🤖 ROS Attendance Bot — Autonomous Headless Robot Runner")
    log.info("  Active Features:")
    log.info("    ✓ Pi 4B Camera Telemetry (0-Latency Grabber)")
    log.info("    ✓ Face Recognition & Multi-Frame Confirmation")
    log.info("    ✓ ROS 2 /cmd_vel FSM: %s", "ENABLED" if nav_enabled else "DISABLED")
    log.info("    ✓ TFT Screen Feedback: %s", "ENABLED" if tft_enabled else "DISABLED")
    log.info("    ✓ Formatted Excel Reporting (Every %d min)", export_interval)
    log.info("══════════════════════════════════════════════════════════════════")

    encode_faces(rebuild=False)

    att_mgr = AttendanceManager()
    tft     = None
    if tft_enabled and config.TFT_ENABLED:
        try:
            tft = TFTDisplay()
            tft.show_idle(total_count=att_mgr.get_count())
        except Exception as e:
            log.warning("Could not initialize TFT display: %s", e)

    nav_fsm = RobotNavigationFSM(enabled=nav_enabled)

    def on_face_detected(name, sid, frame, boxes):
        log.info("🎯 TARGET VERIFIED: %s (ID: %s)", name, sid)
        if tft:
            tft.show_success(name, sid)
        nav_fsm.lock_target(name, sid, att_mgr.get_count())

    def on_unknown_detected(frame, boxes):
        log.warning("⚠️ UNKNOWN PERSON DETECTED — Not in database!")
        if tft:
            tft.show_unknown()
        nav_fsm.broadcast_unknown()

    def on_status(s):
        log.info("STATUS: %s", s)
        if tft:
            tft.update_status(s)

    engine = RecognitionEngine(
        attendance_manager=att_mgr,
        on_face_detected=on_face_detected,
        on_unknown_detected=on_unknown_detected,
        on_status=on_status,
    )
    engine.start()

    def shutdown(sig=None, frame=None):
        log.info("Shutting down unified runner…")
        engine.stop()
        nav_fsm.stop()
        if tft:
            tft.close()
        path = att_mgr.export_excel()
        log.info("Final Excel exported → %s", path)
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    last_export = time.time()
    try:
        while True:
            time.sleep(2.0)
            if time.time() - last_export >= export_interval * 60:
                p = att_mgr.export_excel()
                log.info("📊 Auto-exported Excel snapshot → %s", p)
                last_export = time.time()
    except KeyboardInterrupt:
        shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions & Display Detection
# ─────────────────────────────────────────────────────────────────────────────
def _open_file(path: str):
    p = str(path)
    if platform.system() == "Darwin":
        subprocess.run(["open", p])
    elif platform.system() == "Windows":
        os.startfile(p)
    else:
        subprocess.run(["xdg-open", p])


def is_gui_available():
    """Detects whether graphical display server is accessible."""
    if platform.system() == "Linux" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    try:
        root = Tk()
        root.destroy()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Unified Master Entry Point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ROS Attendance Bot — Unified Master Runner")
    parser.add_argument("--headless", action="store_true", help="Force autonomous headless robot mode")
    parser.add_argument("--no-nav",   action="store_true", help="Disable /cmd_vel navigation state machine")
    parser.add_argument("--no-tft",   action="store_true", help="Disable TFT display output")
    parser.add_argument("--cam",      type=int, default=config.CAMERA_INDEX, help="Camera device index")
    parser.add_argument("--export-interval", type=int, default=10, help="Excel auto-export interval in minutes")
    args = parser.parse_args()

    config.CAMERA_INDEX = args.cam
    nav_enabled         = not args.no_nav
    tft_enabled         = not args.no_tft

    # Auto-detect whether to run GUI or Headless
    if args.headless or not is_gui_available():
        log.info("Display server not detected or --headless specified. Launching unified Headless Mode.")
        run_headless(nav_enabled=nav_enabled, tft_enabled=tft_enabled, export_interval=args.export_interval)
    else:
        log.info("Display server detected. Launching full unified GUI Application.")
        app = AttendanceApp(nav_enabled=nav_enabled, tft_enabled=tft_enabled)
        app.mainloop()


if __name__ == "__main__":
    main()
