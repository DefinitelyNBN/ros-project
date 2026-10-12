#!/usr/bin/env python3
"""
=============================================================================
 Manual Teleoperation — BTS7960 Keyboard Controller
 Control your robot manually from the terminal over SSH.
=============================================================================
Controls:
    W  /  ↑   : Forward
    S  /  ↓   : Backward
    A  /  ←   : Spin Left (Counter-Clockwise)
    D  /  →   : Spin Right (Clockwise)
    Q           : Rotate Left (Arc Turn)
    E           : Rotate Right (Arc Turn)
    SPACE       : Emergency Stop (Brake)
    +  /  =     : Increase Speed
    -           : Decrease Speed
    X           : Exit Teleop
=============================================================================
Usage:
    python3 teleop.py
    python3 teleop.py --speed 0.4       # Start at 40% speed
    python3 teleop.py --step 0.1        # Speed increment step
=============================================================================
"""

import sys
import time
import argparse
import logging
import tty
import termios
import threading

from motor_controller import MotorDriver

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [TELEOP] %(message)s")
log = logging.getLogger("teleop")

# ── Key Bindings ──────────────────────────────────────────────────────────────
KEY_FORWARD   = ['w', 'W', '\x1b[A']  # W or Up Arrow
KEY_BACKWARD  = ['s', 'S', '\x1b[B']  # S or Down Arrow
KEY_LEFT      = ['a', 'A', '\x1b[D']  # A or Left Arrow
KEY_RIGHT     = ['d', 'D', '\x1b[C']  # D or Right Arrow
KEY_ARC_LEFT  = ['q', 'Q']
KEY_ARC_RIGHT = ['e', 'E']
KEY_STOP      = [' ']                 # Spacebar
KEY_SPEED_UP  = ['+', '=']
KEY_SPEED_DN  = ['-', '_']
KEY_QUIT      = ['x', 'X', '\x03']   # X or Ctrl+C

SPEED_MIN  = 0.10
SPEED_MAX  = 1.00
SPEED_STEP = 0.05


def get_key():
    """Read a single keypress (blocking) with arrow key support."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                return '\x1b[' + ch3
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def print_dashboard(speed: float, state: str, left: float, right: float):
    """Renders a live terminal HUD."""
    bar_len = 20
    filled  = int(abs(speed) * bar_len)
    bar     = "█" * filled + "░" * (bar_len - filled)

    # ANSI colors
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    RESET  = "\033[0m"

    state_color = GREEN if "Forward" in state else (RED if "Brake" in state else YELLOW)

    print("\033[H\033[J", end="")  # Clear screen
    print(f"{"="*54}")
    print(f"   {'🤖  ROBOT MANUAL TELEOPERATION':^48}")
    print(f"{"="*54}")
    print(f"   Speed  : {CYAN}[{bar}]{RESET}  {speed*100:5.1f}%")
    print(f"   State  : {state_color}{state:<20}{RESET}")
    print(f"   Motors : Left {left:+.2f}  |  Right {right:+.2f}")
    print(f"{"─"*54}")
    print(f"   {CYAN}W / ↑{RESET} = Forward      {CYAN}S / ↓{RESET} = Backward")
    print(f"   {CYAN}A / ←{RESET} = Spin Left    {CYAN}D / →{RESET} = Spin Right")
    print(f"   {CYAN}Q{RESET}    = Arc Left      {CYAN}E{RESET}    = Arc Right")
    print(f"   {CYAN}SPACE{RESET} = BRAKE         {CYAN}+/-{RESET}  = Speed ± {SPEED_STEP*100:.0f}%")
    print(f"   {RED}X{RESET}    = Exit")
    print(f"{"="*54}")


def run_teleop(initial_speed: float = 0.35, speed_step: float = SPEED_STEP):
    driver = MotorDriver()
    speed  = initial_speed
    left   = 0.0
    right  = 0.0
    state  = "STOPPED"

    print_dashboard(speed, state, left, right)

    try:
        while True:
            key = get_key()

            if key in KEY_QUIT:
                driver.stop()
                print("\n\033[92m[✓] Teleop stopped. All motors halted.\033[0m\n")
                break

            elif key in KEY_FORWARD:
                left  = speed
                right = speed
                state = "▲ Forward"
                driver.set_motors(left, right)

            elif key in KEY_BACKWARD:
                left  = -speed
                right = -speed
                state = "▼ Backward"
                driver.set_motors(left, right)

            elif key in KEY_LEFT:
                # Spin counter-clockwise in place
                left  = -speed
                right = speed
                state = "◄ Spin Left"
                driver.set_motors(left, right)

            elif key in KEY_RIGHT:
                # Spin clockwise in place
                left  = speed
                right = -speed
                state = "► Spin Right"
                driver.set_motors(left, right)

            elif key in KEY_ARC_LEFT:
                # Arc turn (gentle left curve while moving forward)
                left  = speed * 0.4
                right = speed
                state = "↰ Arc Left"
                driver.set_motors(left, right)

            elif key in KEY_ARC_RIGHT:
                # Arc turn (gentle right curve while moving forward)
                left  = speed
                right = speed * 0.4
                state = "↱ Arc Right"
                driver.set_motors(left, right)

            elif key in KEY_STOP:
                left  = 0.0
                right = 0.0
                state = "■ BRAKE"
                driver.stop()

            elif key in KEY_SPEED_UP:
                speed = min(SPEED_MAX, round(speed + speed_step, 2))
                state = f"⬆ Speed: {speed*100:.0f}%"

            elif key in KEY_SPEED_DN:
                speed = max(SPEED_MIN, round(speed - speed_step, 2))
                state = f"⬇ Speed: {speed*100:.0f}%"

            print_dashboard(speed, state, left, right)

    except KeyboardInterrupt:
        pass
    finally:
        driver.stop()
        driver.cleanup()
        print("\033[?25h", end="")  # Restore cursor


def main():
    parser = argparse.ArgumentParser(description="Manual Keyboard Teleop")
    parser.add_argument("--speed", type=float, default=0.35,
                        help="Initial motor speed 0.0 to 1.0 (default: 0.35 = 35%%)")
    parser.add_argument("--step",  type=float, default=SPEED_STEP,
                        help="Speed increment per keypress (default: 0.05 = 5%%)")
    args = parser.parse_args()

    print("\033[?25l", end="")  # Hide cursor for clean UI
    run_teleop(initial_speed=args.speed, speed_step=args.step)


if __name__ == "__main__":
    main()
