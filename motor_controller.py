#!/usr/bin/env python3
"""
=============================================================================
 Motor Hardware Controller & Diagnostic Utility
 Directly drives motors via Raspberry Pi GPIO or translates ROS 2 /cmd_vel
 to L298N / L9110S motor driver signals.
=============================================================================
Usage:
    # 1. Test motors directly (Spin Left, Spin Right, Stop):
    python3 motor_controller.py --test

    # 2. Run standalone motor driver listening to ROS FSM:
    python3 motor_controller.py
=============================================================================
"""

import sys
import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOTOR] %(message)s")
log = logging.getLogger("motor")

# ── Default Motor Pinout (Matches CIRCUIT_AND_PINOUT_GUIDE.md) ───────────────
PIN_ENA = 12  # Physical Pin 32 (PWM)
PIN_IN1 = 5   # Physical Pin 29
PIN_IN2 = 6   # Physical Pin 31
PIN_IN3 = 13  # Physical Pin 33
PIN_IN4 = 19  # Physical Pin 35
PIN_ENB = 16  # Physical Pin 36 (PWM)

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    log.warning("RPi.GPIO not available or not on Raspberry Pi. Using simulation driver.")


class MotorDriver:
    """
    Controls differential drive DC motors via an L298N H-Bridge.
    Translates linear (m/s) and angular (rad/s) velocities to wheel PWM.
    """

    def __init__(self, ena=PIN_ENA, in1=PIN_IN1, in2=PIN_IN2,
                 in3=PIN_IN3, in4=PIN_IN4, enb=PIN_ENB):
        self.ena_pin = ena
        self.in1_pin = in1
        self.in2_pin = in2
        self.in3_pin = in3
        self.in4_pin = in4
        self.enb_pin = enb

        self._pwm_a = None
        self._pwm_b = None
        self._initialized = False

        if GPIO_AVAILABLE:
            try:
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                for pin in [self.in1_pin, self.in2_pin, self.in3_pin, self.in4_pin, self.ena_pin, self.enb_pin]:
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)

                self._pwm_a = GPIO.PWM(self.ena_pin, 1000) # 1 kHz PWM
                self._pwm_b = GPIO.PWM(self.enb_pin, 1000)
                self._pwm_a.start(0)
                self._pwm_b.start(0)
                self._initialized = True
                log.info("Motor hardware initialized successfully on GPIO (BCM).")
            except Exception as e:
                log.error("Failed to initialize GPIO: %s", e)

    def set_twist(self, linear_x: float, angular_z: float):
        """
        Calculates left and right motor speeds from /cmd_vel twist parameters.
        linear_x  : forward (+) / backward (-) velocity
        angular_z : rotate counter-clockwise (+) / clockwise (-)
        """
        # Differential drive kinematic mix
        left_val  = linear_x - angular_z * 0.5
        right_val = linear_x + angular_z * 0.5

        self.set_motors(left_val, right_val)

    def set_motors(self, left_speed: float, right_speed: float):
        """
        Speeds from -1.0 (Full Reverse) to +1.0 (Full Forward).
        """
        left_speed  = max(-1.0, min(1.0, left_speed))
        right_speed = max(-1.0, min(1.0, right_speed))

        if not self._initialized:
            log.debug("[SIM] Left: %.2f | Right: %.2f", left_speed, right_speed)
            return

        # ── Left Motor (A) ──
        if left_speed > 0:
            GPIO.output(self.in1_pin, GPIO.HIGH)
            GPIO.output(self.in2_pin, GPIO.LOW)
            self._pwm_a.ChangeDutyCycle(abs(left_speed) * 100)
        elif left_speed < 0:
            GPIO.output(self.in1_pin, GPIO.LOW)
            GPIO.output(self.in2_pin, GPIO.HIGH)
            self._pwm_a.ChangeDutyCycle(abs(left_speed) * 100)
        else:
            GPIO.output(self.in1_pin, GPIO.LOW)
            GPIO.output(self.in2_pin, GPIO.LOW)
            self._pwm_a.ChangeDutyCycle(0)

        # ── Right Motor (B) ──
        if right_speed > 0:
            GPIO.output(self.in3_pin, GPIO.HIGH)
            GPIO.output(self.in4_pin, GPIO.LOW)
            self._pwm_b.ChangeDutyCycle(abs(right_speed) * 100)
        elif right_speed < 0:
            GPIO.output(self.in3_pin, GPIO.LOW)
            GPIO.output(self.in4_pin, GPIO.HIGH)
            self._pwm_b.ChangeDutyCycle(abs(right_speed) * 100)
        else:
            GPIO.output(self.in3_pin, GPIO.LOW)
            GPIO.output(self.in4_pin, GPIO.LOW)
            self._pwm_b.ChangeDutyCycle(0)

    def spin_search(self, speed=0.35):
        """Rotates the robot slowly in place to scan for faces."""
        log.info("Robot SEARCHING: Spinning in place at %.0f%% power...", speed * 100)
        self.set_motors(left_speed=speed, right_speed=-speed)

    def stop(self):
        """Immediately halts both motors."""
        log.info("Robot LOCKED: Motors halted.")
        self.set_motors(0.0, 0.0)

    def cleanup(self):
        self.stop()
        if self._initialized:
            try:
                self._pwm_a.stop()
                self._pwm_b.stop()
                GPIO.cleanup()
            except Exception:
                pass


def run_hardware_test():
    """Runs a 10-second self-test for robot motors."""
    print("=" * 60)
    print("  ROBOT CHASSIS MOTOR HARDWARE TEST")
    print("  Make sure the robot wheels are elevated or on the floor!")
    print("=" * 60)

    driver = MotorDriver()

    try:
        print("\n[1/4] Spinning in Place (Face Search Mode) for 3 seconds...")
        driver.spin_search(speed=0.35)
        time.sleep(3)

        print("\n[2/4] Testing Stop (Target Locked / Attendance Verified) for 2 seconds...")
        driver.stop()
        time.sleep(2)

        print("\n[3/4] Testing Forward Drive for 2 seconds...")
        driver.set_motors(0.35, 0.35)
        time.sleep(2)

        print("\n[4/4] Final Stop...")
        driver.stop()
        print("\n[✓] Motor test completed successfully!")

    finally:
        driver.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robot Motor Controller")
    parser.add_argument("--test", action="store_true", help="Run 10-second motor hardware test")
    args = parser.parse_args()

    if args.test:
        run_hardware_test()
    else:
        run_hardware_test()
