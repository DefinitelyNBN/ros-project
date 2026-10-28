// =============================================================================
//  Arduino Uno + 2.4" / 2.8" TFT LCD Shield (MCUFRIEND / SPFD5408 / ILI9341)
//  Face Recognition Attendance Bot Visual Feedback Display
//
//  Connected to Raspberry Pi via USB Serial Cable (/dev/ttyACM0 or /dev/ttyUSB0).
//  Baud rate: 115200.
//
//  Commands from Raspberry Pi:
//    - OK:<NAME>:<ID>   -> Displays GREEN CHECKMARK (✔), Name, ID, Attendance Marked
//    - UNKNOWN          -> Displays RED X MARK (✖), "ACCESS DENIED / UNREGISTERED"
//    - IDLE:<COUNT>     -> Returns to Scanning / Idle Radar Screen with total count
//    - PING             -> Responds with "PONG"
//
//  Libraries Required (install via Arduino Library Manager):
//    1. "Adafruit GFX Library" by Adafruit
//    2. "MCUFRIEND_kbv" by David Prentice
//       (Or "Adafruit_TFTLCD" for older 8-bit parallel shields)
// =============================================================================

#include <Adafruit_GFX.h>
#include <MCUFRIEND_kbv.h>

MCUFRIEND_kbv tft;

// 16-bit 565 RGB Color Definitions
#define BLACK       0x0000
#define NAVY        0x000F
#define DARKGREEN   0x03E0
#define DARKCYAN    0x03EF
#define MAROON      0x7800
#define PURPLE      0x780F
#define OLIVE       0x7BE0
#define LIGHTGREY   0xC618
#define DARKGREY    0x3186
#define BLUE        0x001F
#define GREEN       0x07E0
#define CYAN        0x07FF
#define RED         0xF800
#define MAGENTA     0xF81F
#define YELLOW      0xFFE0
#define WHITE       0xFFFF
#define ORANGE      0xFD20
#define EMERALD     0x2E6B
#define CRIMSON     0xD000
#define BG_DARK     0x0842

// Display states
enum ScreenState {
  STATE_IDLE,
  STATE_CHECKMARK,
  STATE_CROSS
};

ScreenState currentState = STATE_IDLE;
unsigned long stateTimestamp = 0;
const unsigned long HOLD_DURATION = 4000; // Hold check/cross for 4 seconds before returning to idle
int attendanceCount = 0;

// Communication buffer
String inputBuffer = "";

// Forward declarations
void showIdleScreen(int count);
void showSuccessCheckmark(String name, String id);
void showUnknownCross();
void drawCheckmark(int cx, int cy, int radius, uint16_t color);
void drawCross(int cx, int cy, int radius, uint16_t color);
void handleSerialCommand(String cmd);

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; } // wait for serial port to connect

  uint16_t ID = tft.readID();
  // Register dump showed reg(0x00D3) = 00 00 91 41 -> ILI9341 with bit 9 low
  if (ID == 0x9141 || ID == 0xD3D3 || ID == 0xD3 || ID == 0x0 || ID == 0xFFFF) {
    ID = 0x9341;
  }
  tft.begin(ID);

  // Landscape orientation: 320x240
  tft.setRotation(1);
  tft.fillScreen(BG_DARK);

  Serial.println(F("[ARDUINO_TFT] Ready. Waiting for commands..."));
  showIdleScreen(0);
}

void loop() {
  // 1. Process incoming Serial messages from Raspberry Pi
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        handleSerialCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }

  // 2. Auto-revert back to idle after hold duration
  if (currentState != STATE_IDLE && (millis() - stateTimestamp > HOLD_DURATION)) {
    currentState = STATE_IDLE;
    showIdleScreen(attendanceCount);
  }
}

void handleSerialCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd.startsWith("OK:")) {
    // Format: OK:FirstName_LastName:ID
    int firstColon = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon + 1);

    String personName = "Student";
    String studentId = "";

    if (secondColon != -1) {
      personName = cmd.substring(firstColon + 1, secondColon);
      studentId  = cmd.substring(secondColon + 1);
    } else {
      personName = cmd.substring(firstColon + 1);
    }

    // Replace underscores with spaces for clean UI
    personName.replace("_", " ");

    attendanceCount++;
    currentState = STATE_CHECKMARK;
    stateTimestamp = millis();
    showSuccessCheckmark(personName, studentId);
    Serial.println(F("ACK:SUCCESS_DISPLAYED"));

  } else if (cmd == "UNKNOWN" || cmd.startsWith("UNKNOWN:") || cmd == "INTRUDER" || cmd.startsWith("INTRUDER:")) {
    currentState = STATE_CROSS;
    stateTimestamp = millis();
    showUnknownCross();
    Serial.println(F("ACK:INTRUDER_DISPLAYED"));

  } else if (cmd.startsWith("IDLE")) {
    int colon = cmd.indexOf(':');
    if (colon != -1) {
      attendanceCount = cmd.substring(colon + 1).toInt();
    }
    currentState = STATE_IDLE;
    showIdleScreen(attendanceCount);
    Serial.println(F("ACK:IDLE_DISPLAYED"));

  } else if (cmd == "PING") {
    Serial.println(F("PONG"));
  }
}

// -----------------------------------------------------------------------------
// UI SCREEN: IDLE / PERIMETER PATROL RADAR
// -----------------------------------------------------------------------------
void showIdleScreen(int count) {
  tft.fillScreen(BG_DARK);

  // Top Tactical Header Banner
  tft.fillRect(0, 0, 320, 32, NAVY);
  tft.drawFastHLine(0, 32, 320, CYAN);
  tft.setTextColor(CYAN);
  tft.setTextSize(2);
  tft.setCursor(22, 8);
  tft.print(F("[SEC-BOT] PATROL ACTIVE"));

  // Tactical Corner Brackets
  int margin = 10;
  int blen = 15;
  // Top-left
  tft.drawFastHLine(margin, 40, blen, CYAN);
  tft.drawFastVLine(margin, 40, blen, CYAN);
  // Top-right
  tft.drawFastHLine(320 - margin - blen, 40, blen, CYAN);
  tft.drawFastVLine(320 - margin, 40, blen, CYAN);
  // Bottom-left
  tft.drawFastHLine(margin, 205, blen, CYAN);
  tft.drawFastVLine(margin, 205 - blen, blen, CYAN);
  // Bottom-right
  tft.drawFastHLine(320 - margin - blen, 205, blen, CYAN);
  tft.drawFastVLine(320 - margin, 205 - blen, blen, CYAN);

  // Center Security Radar Reticle
  int cx = 160;
  int cy = 120;
  tft.drawCircle(cx, cy, 55, CYAN);
  tft.drawCircle(cx, cy, 38, DARKCYAN);
  tft.drawCircle(cx, cy, 20, NAVY);
  tft.drawFastHLine(cx - 65, cy, 130, DARKCYAN);
  tft.drawFastVLine(cx, cy - 65, 130, DARKCYAN);
  tft.fillCircle(cx, cy, 3, CYAN);

  // Subtitle
  tft.setTextColor(WHITE);
  tft.setTextSize(1);
  tft.setCursor(85, 185);
  tft.print(F("PERIMETER SURVEILLANCE ZONE"));

  // Bottom Status Bar
  tft.fillRect(0, 212, 320, 28, BLACK);
  tft.drawFastHLine(0, 212, 320, DARKCYAN);
  tft.setTextColor(GREEN);
  tft.setTextSize(1);
  tft.setCursor(12, 222);
  tft.print(F("STATUS: SECURE"));

  tft.setTextColor(CYAN);
  tft.setCursor(185, 222);
  tft.print(F("AUTHORIZED: "));
  tft.setTextColor(WHITE);
  tft.print(count);
}

// -----------------------------------------------------------------------------
// UI SCREEN: AUTHORIZED ACCESS GRANTED (WELCOME BY NAME)
// -----------------------------------------------------------------------------
void showSuccessCheckmark(String name, String id) {
  tft.fillScreen(BG_DARK);

  // Glowing Emerald Header
  tft.fillRect(0, 0, 320, 35, DARKGREEN);
  tft.drawFastHLine(0, 35, 320, GREEN);
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  tft.setCursor(55, 9);
  tft.print(F("ACCESS GRANTED"));

  // Green Security Shield & Checkmark
  drawCheckmark(160, 95, 42, GREEN);

  // Personalized Welcome Header
  tft.setTextColor(GREEN);
  tft.setTextSize(1);
  tft.setCursor(105, 148);
  tft.print(F("WELCOME AUTHORIZED:"));

  // Full Name
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  int nameX = max(10, 160 - (int)(name.length() * 6));
  tft.setCursor(nameX, 164);
  tft.print(name);

  // Security Clearance / ID
  tft.setTextColor(CYAN);
  tft.setTextSize(1);
  if (id.length() > 0) {
    int idX = max(10, 160 - (int)(id.length() * 3) - 15);
    tft.setCursor(idX, 190);
    tft.print(F("CLEARANCE: "));
    tft.print(id);
  } else {
    tft.setCursor(95, 190);
    tft.print(F("IDENTITY VERIFIED"));
  }

  // Bottom Confirmation Bar
  tft.fillRect(0, 210, 320, 30, DARKGREEN);
  tft.setTextColor(WHITE);
  tft.setTextSize(1);
  tft.setCursor(75, 220);
  tft.print(F("PERIMETER PASS CONFIRMED"));
}

// -----------------------------------------------------------------------------
// UI SCREEN: INTRUDER ALERT! (UNFAMILIAR / UNREGISTERED PERSON)
// -----------------------------------------------------------------------------
void showUnknownCross() {
  tft.fillScreen(CRIMSON);

  // Flashing Hazard Alert Header
  tft.fillRect(0, 0, 320, 38, RED);
  tft.drawFastHLine(0, 38, 320, WHITE);
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  tft.setCursor(35, 11);
  tft.print(F("INTRUDER ALERT!"));

  // High-Visibility Hazard Cross
  drawCross(160, 100, 44, WHITE);

  // Threat Warning Text
  tft.setTextColor(YELLOW);
  tft.setTextSize(2);
  tft.setCursor(45, 158);
  tft.print(F("UNFAMILIAR FACE"));

  tft.setTextColor(WHITE);
  tft.setTextSize(1);
  tft.setCursor(65, 188);
  tft.print(F("SECURITY SIREN TRIGGERED"));

  // Bottom Warning Banner
  tft.fillRect(0, 210, 320, 30, RED);
  tft.drawFastHLine(0, 210, 320, WHITE);
  tft.setTextColor(WHITE);
  tft.setTextSize(1);
  tft.setCursor(55, 220);
  tft.print(F("WARNING: STEP BACK FROM ROBOT"));
}

// -----------------------------------------------------------------------------
// GRAPHICS HELPER: DRAW THICK CHECKMARK (✔)
// -----------------------------------------------------------------------------
void drawCheckmark(int cx, int cy, int radius, uint16_t color) {
  // Outer circle ring
  for (int r = radius - 4; r <= radius; r++) {
    tft.drawCircle(cx, cy, r, color);
  }

  // Inner thick checkmark polyline: (-20, 0) -> (-6, 16) -> (22, -14)
  for (int w = -3; w <= 3; w++) {
    tft.drawLine(cx - 20, cy + w, cx - 6, cy + 16 + w, color);
    tft.drawLine(cx - 6, cy + 16 + w, cx + 22, cy - 14 + w, color);
  }
}

// -----------------------------------------------------------------------------
// GRAPHICS HELPER: DRAW THICK RED/WHITE HAZARD CROSS (✖)
// -----------------------------------------------------------------------------
void drawCross(int cx, int cy, int radius, uint16_t color) {
  // Outer circle ring
  for (int r = radius - 4; r <= radius; r++) {
    tft.drawCircle(cx, cy, r, color);
  }

  // Thick X cross lines
  int offset = 20;
  for (int w = -4; w <= 4; w++) {
    tft.drawLine(cx - offset, cy - offset + w, cx + offset, cy + offset + w, color);
    tft.drawLine(cx - offset, cy + offset + w, cx + offset, cy - offset + w, color);
  }
}
