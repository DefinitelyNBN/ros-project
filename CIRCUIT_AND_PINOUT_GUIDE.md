# ⚡ ROS Attendance Robot — Circuit & Pinout Architecture Guide

> A comprehensive hardware schematic, wiring diagram, and pin-by-pin interconnection manual for integrating the **Raspberry Pi 4B**, **SPI TFT Display**, **External Camera**, **Motor Controller**, and **Power Distribution**.

---

## 📑 Table of Contents
1. [Master System Schematic Diagram](#1-master-system-schematic-diagram)
2. [Complete 40-Pin GPIO Header Reference Map](#2-complete-40-pin-gpio-header-reference-map)
3. [Circuit 1: Power Distribution & Star Grounding](#3-circuit-1-power-distribution--star-grounding)
4. [Circuit 2: SPI TFT Display (Pin-by-Pin Wiring)](#4-circuit-2-spi-tft-display-pin-by-pin-wiring)
5. [Circuit 3: Motor Driver & Navigation Control (/cmd_vel)](#5-circuit-3-motor-driver--navigation-control-cmd_vel)
6. [Circuit 4: External USB Camera & Optional Audio Buzzer](#6-circuit-4-external-usb-camera--optional-audio-buzzer)
7. [Recommended Wire Gauges & Color Coding](#7-recommended-wire-gauges--color-coding)
8. [Pre-Power-On Multimeter Safety Checklist](#8-pre-power-on-multimeter-safety-checklist)

---

## 1. Master System Schematic Diagram

```
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                         MAIN ROBOT BATTERY PACK                             │
 │                         (7.4V - 12.6V LiPo / Li-Ion)                        │
 └──────────────┬───────────────────────────────────────────────┬──────────────┘
                │ (+) Positive [Red 18 AWG]                     │ (-) Negative [Black 18 AWG]
                │                                               │
 ┌──────────────▼──────────────────────────────┐                │
 │       POWER SWITCH (SPST 10A Heavy Duty)    │                │
 └──────────────┬──────────────────────────────┘                │
                │                                               │
        ┌───────┴────────────────────────┐                      │
        │                                │                      │
 ┌──────▼─────────────────────┐   ┌──────▼──────────────────┐   │
 │   DC-DC BUCK CONVERTER     │   │   MOTOR DRIVER (L298N)  │   │
 │   (LM2596 / XL4015)        │   │   High Current Stage    │   │
 │   IN: 7.4V - 12V           │   │   12V Motor Input (VMS) │   │
 │   OUT: 5.1V @ 3.5A Max     │   └──────┬────────────┬─────┘   │
 └──────┬──────────────┬──────┘          │            │         │
        │ (+) 5.1V     │ (-) GND         │ OUT1/OUT2  │ OUT3/4  │
        │              │                 ▼            ▼         │
        │              │             [MOTOR A]    [MOTOR B]     │
        │              │             Left Wheel   Right Wheel   │
        │              │                                        │
        │              └─────────────────┬──────────────────────┘
        │                                │
        │               COMMON GROUND BUS BAR (STAR GND)
        │                                │
 ┌──────▼────────────────────────────────▼─────────────────────────────────────┐
 │                           RASPBERRY PI 4B                                   │
 │   [USB-C Power Port] ◄── 5.1V / 3.5A (From Buck Converter)                  │
 │                                                                             │
 │   [USB 2.0 Port]     ◄── External Webcam (1080p/720p MJPG)                  │
 │                                                                             │
 │   [40-PIN GPIO HEADER]                                                      │
 │      ├── SPI Bus (Pins 19, 23, 24, 22, 18, 12, 1, 6) ──► SPI TFT Screen     │
 │      │                                                   (Checkmark/Red X)  │
 │      └── Motor PWM/DIR (Pins 29, 31, 33, 35, 37, 32) ──► Motor Driver Logic │
 │                                                          (cmd_vel control)  │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete 40-Pin GPIO Header Reference Map

This chart shows **every single pin** on the Raspberry Pi 4B header, its default hardware function, and its exact assignment in this robot project:

```
                              RASPBERRY PI 4B
                             40-PIN GPIO HEADER
                        (Pin 1 is nearest MicroSD slot)

               [Physical Pin]                       [Physical Pin]
                                 ┌─────┬─────┐
        TFT VCC (3.3V Power)  -- │ 01  │  02 │ -- 5V Power (Cooling Fan +)
              I2C SDA (GPIO 2) -- │ 03  │  04 │ -- 5V Power (Auxiliary)
              I2C SCL (GPIO 3) -- │ 05  │  06 │ -- GND (TFT GND) [Common]
             System (GPIO 4)   -- │ 07  │  08 │ -- UART TX (GPIO 14)
                GND [Common]   -- │ 09  │  10 │ -- UART RX (GPIO 15)
              System (GPIO 17) -- │ 11  │  12 │ -- TFT Backlight BL (GPIO 18 / PWM0)
              System (GPIO 27) -- │ 13  │  14 │ -- GND (Cooling Fan -)
              System (GPIO 22) -- │ 15  │  16 │ -- Optional Buzzer (GPIO 23)
        3.3V Power (Auxiliary) -- │ 17  │  18 │ -- TFT Reset RST (GPIO 24)
           TFT MOSI (GPIO 10)  -- │ 19  │  20 │ -- GND [Common]
           TFT MISO (GPIO 9)   -- │ 21  │  22 │ -- TFT Data/Command DC (GPIO 25)
           TFT SCLK (GPIO 11)  -- │ 23  │  24 │ -- TFT Chip Select CE0 (GPIO 8)
                GND [Common]   -- │ 25  │  26 │ -- SPI CE1 (GPIO 7)
               ID EEPROM (SD)  -- │ 27  │  28 │ -- ID EEPROM (SC)
          MOTOR IN1 (GPIO 5)   -- │ 29  │  30 │ -- GND [Common]
          MOTOR IN2 (GPIO 6)   -- │ 31  │  32 │ -- MOTOR ENA / PWM (GPIO 12)
          MOTOR IN3 (GPIO 13)  -- │ 33  │  34 │ -- GND (Motor Driver GND) [Common]
          MOTOR IN4 (GPIO 19)  -- │ 35  │  36 │ -- MOTOR ENB / PWM (GPIO 16)
          System (GPIO 26)     -- │ 37  │  38 │ -- System (GPIO 20)
                GND [Common]   -- │ 39  │  40 │ -- System (GPIO 21)
                                 └─────┴─────┘
```

---

## 3. Circuit 1: Power Distribution & Star Grounding

### Why Star Grounding is Mandatory
DC motors generate sharp inductive voltage spikes and EMF back-feed when spinning or stopping. If the Raspberry Pi shares a single thin ground loop wire with the motor driver, the Pi will experience brownout voltage drops and kernel freeze.

### Exact Power Connection Scheme:

```
[Main Battery Positive (+)]
         │
         ├──► SPST Switch (Input)
                    │ (Switch Output)
                    ├──► [Buck Converter IN+] (e.g. XL4015) ──► OUT+ (5.1V) ──► Pi USB-C (+)
                    └──► [Motor Driver 12V VMS (+)]

[Main Battery Negative (-)]
         │
         ▼
[ ★ STAR GROUND BUS BAR ★ ]
         │
         ├──► [Buck Converter IN-] ──► OUT- (GND) ──► Pi USB-C (GND)
         ├──► [Motor Driver GND]
         └──► [Raspberry Pi GPIO Pin 6, 14, 30, or 34] (Ground Reference)
```

#### Power Component Ratings:
- **Main Battery**: 2S LiPo (7.4V nominal) or 3S LiPo (11.1V nominal), minimum 2200 mAh, 20C discharge.
- **Buck Converter**: High-efficiency switching regulator (LM2596 or XL4015). **Must be tuned to 5.1V** with an output capability of **≥ 3.5 Amps continuous**.
- **Decoupling Capacitor**: Solder a **1000 µF 25V Electrolytic Capacitor** across the motor driver 12V and GND terminals to absorb motor inductive kickback.

---

## 4. Circuit 2: SPI TFT Display (Pin-by-Pin Wiring)

This sub-circuit drives the **320×240 TFT Display** (compatible with ST7789, ILI9341, ST7735, and Waveshare screens) to display the **Green Checkmark (✔)** and **Red X Mark (✖)**.

```
       TFT DISPLAY MODULE                          RASPBERRY PI 4B
   ┌────────────────────────┐                   ┌─────────────────────┐
   │ 1. VCC (3.3V)          ├───────────────────┤ Pin 01 (3.3V Power) │
   │ 2. GND                 ├───────────────────┤ Pin 06 (Ground)     │
   │ 3. CS / CE0            ├───────────────────┤ Pin 24 (GPIO 8)     │
   │ 4. RESET / RST         ├───────────────────┤ Pin 18 (GPIO 24)    │
   │ 5. DC / RS             ├───────────────────┤ Pin 22 (GPIO 25)    │
   │ 6. MOSI / DIN          ├───────────────────┤ Pin 19 (GPIO 10)    │
   │ 7. SCLK / CLK          ├───────────────────┤ Pin 23 (GPIO 11)    │
   │ 8. LED / BL (Backlight)├───────────────────┤ Pin 12 (GPIO 18)    │
   └────────────────────────┘                   └─────────────────────┘
```

### Pin-by-Pin Interconnection Table:

| TFT Display Pin | Wire Color | Raspberry Pi Physical Pin | BCM GPIO | Electrical Level | Description |
|---|---|---|---|---|---|
| **VCC** | **Red** | **Pin 01** | `3V3` | 3.3V DC | Main screen logic power |
| **GND** | **Black** | **Pin 06** | `GND` | 0V (Ground) | Common circuit return |
| **CS / CE0** | **Yellow** | **Pin 24** | `GPIO 8` | 3.3V Logic | Active-Low SPI Chip Select |
| **RESET / RST** | **Blue** | **Pin 18** | `GPIO 24` | 3.3V Logic | Hardware display reset trigger |
| **DC / RS** | **Green** | **Pin 22** | `GPIO 25` | 3.3V Logic | Data (High) vs Command (Low) |
| **MOSI / DIN** | **Orange** | **Pin 19** | `GPIO 10` | 3.3V High-Speed | SPI Serial Data Input |
| **SCLK / CLK** | **White** | **Pin 23** | `GPIO 11` | 3.3V High-Speed | SPI Serial Clock signal |
| **LED / BL** | **Purple** | **Pin 12** | `GPIO 18` | 3.3V PWM | Backlight brightness control (or tie to 3.3V) |

> [!WARNING]
> Do **NOT** connect the TFT VCC pin to 5V (Physical Pin 2 or 4) unless your TFT breakout specifically includes an onboard 3.3V AMS1117 regulator. Standard ST7789 chips run strictly on 3.3V logic.

---

## 5. Circuit 3: Motor Driver & Navigation Control (/cmd_vel)

The ROS 2 navigation state machine publishes rotational commands on `/cmd_vel` (`angular.z = 0.3` during `'SEARCHING'` and `0.0` during `'LOCKED'`).

This sub-circuit shows how the Raspberry Pi 4B drives an **L298N Dual H-Bridge Motor Controller**:

```
        RASPBERRY PI 4B                            L298N DUAL H-BRIDGE
   ┌────────────────────────┐                   ┌───────────────────────────┐
   │ Pin 32 (GPIO 12 - PWM0)├───────────────────┤ ENA (Left Motor Speed)    │
   │ Pin 29 (GPIO 5)        ├───────────────────┤ IN1 (Left Motor Dir A)    │
   │ Pin 31 (GPIO 6)        ├───────────────────┤ IN2 (Left Motor Dir B)    │
   │ Pin 33 (GPIO 13)       ├───────────────────┤ IN3 (Right Motor Dir A)   │
   │ Pin 35 (GPIO 19)       ├───────────────────┤ IN4 (Right Motor Dir B)   │
   │ Pin 36 (GPIO 16 - PWM1)├───────────────────┤ ENB (Right Motor Speed)   │
   │ Pin 34 (GND)           ├───────────────────┤ GND (Common Logic Ground) │
   └────────────────────────┘                   └──────┬─────────────┬──────┘
                                                       │             │
                                                       ▼             ▼
                                                   [MOTOR A]     [MOTOR B]
                                                  Left Wheel    Right Wheel
```

### Motor Connection Pin Table:

| Signal Function | Pi Physical Pin | BCM GPIO | L298N Pin | Movement Function |
|---|---|---|---|---|
| **Left Speed PWM** | **Pin 32** | `GPIO 12` | **ENA** | Hardware PWM (0–255 speed) |
| **Left Forward** | **Pin 29** | `GPIO 5` | **IN1** | High = Forward, Low = Reverse |
| **Left Reverse** | **Pin 31** | `GPIO 6` | **IN2** | Low = Forward, High = Reverse |
| **Right Forward**| **Pin 33** | `GPIO 13` | **IN3** | High = Forward, Low = Reverse |
| **Right Reverse**| **Pin 35** | `GPIO 19` | **IN4** | Low = Forward, High = Reverse |
| **Right Speed PWM**| **Pin 36**| `GPIO 16` | **ENB** | Hardware PWM (0–255 speed) |
| **Common GND**   | **Pin 34** | `GND` | **GND** | Reference Ground |

### Truth Table for Autonomous Rotation (`angular.z = 0.3`):
To spin in place clockwise to scan the room:
- **Left Motor (A)**: `IN1 = HIGH`, `IN2 = LOW` (Drive Forward at ~30% PWM)
- **Right Motor (B)**: `IN3 = LOW`, `IN4 = HIGH` (Drive Reverse at ~30% PWM)

### Truth Table for Full Stop (`'LOCKED'` State):
When attendance is verified:
- **Left Motor (A)**: `IN1 = LOW`, `IN2 = LOW`, `ENA = 0` (Brake / Coast)
- **Right Motor (B)**: `IN3 = LOW`, `IN4 = LOW`, `ENB = 0` (Brake / Coast)

---

## 6. Circuit 4: External USB Camera & Optional Audio Buzzer

### A. USB Camera Port Connection
```
Raspberry Pi 4B Rear Ports View:
 ┌──────────────────────┐
 │ [Ethernet]  [USB 3]  │  ◄── USB 3.0 (Blue): Leave empty for lower 2.4GHz RF noise
 │             [USB 3]  │
 │                      │
 │             [USB 2]  │  ◄── Top Black Port: Connect USB Camera Here!
 │             [USB 2]  │  ◄── Bottom Black Port: Keyboard / Flash drive
 └──────────────────────┘
```
- **Port Choice**: Plug the USB webcam into **USB 2.0 (Top Black Port)**.
- **Video Standard**: USB 2.0 provides 480 Mbps, which easily handles 640×480 MJPG video at 30 FPS with negligible CPU transmission overhead.

---

### B. Optional 5V Active Buzzer (Audible Confirmation Beep)
You can optionally attach a small **5V Active Buzzer** to emit a brief "Beep" when the Green Checkmark appears on the TFT screen:

```
   Raspberry Pi 4B Physical Header:
      Pin 02 (5V Power)   ──► Buzzer (+) Positive Terminal
      Pin 16 (GPIO 23)    ──► Base of 2N2222 NPN Transistor (via 1kΩ Resistor)
      Transistor Collector ──► Buzzer (-) Negative Terminal
      Transistor Emitter   ──► Ground (Pin 14)
```

---

## 7. Recommended Wire Gauges & Color Coding

Using consistent wire coloring prevents costly short circuits during assembly:

| Circuit Type | Wire Color | Gauge (AWG) | Purpose |
|---|---|---|---|
| **Main Battery Line** | **Thick Red** | 16–18 AWG | High-current raw battery positive |
| **Main Battery Return** | **Thick Black** | 16–18 AWG | High-current raw battery ground |
| **Regulated 5.1V Line** | **Red** | 20–22 AWG | Clean 5.1V power to Raspberry Pi |
| **Logic 3.3V Line** | **Orange / Red** | 24–28 AWG | Clean 3.3V power to TFT screen |
| **Logic Ground** | **Black / Brown**| 24–28 AWG | Low-current signal return |
| **SPI Data Lines** | **Yellow / Green** | 24–28 AWG | MOSI, MISO, SCLK, CS high-speed data |
| **Motor Control Lines** | **Blue / White** | 22–26 AWG | IN1–IN4, ENA, ENB direction and speed |

---

## 8. Pre-Power-On Multimeter Safety Checklist

Before flipping the main battery power switch for the first time, complete this **5-minute electrical verification**:

1. **[ ] Disconnect Pi USB-C**: Unplug the USB-C cable from the Raspberry Pi.
2. **[ ] Turn on Battery Switch**: Power on the buck converter and motor driver.
3. **[ ] Measure Buck Output**: Place multimeter probes across the buck converter output.
   - **Target Voltage**: **5.10V to 5.20V DC** (Adjust the brass potentiometer screw until exactly in this range).
   - If voltage exceeds 5.30V, **do not connect to Pi**—adjust potentiometer immediately.
4. **[ ] Continuity Test to Ground**:
   - Touch one probe to the Raspberry Pi USB-C ground shell.
   - Touch the other probe to the battery negative terminal.
   - Multimeter must beep (0.0 Ω resistance), confirming **Common Ground** is intact.
5. **[ ] Check for Shorts on 3.3V Rail**:
   - Turn off power.
   - Measure resistance between Pi **Pin 1 (3.3V)** and **Pin 6 (GND)**.
   - Must show high resistance (> 1 kΩ). If resistance is near 0 Ω, check your TFT wiring for shorts!
6. **[ ] Connect & Boot**:
   - Re-attach the USB-C connector to the Pi.
   - Plug in the USB Camera.
   - Turn on the power switch. The Raspberry Pi red PWR LED should glow solid, and green ACT LED should flicker as it boots!
7. **[ ] Execute System**:
   ```bash
   cd ~/rosprojectattendance
   python3 main.py
   ```

---

## 🏁 Summary

With the circuit completed as detailed above:
- **Zero Brownouts**: Motor electrical noise is isolated from the Pi compute module.
- **Clean SPI Bus**: TFT display refreshes smoothly without visual flickering.
- **Robust Telemetry**: External camera streams clean 30 FPS video to the face recognition confirmation gate.
- **Autonomous Mobility**: ROS 2 Humble commands drive `/cmd_vel` smoothly across the L298N H-bridge.
