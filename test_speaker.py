"""
=============================================================================
 ROS Attendance Bot — Speaker Test Script
 Run this on the Raspberry Pi to verify USB speakers are working.
 Tests: espeak TTS, audio device detection, and the AudioAnnouncer class.
=============================================================================
 Usage (on the Pi):
     python3 test_speaker.py
=============================================================================
"""

import subprocess
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── ANSI Colors ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"  {GREEN}✓{RESET}  {msg}")
def fail(msg):print(f"  {RED}✗{RESET}  {msg}")
def info(msg):print(f"  {CYAN}→{RESET}  {msg}")


# ── Step 1: Check espeak is installed ────────────────────────────────────────
def check_espeak():
    print(f"\n{BOLD}[1/4] Checking espeak installation...{RESET}")
    try:
        result = subprocess.run(
            ["espeak", "--version"],
            capture_output=True, text=True, timeout=5
        )
        ok(f"espeak found: {result.stdout.strip() or result.stderr.strip()}")
        return True
    except FileNotFoundError:
        fail("espeak NOT installed!")
        print(f"\n  {YELLOW}Fix it on the Pi:{RESET}")
        print("      sudo apt-get update")
        print("      sudo apt-get install -y espeak espeak-ng")
        return False


# ── Step 2: List ALSA audio devices ──────────────────────────────────────────
def list_audio_devices():
    print(f"\n{BOLD}[2/4] Scanning ALSA audio output devices...{RESET}")
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            for line in lines:
                ok(line)
        else:
            fail("No ALSA playback devices found — is the USB speaker plugged in?")
    except FileNotFoundError:
        fail("aplay not found (install alsa-utils: sudo apt-get install alsa-utils)")
    except Exception as e:
        fail(f"aplay error: {e}")


# ── Step 3: Raw espeak test — "Hello Niyanth" ─────────────────────────────────
def test_espeak_direct():
    print(f"\n{BOLD}[3/4] Speaking directly via espeak...{RESET}")
    text = "Hello Niyanth! Speaker test successful. The Raspberry Pi and speakers are working together!"
    info(f'Speaking: "{text}"')
    cmd = [
        "espeak",
        "-v", "en",
        "-s", "155",    # speed
        "-a", "180",    # amplitude / volume
        "-p", "55",     # pitch
        text
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            ok("espeak completed successfully -> you should have heard the audio!")
        else:
            fail(f"espeak exited with code {result.returncode}")
            if result.stderr:
                fail(f"stderr: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        fail("espeak timed out (>15 s). Check speaker connection.")
    except Exception as e:
        fail(f"Unexpected error: {e}")


# ── Step 4: Test via AudioAnnouncer class (used by the real system) ───────────
def test_audio_announcer_class():
    print(f"\n{BOLD}[4/4] Testing AudioAnnouncer class (your real system)...{RESET}")
    try:
        from audio_announcer import AudioAnnouncer
        announcer = AudioAnnouncer(enabled=True)
        time.sleep(0.5)  # let worker thread spin up

        announcer.speak("Hello Niyanth! Audio Announcer class is working perfectly.")
        info("Message queued — waiting for it to finish speaking...")
        time.sleep(6)    # wait for speech to complete

        announcer.shutdown()
        ok("AudioAnnouncer class test passed!")
    except ImportError:
        fail("Could not import AudioAnnouncer — make sure you're running from the project root.")
    except Exception as e:
        fail(f"AudioAnnouncer error: {e}")


# ── Summary ───────────────────────────────────────────────────────────────────
def print_summary():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Speaker Test Complete{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"""
  If you heard both announcements:
    USB speakers are connected and working
    espeak TTS is functioning on the Pi
    AudioAnnouncer class is ready for the main system

  If you heard NOTHING:
    1. Check USB speaker is plugged into the Pi USB port
    2. Run:  aplay -l   to see detected audio cards
    3. Set volume:  amixer -c 1 sset Master 100%
    4. Try a direct test:  espeak "hello" -v en -a 200
    5. If still silent, check:  cat /proc/asound/cards
       Then fix ALSA:  sudo nano /etc/asound.conf
       Add:  defaults.pcm.card N   (replace N with your USB card number)
""")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{BOLD}{CYAN}{'='*60}")
    print("   ROS Attendance Bot — Speaker Hardware Test")
    print(f"{'='*60}{RESET}")

    espeak_ok = check_espeak()
    list_audio_devices()

    if espeak_ok:
        test_espeak_direct()
        time.sleep(1)
        test_audio_announcer_class()
    else:
        fail("Skipping speech tests — espeak must be installed first.")
        sys.exit(1)

    print_summary()
