"""
=============================================================================
 ROS Attendance Bot — Mobile Web Teleoperation Server
 Serves a touch-friendly joystick UI to any phone on the same WiFi network.
=============================================================================
 Usage (on the Pi):
     python3 teleop_server.py
     python3 teleop_server.py --port 5000 --speed 0.4

 Then on your phone:
     Open browser → http://<raspberry-pi-ip>:5000

 Find Pi IP:
     hostname -I
=============================================================================
 Install dependency (one-time):
     pip3 install flask
=============================================================================
"""

import argparse
import logging
import threading
import time
from flask import Flask, request, jsonify, render_template_string

try:
    from motor_controller import MotorDriver
    MOTORS_AVAILABLE = True
except Exception as e:
    MOTORS_AVAILABLE = False
    print(f"[WARNING] MotorDriver not available: {e} — running in simulation mode")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [TELEOP-WEB] %(message)s")
log = logging.getLogger("teleop_server")

app = Flask(__name__)

# ── Global state ──────────────────────────────────────────────────────────────
driver       = None
current_cmd  = {"left": 0.0, "right": 0.0, "state": "IDLE"}
base_speed   = 0.40          # default speed, overridable via args
WATCHDOG_SEC = 0.5           # stop motors if no command in this many seconds
_last_cmd_ts = time.time()

# ── Watchdog: stop motors if phone disconnects ────────────────────────────────
def _watchdog():
    global _last_cmd_ts
    while True:
        time.sleep(0.1)
        if time.time() - _last_cmd_ts > WATCHDOG_SEC:
            if driver and current_cmd["state"] != "IDLE":
                driver.stop()
                current_cmd.update({"left": 0.0, "right": 0.0, "state": "IDLE"})

# ── HTML Template (served to the phone) ───────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>🤖 Robot Teleop</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0D1117;
    --card:      #161B22;
    --border:    #30363D;
    --accent:    #58A6FF;
    --green:     #3FB950;
    --red:       #F78166;
    --yellow:    #E3B341;
    --text:      #E6EDF3;
    --muted:     #8B949E;
  }

  html, body {
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    touch-action: none;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  /* ── Header ── */
  header {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    background: var(--card);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 10;
  }
  header h1 { font-size: 1rem; font-weight: 700; letter-spacing: 0.02em; }
  #status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    transition: background 0.3s;
  }
  #status-dot.idle    { background: var(--muted); box-shadow: none; }
  #status-dot.moving  { background: var(--green); box-shadow: 0 0 8px var(--green); }
  #status-dot.stopped { background: var(--red);   box-shadow: 0 0 8px var(--red); }

  /* ── State badge ── */
  #state-label {
    font-size: 0.75rem;
    color: var(--muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  /* ── Speed row ── */
  .speed-row {
    width: 90%;
    max-width: 400px;
    margin-top: 18px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .speed-row label { font-size: 0.8rem; color: var(--muted); white-space: nowrap; }
  #speed-slider {
    flex: 1;
    -webkit-appearance: none;
    appearance: none;
    height: 6px;
    border-radius: 3px;
    background: var(--border);
    outline: none;
  }
  #speed-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 22px; height: 22px; border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    box-shadow: 0 0 8px var(--accent);
  }
  #speed-val {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--accent);
    min-width: 38px;
    text-align: right;
  }

  /* ── D-pad grid ── */
  .dpad-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 10px 0 20px;
  }
  .dpad {
    display: grid;
    grid-template-columns: repeat(3, 90px);
    grid-template-rows: repeat(3, 90px);
    gap: 10px;
  }
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 16px;
    border: 1.5px solid var(--border);
    background: var(--card);
    color: var(--text);
    font-size: 2rem;
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
    transition: background 0.1s, transform 0.08s, box-shadow 0.1s;
    -webkit-tap-highlight-color: transparent;
  }
  .btn:active, .btn.pressed {
    background: #1c2d42;
    box-shadow: 0 0 18px var(--accent);
    border-color: var(--accent);
    transform: scale(0.94);
  }
  .btn.stop {
    background: #2d1a1a;
    border-color: var(--red);
    color: var(--red);
  }
  .btn.stop:active, .btn.stop.pressed {
    background: #4a1c1c;
    box-shadow: 0 0 18px var(--red);
  }
  .btn.arc {
    border-color: var(--yellow);
    color: var(--yellow);
    font-size: 1.5rem;
  }
  .btn.arc:active, .btn.arc.pressed {
    background: #2d2a0d;
    box-shadow: 0 0 18px var(--yellow);
  }
  .empty { visibility: hidden; }

  /* ── Motor bars ── */
  .motor-row {
    display: flex;
    gap: 24px;
    margin-top: 10px;
    margin-bottom: 8px;
  }
  .motor-col { display: flex; flex-direction: column; align-items: center; gap: 4px; }
  .motor-col span { font-size: 0.7rem; color: var(--muted); }
  .motor-bar-wrap {
    width: 14px; height: 80px;
    background: var(--border);
    border-radius: 7px;
    overflow: hidden;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  .motor-bar {
    width: 100%;
    position: absolute;
    bottom: 50%;
    border-radius: 4px;
    transition: height 0.1s, background 0.1s;
  }
  .motor-val {
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--accent);
    min-width: 36px;
    text-align: center;
  }
</style>
</head>
<body>

<header>
  <h1>🤖 Robot Teleop</h1>
  <span id="state-label">IDLE</span>
  <div id="status-dot" class="idle"></div>
</header>

<!-- Speed -->
<div class="speed-row">
  <label>Speed</label>
  <input type="range" id="speed-slider" min="10" max="100" value="40" step="5">
  <span id="speed-val">40%</span>
</div>

<!-- Motor bars -->
<div class="motor-row">
  <div class="motor-col">
    <span>L</span>
    <div class="motor-bar-wrap">
      <div class="motor-bar" id="bar-left" style="height:0%;background:var(--green)"></div>
    </div>
    <span class="motor-val" id="val-left">0%</span>
  </div>
  <div class="motor-col">
    <span>R</span>
    <div class="motor-bar-wrap">
      <div class="motor-bar" id="bar-right" style="height:0%;background:var(--green)"></div>
    </div>
    <span class="motor-val" id="val-right">0%</span>
  </div>
</div>

<!-- D-pad -->
<div class="dpad-wrap">
  <div class="dpad">
    <!-- Row 1 -->
    <button class="btn arc" id="btn-arc-left"  data-cmd="arc_left"  >↰</button>
    <button class="btn"     id="btn-forward"   data-cmd="forward"   >▲</button>
    <button class="btn arc" id="btn-arc-right" data-cmd="arc_right" >↱</button>
    <!-- Row 2 -->
    <button class="btn"     id="btn-left"      data-cmd="left"      >◄</button>
    <button class="btn stop"id="btn-stop"      data-cmd="stop"      >■</button>
    <button class="btn"     id="btn-right"     data-cmd="right"     >►</button>
    <!-- Row 3 -->
    <div class="empty"></div>
    <button class="btn"     id="btn-backward"  data-cmd="backward"  >▼</button>
    <div class="empty"></div>
  </div>
</div>

<script>
  const slider   = document.getElementById('speed-slider');
  const speedVal = document.getElementById('speed-val');
  const stateLbl = document.getElementById('state-label');
  const dot      = document.getElementById('status-dot');
  const barL     = document.getElementById('bar-left');
  const barR     = document.getElementById('bar-right');
  const valL     = document.getElementById('val-left');
  const valR     = document.getElementById('val-right');

  let activeCmd  = null;
  let sendTimer  = null;
  let speed      = 0.40;

  // ── Speed slider ──
  slider.addEventListener('input', () => {
    speed = parseInt(slider.value) / 100;
    speedVal.textContent = slider.value + '%';
    if (activeCmd && activeCmd !== 'stop') sendCmd(activeCmd);
  });

  // ── Update HUD ──
  function updateHUD(cmd, left, right) {
    stateLbl.textContent = cmd.toUpperCase().replace('_', ' ');
    dot.className = cmd === 'stop' || cmd === 'idle' ? 'idle' : 'moving';

    const pctL = Math.round(Math.abs(left) * 100);
    const pctR = Math.round(Math.abs(right) * 100);
    const colL = left >= 0 ? 'var(--green)' : 'var(--red)';
    const colR = right >= 0 ? 'var(--green)' : 'var(--red)';

    barL.style.height    = pctL + '%';
    barR.style.height    = pctR + '%';
    barL.style.background = colL;
    barR.style.background = colR;
    valL.textContent = (left >= 0 ? '+' : '') + (left * 100).toFixed(0) + '%';
    valR.textContent = (right >= 0 ? '+' : '') + (right * 100).toFixed(0) + '%';
  }

  // ── Send command to Pi ──
  async function sendCmd(cmd) {
    try {
      const res = await fetch('/cmd', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cmd, speed})
      });
      const data = await res.json();
      updateHUD(cmd, data.left, data.right);
    } catch(e) {
      dot.className = 'stopped';
      stateLbl.textContent = 'DISCONNECTED';
    }
  }

  // ── Continuous send while held ──
  function startHold(cmd) {
    activeCmd = cmd;
    sendCmd(cmd);
    sendTimer = setInterval(() => sendCmd(cmd), 80);
  }

  function stopHold() {
    clearInterval(sendTimer);
    sendTimer = null;
    activeCmd = null;
    sendCmd('stop');
  }

  // ── Button bindings ──
  document.querySelectorAll('.btn[data-cmd]').forEach(btn => {
    const cmd = btn.dataset.cmd;

    // Touch events (mobile)
    btn.addEventListener('touchstart', (e) => {
      e.preventDefault();
      btn.classList.add('pressed');
      if (cmd === 'stop') { sendCmd('stop'); }
      else { startHold(cmd); }
    }, {passive: false});

    btn.addEventListener('touchend', (e) => {
      e.preventDefault();
      btn.classList.remove('pressed');
      if (cmd !== 'stop') stopHold();
    }, {passive: false});

    // Mouse events (desktop fallback)
    btn.addEventListener('mousedown', () => {
      btn.classList.add('pressed');
      if (cmd === 'stop') sendCmd('stop');
      else startHold(cmd);
    });
    btn.addEventListener('mouseup', () => {
      btn.classList.remove('pressed');
      if (cmd !== 'stop') stopHold();
    });
    btn.addEventListener('mouseleave', () => {
      if (btn.classList.contains('pressed')) {
        btn.classList.remove('pressed');
        if (cmd !== 'stop') stopHold();
      }
    });
  });

  // ── Keyboard fallback (desktop) ──
  const keyMap = {
    'ArrowUp':'forward','ArrowDown':'backward',
    'ArrowLeft':'left','ArrowRight':'right',
    'w':'forward','s':'backward','a':'left','d':'right',
    'q':'arc_left','e':'arc_right',' ':'stop'
  };
  const held = new Set();
  document.addEventListener('keydown', e => {
    if (held.has(e.key)) return;
    held.add(e.key);
    const cmd = keyMap[e.key];
    if (!cmd) return;
    const btn = document.querySelector(`[data-cmd="${cmd}"]`);
    if (btn) btn.classList.add('pressed');
    if (cmd === 'stop') sendCmd('stop');
    else startHold(cmd);
  });
  document.addEventListener('keyup', e => {
    held.delete(e.key);
    const cmd = keyMap[e.key];
    if (!cmd || cmd === 'stop') return;
    const btn = document.querySelector(`[data-cmd="${cmd}"]`);
    if (btn) btn.classList.remove('pressed');
    stopHold();
  });
</script>
</body>
</html>
"""

# ── Flask Routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/cmd", methods=["POST"])
def command():
    global _last_cmd_ts
    _last_cmd_ts = time.time()

    data  = request.get_json(force=True, silent=True) or {}
    cmd   = data.get("cmd", "stop")
    spd   = float(data.get("speed", base_speed))
    spd   = max(0.0, min(1.0, spd))

    left  = 0.0
    right = 0.0

    if cmd == "forward":
        left = right = spd
    elif cmd == "backward":
        left = right = -spd
    elif cmd == "left":          # spin counter-clockwise in place
        left  = -spd
        right =  spd
    elif cmd == "right":         # spin clockwise in place
        left  =  spd
        right = -spd
    elif cmd == "arc_left":      # gentle left curve
        left  =  spd * 0.35
        right =  spd
    elif cmd == "arc_right":     # gentle right curve
        left  =  spd
        right =  spd * 0.35
    elif cmd == "stop":
        left = right = 0.0

    if driver:
        if cmd == "stop":
            driver.stop()
        else:
            driver.set_motors(left, right)

    current_cmd.update({"left": left, "right": right, "state": cmd})
    log.info("CMD %-12s  L=%+.2f  R=%+.2f  speed=%.0f%%", cmd, left, right, spd * 100)
    return jsonify({"ok": True, "cmd": cmd, "left": left, "right": right})


# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    global driver, base_speed

    parser = argparse.ArgumentParser(description="Mobile Web Teleop Server")
    parser.add_argument("--port",  type=int,   default=5000,  help="HTTP port (default: 5000)")
    parser.add_argument("--host",  type=str,   default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--speed", type=float, default=0.40,  help="Default speed 0-1 (default: 0.40)")
    args = parser.parse_args()

    base_speed = args.speed

    if MOTORS_AVAILABLE:
        driver = MotorDriver()
        log.info("MotorDriver initialized ✓")
    else:
        log.warning("Running WITHOUT motor hardware (simulation mode)")

    # Start watchdog thread
    threading.Thread(target=_watchdog, daemon=True, name="MotorWatchdog").start()

    # Print connection instructions
    import socket
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "YOUR_PI_IP"

    print("\n" + "═" * 52)
    print("   🤖  ROBOT MOBILE TELEOP SERVER")
    print("═" * 52)
    print(f"   Open on your phone:")
    print(f"   → http://{local_ip}:{args.port}")
    print(f"   → http://{hostname}.local:{args.port}")
    print(f"   (Phone must be on same WiFi as Pi)")
    print("═" * 52 + "\n")

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
