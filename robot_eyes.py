"""
=============================================================================
 ROS Attendance Bot — Dual OLED Robot Eyes
 Animated eyes using two 128x64 SSD1306 OLED displays.
 Left Eye on I2C-1 (GPIO 2/3), Right Eye on I2C-3 (GPIO 23/24).
 
 Animations supported:
   - Blink
   - Look Left / Right / Center / Up / Down
   - Happy / Squint (attendance marked!)
   - Suspicious / Angry (unrecognized face)
   - Scan / Wonder (robot moving)
=============================================================================
"""

import time
import math
from PIL import Image, ImageDraw

try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    LUMA_AVAILABLE = True
except ImportError:
    LUMA_AVAILABLE = False


class RobotEyes:
    WIDTH = 128
    HEIGHT = 64

    def __init__(self, left_bus=1, right_bus=3, addr=0x3C, single_bus_mode=False, right_addr=0x3D):
        """
        :param left_bus: I2C bus for Left Eye (default 1)
        :param right_bus: I2C bus for Right Eye (default 3)
        :param single_bus_mode: True if both screens are on the same I2C bus with distinct addresses (0x3C & 0x3D)
        """
        if not LUMA_AVAILABLE:
            raise RuntimeError("luma.oled is required! Install via: pip3 install luma.oled")

        # Initialize Left Eye
        serial_left = i2c(port=left_bus, address=addr)
        self.device_left = ssd1306(serial_left, width=self.WIDTH, height=self.HEIGHT)

        # Initialize Right Eye
        if single_bus_mode:
            serial_right = i2c(port=left_bus, address=right_addr)
        else:
            serial_right = i2c(port=right_bus, address=addr)
        self.device_right = ssd1306(serial_right, width=self.WIDTH, height=self.HEIGHT)

        # Eye geometric defaults
        self.center_x = self.WIDTH // 2
        self.center_y = self.HEIGHT // 2
        self.pupil_radius = 24
        self.pupil_inner = 14

    def _draw_eye(self, offset_x=0, offset_y=0, eyelid_ratio=1.0, is_happy=False, is_angry=False, is_left_eye=True):
        """Generates a PIL image for a single eye with dynamic shape and eyelids."""
        img = Image.new("1", (self.WIDTH, self.HEIGHT), 0)
        draw = ImageDraw.Draw(img)

        # Eye socket dimensions
        cx = self.center_x + offset_x
        cy = self.center_y + offset_y
        r = self.pupil_radius

        if eyelid_ratio <= 0.05:
            # Completely closed (blinking slit)
            draw.line([(cx - r, cy), (cx + r, cy)], fill=1, width=3)
            return img

        if is_happy:
            # Inverted arc / happy eye (^ shape)
            bbox = [cx - r, cy - r, cx + r, cy + r]
            draw.chord(bbox, start=180, end=360, fill=1)
            # Inner cutout for expression
            draw.chord([cx - r + 5, cy - r + 5, cx + r - 5, cy + r], start=180, end=360, fill=0)
            return img

        # Normal rounded eye
        current_ry = int(r * eyelid_ratio)
        bbox = [cx - r, cy - current_ry, cx + r, cy + current_ry]
        draw.rounded_rectangle(bbox, radius=12, fill=1)

        # Pupil inner cutout (gives expressive cartoon look)
        ir = int(self.pupil_inner * eyelid_ratio)
        if ir > 2:
            inner_cx = cx + (offset_x // 2)
            inner_cy = cy + (offset_y // 2)
            draw.rounded_rectangle([inner_cx - ir, inner_cy - ir, inner_cx + ir, inner_cy + ir], radius=6, fill=0)

        # Angry slanted eyelids
        if is_angry:
            if is_left_eye:
                draw.polygon([(0, 0), (self.WIDTH, 0), (self.WIDTH, 18), (0, 36)], fill=0)
            else:
                draw.polygon([(0, 0), (self.WIDTH, 0), (self.WIDTH, 36), (0, 18)], fill=0)

        return img

    def display(self, left_img, right_img):
        """Send images to both displays."""
        self.device_left.display(left_img)
        self.device_right.display(right_img)

    def look(self, offset_x=0, offset_y=0, eyelid_ratio=1.0, is_happy=False, is_angry=False):
        """Set eye direction and emotion."""
        l_img = self._draw_eye(offset_x, offset_y, eyelid_ratio, is_happy, is_angry, is_left_eye=True)
        r_img = self._draw_eye(offset_x, offset_y, eyelid_ratio, is_happy, is_angry, is_left_eye=False)
        self.display(l_img, r_img)

    def blink(self, speed=0.03):
        """Natural blink animation."""
        for ratio in [0.7, 0.4, 0.1, 0.0, 0.4, 0.8, 1.0]:
            self.look(0, 0, eyelid_ratio=ratio)
            time.sleep(speed)

    def look_around(self):
        """Looking sequence: center -> left -> right -> center."""
        self.look(0, 0)
        time.sleep(0.8)
        self.look(-18, 0) # Look left
        time.sleep(0.6)
        self.look(18, 0)  # Look right
        time.sleep(0.6)
        self.look(0, 0)   # Center
        time.sleep(0.4)

    def celebrate_recognized(self):
        """Happy eye animation when face attendance is marked."""
        for _ in range(3):
            self.look(0, -6, is_happy=True)
            time.sleep(0.35)
            self.look(0, 0, is_happy=False)
            time.sleep(0.2)

    def alert_unknown(self):
        """Angry/suspicious expression when unauthorized face detected."""
        self.look(0, 4, is_angry=True)
        time.sleep(1.2)
        self.blink()
        self.look(0, 0)


if __name__ == "__main__":
    print("Testing Dual OLED Robot Eyes...")
    try:
        eyes = RobotEyes(left_bus=1, right_bus=3)
        print("Connected to OLED Eyes! Running animation loop...")

        while True:
            # Idle animation loop
            eyes.look(0, 0)
            time.sleep(1.5)
            eyes.blink()
            time.sleep(0.8)

            print("Animation: Looking around...")
            eyes.look_around()

            print("Animation: Happy (Welcome / Marked)...")
            eyes.celebrate_recognized()
            time.sleep(1.0)

            print("Animation: Alert (Unknown person)...")
            eyes.alert_unknown()
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nStopping Robot Eyes.")
    except Exception as e:
        print(f"Error initializing OLED eyes: {e}")
        print("\nIf you are using a single I2C bus or mirrored display, test with:")
        print("RobotEyes(left_bus=1, single_bus_mode=True, right_addr=0x3D)")
