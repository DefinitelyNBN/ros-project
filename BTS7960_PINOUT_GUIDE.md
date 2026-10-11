# BTS7960 Motor Driver Wiring & Pin Connection Guide

This document specifies the exact, pin-by-pin hardware connections between the **Raspberry Pi 4B (40-Pin GPIO)** and **two BTS7960 (IBT-2) 43A High-Current Dual H-Bridge Motor Drivers** for autonomous differential-drive robot movement.

---

## ⚡ 1. High-Current Battery & Power Connections (Screw Terminals)

Each BTS7960 driver has 4 heavy-duty screw terminals:
- `B+ (VCC)`: Main Motor Battery Positive (+12V to +24V).
- `B- (GND)`: Main Motor Battery Negative (0V Ground).
- `M+`: Motor lead A.
- `M-`: Motor lead B.

```
                         [12V-24V Main Battery (+)]
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
         [Left BTS7960 B+]                   [Right BTS7960 B+]
         
                         [12V-24V Main Battery (-)]
                                     │
               ┌─────────────────────┼─────────────────────┐
               ▼                     ▼                     ▼
      [Left BTS7960 B-]     [Right BTS7960 B-]     [Raspberry Pi GND]
                                                   (Pin 20, 30, or 34)
                                                   ★ COMMON STAR GROUND ★
```

> [!CAUTION]
> **COMMON GROUND IS MANDATORY**: You MUST connect the Battery Negative (-) to one of the Raspberry Pi's GND pins (such as Physical Pin 20 or 34). Without a common ground reference, the PWM logic signals cannot function and erratic motor jumping will occur.

---

## 🔌 2. Left Motor BTS7960 Driver (Logic Header Pins)

Controls the **Left Wheel**:

| BTS7960 Pin | Connect to | Pi Physical Pin | Pi BCM GPIO | Electrical Level | Function |
|---|---|---|---|---|---|
| **VCC** | **Pi 5V** | **Pin 02** | `5V` | 5.0V DC | Logic power for isolator IC |
| **GND** | **Pi Ground** | **Pin 06** | `GND` | 0.0V Ground | Signal ground |
| **R_EN** | **Pi GPIO 5** | **Pin 29** | `GPIO 5` | 3.3V / 5V | Forward Enable *(or jumper to VCC)* |
| **L_EN** | **Pi GPIO 5** | **Pin 29** | `GPIO 5` | 3.3V / 5V | Reverse Enable *(or jumper to VCC)* |
| **RPWM** | **Pi GPIO 12** | **Pin 32** | `GPIO 12` | 3.3V PWM | **Left Forward Speed** (Hardware PWM0) |
| **LPWM** | **Pi GPIO 13** | **Pin 33** | `GPIO 13` | 3.3V PWM | **Left Reverse Speed** (Hardware PWM1) |
| **R_IS** | *Not Connected*| — | — | — | Current alarm (leave floating) |
| **L_IS** | *Not Connected*| — | — | — | Current alarm (leave floating) |

*(Quick Tip: You can connect `R_EN` and `L_EN` together with a short jumper wire and connect both to Pin 29, or simply tie them directly to VCC on the driver board).*

---

## 🔌 3. Right Motor BTS7960 Driver (Logic Header Pins)

Controls the **Right Wheel**:

| BTS7960 Pin | Connect to | Pi Physical Pin | Pi BCM GPIO | Electrical Level | Function |
|---|---|---|---|---|---|
| **VCC** | **Pi 5V** | **Pin 04** | `5V` | 5.0V DC | Logic power for isolator IC |
| **GND** | **Pi Ground** | **Pin 14** | `GND` | 0.0V Ground | Signal ground |
| **R_EN** | **Pi GPIO 6** | **Pin 31** | `GPIO 6` | 3.3V / 5V | Forward Enable *(or jumper to VCC)* |
| **L_EN** | **Pi GPIO 6** | **Pin 31** | `GPIO 6` | 3.3V / 5V | Reverse Enable *(or jumper to VCC)* |
| **RPWM** | **Pi GPIO 18** | **Pin 12** | `GPIO 18` | 3.3V PWM | **Right Forward Speed** (Hardware PWM0) |
| **LPWM** | **Pi GPIO 19** | **Pin 35** | `GPIO 19` | 3.3V PWM | **Right Reverse Speed** (Hardware PWM1) |
| **R_IS** | *Not Connected*| — | — | — | Current alarm (leave floating) |
| **L_IS** | *Not Connected*| — | — | — | Current alarm (leave floating) |

---

## 🗺️ 4. Raspberry Pi 4B 40-Pin Physical Pinout Map

```
                     ┌──────────────────┐
        3.3V Power - │ [ 1]  [ 2] │ - 5V Power ──► Left BTS7960 VCC
                     │ [ 3]  [ 4] │ - 5V Power ──► Right BTS7960 VCC
                     │ [ 5]  [ 6] │ - Ground ────► Left BTS7960 GND
                     │ [ 7]  [ 8] │
                     │ [ 9]  [10] │
                     │ [11]  [12] │ - GPIO 18 ───► Right Motor RPWM (Forward)
                     │ [13]  [14] │ - Ground ────► Right BTS7960 GND
                     │ [15]  [16] │
                     │ [17]  [18] │
                     │ [19]  [20] │ - Ground ────► Battery Negative (Common Star GND)
                     │ [21]  [22] │
                     │ [23]  [24] │
                     │ [25]  [26] │
                     │ [27]  [28] │
 Left EN (GPIO 5) ──►│ [29]  [30] │ - Ground
Right EN (GPIO 6) ──►│ [31]  [32] │ - GPIO 12 ───► Left Motor RPWM (Forward)
 Left LPWM (GPIO 13)─►│ [33]  [34] │ - Ground
Right LPWM (GPIO 19)─►│ [35]  [36] │ - GPIO 16
                     │ [37]  [38] │
                     │ [39]  [40] │
                     └──────────────────┘
```

---

## 🤖 5. Software Control & Truth Table

The code in `motor_controller.py` controls these pins using standard PWM duty cycle:

### A. Searching State (Scan Room in Place)
- **Left Motor**: `RPWM = 30%`, `LPWM = 0%` (Left wheel drives forward)
- **Right Motor**: `RPWM = 0%`, `LPWM = 30%` (Right wheel drives reverse)
- **Result**: Robot spins clockwise in place scanning for faces.

### B. Locked State (Attendance Confirmed / Halt)
- **Left Motor**: `RPWM = 0%`, `LPWM = 0%` (Full brake)
- **Right Motor**: `RPWM = 0%`, `LPWM = 0%` (Full brake)
- **Result**: Robot stops completely for 5-second cooldown and displays Green Checkmark on TFT.

---

## 🧪 6. Testing Your Wiring

Once you finish wiring the jumper wires, elevate your robot so the wheels are in the air and run:

```bash
python3 motor_controller.py --test
```

If one wheel spins backwards during the test:
- Simply swap the **`M+` and `M-`** motor wires on that side's BTS7960 screw terminal block.
