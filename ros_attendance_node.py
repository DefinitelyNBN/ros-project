#!/usr/bin/env python3
"""
=============================================================================
 ROS Attendance Bot — ROS 2 Humble Navigation & Attendance Node
 Autonomous Movement & Attendance Tracking Node for Mobile Robots.
=============================================================================
ROS 2 Publishers:
    /cmd_vel                 (geometry_msgs/msg/Twist) — Robot movement velocity
    /attendance/student_id   (std_msgs/msg/String)     — Identified student ID
    /attendance/student_name (std_msgs/msg/String)     — Identified student Name
    /attendance/total_count  (std_msgs/msg/Int32)      — Current session attendance total
    /attendance/state        (std_msgs/msg/String)     — Navigation FSM state
    /attendance/unknown_alert(std_msgs/msg/String)     — Unrecognized face alert

Finite State Machine (FSM):
    'SEARCHING' : Publishes angular.z = 0.3 (spins in place to scan surroundings)
    'LOCKED'    : Publishes linear.x = 0.0, angular.z = 0.0 (stops robot)
                  Holds position for 5 seconds during attendance logging,
                  then automatically resumes 'SEARCHING'.
=============================================================================
"""

import sys
import time
import logging
import threading
from datetime import datetime
from pathlib import Path

import config
from attendance import AttendanceManager
from recognition_engine import RecognitionEngine
from tft_display import TFTDisplay

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ROS2_ATTENDANCE] %(message)s")
log = logging.getLogger("ros2_attendance")

# ── ROS 2 Humble Import & Fallback Emulation ──────────────────────────────────
try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from std_msgs.msg import String, Int32
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    log.warning("rclpy not found. Running with ROS 2 Humble emulation interface.")

    # Lightweight emulation classes for testing outside ROS 2 environment
    class Twist:
        class Vector3:
            def __init__(self):
                self.x = 0.0
                self.y = 0.0
                self.z = 0.0
        def __init__(self):
            self.linear = Twist.Vector3()
            self.angular = Twist.Vector3()

    class String:
        def __init__(self, data=""):
            self.data = data

    class Int32:
        def __init__(self, data=0):
            self.data = data

    class Node:
        def __init__(self, node_name):
            self._node_name = node_name
        def create_publisher(self, msg_type, topic, qos):
            class MockPublisher:
                def __init__(self, topic):
                    self.topic = topic
                def publish(self, msg):
                    pass
            return MockPublisher(topic)
        def create_timer(self, interval, callback):
            class MockTimer:
                def __init__(self, interval, cb):
                    self._interval = interval
                    self._cb = cb
                    self._running = True
                    self._t = threading.Thread(target=self._run, daemon=True)
                    self._t.start()
                def _run(self):
                    while self._running:
                        time.sleep(self._interval)
                        try:
                            self._cb()
                        except Exception:
                            pass
                def cancel(self):
                    self._running = False
            return MockTimer(interval, callback)
        def get_logger(self):
            class MockLogger:
                def info(self, msg): log.info(msg)
                def warn(self, msg): log.warning(msg)
                def error(self, msg): log.error(msg)
            return MockLogger()


# ── ROS 2 Attendance & Navigation Node ───────────────────────────────────────

class AttendanceNavigationNode(Node):
    """
    ROS 2 Humble Node implementing autonomous search and attendance locking FSM.
    """

    STATE_SEARCHING = "SEARCHING"
    STATE_LOCKED    = "LOCKED"
    LOCKED_COOLDOWN = 5.0  # seconds to hold position after face recognition

    def __init__(self):
        super().__init__("attendance_navigation_node")

        # ── 1. ROS 2 Publishers ──────────────────────────────────────────────
        self.cmd_vel_pub     = self.create_publisher(Twist, "/cmd_vel", 10)
        self.pub_student_id  = self.create_publisher(String, "/attendance/student_id", 10)
        self.pub_student_name= self.create_publisher(String, "/attendance/student_name", 10)
        self.pub_total_count = self.create_publisher(Int32, "/attendance/total_count", 10)
        self.pub_state       = self.create_publisher(String, "/attendance/state", 10)
        self.pub_unknown     = self.create_publisher(String, "/attendance/unknown_alert", 10)

        # ── 2. FSM State Management ──────────────────────────────────────────
        self._state_lock        = threading.Lock()
        self._state             = self.STATE_SEARCHING
        self._locked_timestamp  = 0.0

        # ── 3. Core Subsystems ───────────────────────────────────────────────
        self.att_mgr = AttendanceManager()
        from audio_announcer import AudioAnnouncer
        self.audio   = AudioAnnouncer(enabled=True)
        self.tft     = None
        if config.TFT_ENABLED:
            try:
                self.tft = TFTDisplay()
                self.tft.show_idle(total_count=self.att_mgr.get_count())
            except Exception as e:
                self.get_logger().warn(f"TFT Display init failed: {e}")

        # ── 4. Wire Recognition Engine Callbacks ─────────────────────────────
        self.engine = RecognitionEngine(
            attendance_manager=self.att_mgr,
            on_face_detected=self.on_face_detected,
            on_unknown_detected=self.on_unknown_detected,
            on_frame=self.on_frame,
            on_status=self.on_status,
        )
        self.engine.start()

        # ── 5. Control Loop Timer (10 Hz = 0.1s) ─────────────────────────────
        self.control_timer = self.create_timer(0.1, self.control_loop)
        self.get_logger().info("🤖 Autonomous Navigation Node online. State -> SEARCHING")

    # ── FSM Control Loop (10 Hz) ─────────────────────────────────────────────

    def control_loop(self):
        """
        Executes the autonomous navigation state machine:
          - SEARCHING : Spin in place (angular.z = 0.3) to scan environment.
          - LOCKED    : Stop robot (linear.x = 0, angular.z = 0) and wait 5s.
        """
        with self._state_lock:
            now = time.time()

            # State Transition Check: LOCKED -> SEARCHING
            if self._state == self.STATE_LOCKED:
                elapsed = now - self._locked_timestamp
                if elapsed >= self.LOCKED_COOLDOWN:
                    self._state = self.STATE_SEARCHING
                    self.get_logger().info("🔄 5-second cooldown elapsed. State -> SEARCHING (Resuming scan).")
                    self._publish_state_str(self.STATE_SEARCHING)
                else:
                    # Enforce stopped position while locked
                    self._publish_stop()
                    return

            # State Action: SEARCHING
            if self._state == self.STATE_SEARCHING:
                self._publish_search_spin()

    # ── State Machine Transitions ────────────────────────────────────────────

    def on_frame(self, frame):
        """Streams live video frame to TFT display."""
        if self.tft:
            self.tft.show_live_frame(frame)

    def on_face_detected(self, name: str, sid: str, frame, boxes):
        """
        Triggered when a familiar authorized person is confirmed.
        Welcomes them by calling their name, pauses robot, and logs access.
        """
        with self._state_lock:
            self._state = self.STATE_LOCKED
            self._locked_timestamp = time.time()
            self._publish_stop()
            self.get_logger().info(f"✅ State -> AUTHORIZED: Welcoming '{name}' ({sid}). Stopping robot.")
            self._publish_state_str("AUTHORIZED")

        # Voice welcome calling name
        self.audio.announce_recognised(name)

        # Update TFT display
        if self.tft:
            self.tft.show_success(name, sid)

        # Broadcast ROS 2 topics
        msg_sid = String()
        msg_sid.data = sid
        self.pub_student_id.publish(msg_sid)

        msg_name = String()
        msg_name.data = name
        self.pub_student_name.publish(msg_name)

        msg_count = Int32()
        msg_count.data = self.att_mgr.get_count()
        self.pub_total_count.publish(msg_count)

    def on_unknown_detected(self, frame, boxes):
        """Triggered when an unfamiliar person is observed in perimeter."""
        self.get_logger().warn("🚨 INTRUDER ALERT! Unfamiliar person detected!")
        # Sound alarm siren & verbal warning alert
        self.audio.announce_unknown()

        if self.tft:
            self.tft.show_unknown()

        # Capture intruder photo snapshot
        self.att_mgr.log_intruder(frame)

        msg = String()
        msg.data = "INTRUDER_ALERT"
        self.pub_unknown.publish(msg)

    def on_status(self, msg: str):
        if self.tft:
            self.tft.update_status(msg)

    # ── Velocity Helper Functions ────────────────────────────────────────────

    def _publish_search_spin(self):
        """Publishes rotational velocity to scan environment (angular.z = 0.3)."""
        twist = Twist()
        twist.linear.x  = 0.0
        twist.linear.y  = 0.0
        twist.linear.z  = 0.0
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = 0.3
        self.cmd_vel_pub.publish(twist)

    def _publish_stop(self):
        """Halts all robot movement (linear.x = 0.0, angular.z = 0.0)."""
        twist = Twist()
        twist.linear.x  = 0.0
        twist.linear.y  = 0.0
        twist.linear.z  = 0.0
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = 0.0
        self.cmd_vel_pub.publish(twist)

    def _publish_state_str(self, state_str: str):
        msg = String()
        msg.data = state_str
        self.pub_state.publish(msg)

    def shutdown(self):
        """Clean shutdown of hardware and engine."""
        self._publish_stop()
        self.engine.stop()
        if self.tft:
            self.tft.close()
        final_excel = self.att_mgr.export_excel()
        self.get_logger().info(f"📊 Final attendance Excel report saved -> {final_excel}")


# ── Main Entry Point ─────────────────────────────────────────────────────────

def main(args=None):
    if ROS2_AVAILABLE:
        rclpy.init(args=args)

    node = AttendanceNavigationNode()

    try:
        if ROS2_AVAILABLE:
            rclpy.spin(node)
        else:
            # Standalone loop when running outside ROS 2 environment
            log.info("Running standalone control loop (Ctrl+C to stop)...")
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()
        if ROS2_AVAILABLE:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
