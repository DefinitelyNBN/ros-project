#!/usr/bin/env python3
"""
=============================================================================
 BTS7960 High-Current (43A) Dual H-Bridge Motor Driver
 Specifically designed for BTS7960 modules on Raspberry Pi 4B.
=============================================================================
BTS7960 Module Pinout:
  - VCC   : Connect to Pi 5V (Pin 2 or 4)
  - GND   : Connect to Pi GND (Pin 6, 14, 20, 30, or 34)
  - R_EN  : Forward Enable (tied HIGH to 5V or Pi GPIO)
  - L_EN  : Reverse Enable (tied HIGH to 5V or Pi GPIO)
  - RPWM  : Forward PWM speed signal
  - LPWM  : Reverse PWM speed signal

Two BTS7960 Drivers are typically used for differential drive (Left & Right):
  [LEFT MOTOR BTS7960]
    RPWM = GPIO 12 (Pin 32 - Hardware PWM0)
    LPWM = GPIO 13 (Pin 33 - Hardware PWM1)
    R_EN + L_EN = GPIO 5 (Pin 29) or tied to 5V logic

  [RIGHT MOTOR BTS7960]
    RPWM = GPIO 18 (Pin 12 - Hardware PWM0)
    LPWM = GPIO 19 (Pin 35 - Hardware PWM1)
    R_EN + L_EN = GPIO 6 (Pin 31) or tied to 5V logic
=============================================================================
"""

import sys
import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BTS7960] %(message)s")
log = logging.getLogger("bts7960")

# ── GPIO Pin Mapping for Two BTS7960 Drivers ──────────────────────────────────
# Option 2 (Recommended): R_EN and L_EN tied to 5V (VCC) directly on driver board.
# Only 2 PWM signals needed per motor from the Pi!

# Left Motor BTS7960:
PIN_LEFT_RPWM = 12  # Physical Pin 32 (PWM)
PIN_LEFT_LPWM = 13  # Physical Pin 33 (PWM)
PIN_LEFT_EN   = None # Tied to 5V on board

# Right Motor BTS7960:
PIN_RIGHT_RPWM = 18 # Physical Pin 12 (PWM)
PIN_RIGHT_LPWM = 19 # Physical Pin 35 (PWM)
PIN_RIGHT_EN   = None # Tied to 5V on board

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    log.warning("RPi.GPIO not available. Running in BTS7960 simulation mode.")


class BTS7960Motor:
    """Controls a single BTS7960 H-Bridge driver channel."""
    def __init__(self, rpwm_pin: int, lpwm_pin: int, en_pin: int = None, freq: int = 1000):
        self.rpwm_pin = rpwm_pin
        self.lpwm_pin = lpwm_pin
        self.en_pin   = en_pin
        self.freq     = freq
        self._pwm_r   = None
        self._pwm_l   = None
        self._active  = False

        if GPIO_AVAILABLE:
            try:
                GPIO.setup(self.rpwm_pin, GPIO.OUT)
                GPIO.setup(self.lpwm_pin, GPIO.OUT)
                GPIO.output(self.rpwm_pin, GPIO.LOW)
                GPIO.output(self.lpwm_pin, GPIO.LOW)

                if self.en_pin is not None:
                    GPIO.setup(self.en_pin, GPIO.OUT)
                    GPIO.output(self.en_pin, GPIO.HIGH) # Enable chip

                self._pwm_r = GPIO.PWM(self.rpwm_pin, self.freq)
                self._pwm_l = GPIO.PWM(self.lpwm_pin, self.freq)
                self._pwm_r.start(0)
                self._pwm_l.start(0)
                self._active = True
            except Exception as e:
                log.error("Failed to initialize BTS7960 channel: %s", e)

    def set_speed(self, speed: float):
        """
        speed from -1.0 (Full Reverse) to +1.0 (Full Forward).
        0.0 = Stop (Brake).
        """
        speed = max(-1.0, min(1.0, speed))
        duty  = abs(speed) * 100.0

        if not self._active:
            return

        if speed > 0:
            # Forward: RPWM active, LPWM 0%
            self._pwm_l.ChangeDutyCycle(0)
            self._pwm_r.ChangeDutyCycle(duty)
        elif speed < 0:
            # Reverse: LPWM active, RPWM 0%
            self._pwm_r.ChangeDutyCycle(0)
            self._pwm_l.ChangeDutyCycle(duty)
        else:
            # Brake / Coast
            self._pwm_r.ChangeDutyCycle(0)
            self._pwm_l.ChangeDutyCycle(0)

    def stop(self):
        self.set_speed(0.0)

    def cleanup(self):
        self.stop()
        if self._active:
            try:
                self._pwm_r.stop()
                self._pwm_l.stop()
            except Exception:
                pass


class MotorDriver:
    """
    Unified Differential-Drive Motor Controller for two BTS7960 Drivers.
    Translates ROS 2 /cmd_vel into left and right wheel velocities.
    """

    def __init__(self,
                 l_rpwm=PIN_LEFT_RPWM, l_lpwm=PIN_LEFT_LPWM, l_en=PIN_LEFT_EN,
                 r_rpwm=PIN_RIGHT_RPWM, r_lpwm=PIN_RIGHT_LPWM, r_en=PIN_RIGHT_EN):

        if GPIO_AVAILABLE:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)

        self.left_motor  = BTS7960Motor(l_rpwm, l_lpwm, l_en)
        self.right_motor = BTS7960Motor(r_rpwm, r_lpwm, r_en)
        log.info("BTS7960 Dual Driver System Initialized on Raspberry Pi GPIO.")

    def set_motors(self, left_speed: float, right_speed: float):
        """Sets individual wheel speeds (-1.0 to 1.0)."""
        self.left_motor.set_speed(left_speed)
        self.right_motor.set_speed(right_speed)

    def set_twist(self, linear_x: float, angular_z: float):
        """Standard differential drive mixer for /cmd_vel."""
        left  = linear_x - angular_z * 0.5
        right = linear_x + angular_z * 0.5
        self.set_motors(left, right)

    def spin_search(self, speed=0.30):
        """Rotates the robot clockwise in place to scan for faces."""
        # Left forward, Right reverse
        self.set_motors(speed, -speed)

    def stop(self):
        """Instantly halts all motors."""
        self.set_motors(0.0, 0.0)

    def cleanup(self):
        self.stop()
        try:
            self.left_motor.cleanup()
            self.right_motor.cleanup()
        except Exception:
            pass
        if GPIO_AVAILABLE:
            try:
                # Small pause to allow lgpio thread to finish pending cycles
                time.sleep(0.05)
                GPIO.cleanup()
            except Exception:
                pass


def test_bts_motors():
    print("=" * 60)
    print("  BTS7960 43A MOTOR DRIVER TEST UTILITY")
    print("  Ensure robot wheels are elevated or free to turn!")
    print("=" * 60)

    driver = MotorDriver()

    try:
        print("\n[1/4] Testing Face Search Rotation (Clockwise) @ 30% for 3 seconds...")
        driver.spin_search(speed=0.30)
        time.sleep(3)

        print("\n[2/4] Testing Stop (Brake) for 2 seconds...")
        driver.stop()
        time.sleep(2)

        print("\n[3/4] Testing Forward Drive @ 30% for 2 seconds...")
        driver.set_motors(0.30, 0.30)
        time.sleep(2)

        print("\n[4/4] Testing Reverse Drive @ 30% for 2 seconds...")
        driver.set_motors(-0.30, -0.30)
        time.sleep(2)

        print("\n[✓] BTS7960 Motor Hardware Test Completed Successfully!")

    finally:
        driver.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTS7960 Motor Driver")
    parser.add_argument("--test", action="store_true", help="Run 10-second BTS7960 test")
    args = parser.parse_args()
    test_bts_motors()
