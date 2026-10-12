"""
=============================================================================
 ROS Attendance Bot — Mobile Web Teleoperation Server  (v2 — Polished)
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
import socket

from flask import Flask, request, jsonify, render_template_string

try:
    from motor_controller import MotorDriver
    MOTORS_AVAILABLE = True
except Exception as e:
    MOTORS_AVAILABLE = False
    print(f"[WARNING] MotorDriver not available: {e} — simulation mode")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [TELEOP] %(message)s")
log = logging.getLogger("teleop_server")

app        = Flask(__name__)
driver     = None
base_speed = 0.40

# Shared state
current_cmd  = {"left": 0.0, "right": 0.0, "state": "stop"}
_last_cmd_ts = time.time()
WATCHDOG_SEC = 0.6   # stop if no heartbeat for this long


def _watchdog():
    while True:
        time.sleep(0.1)
        if time.time() - _last_cmd_ts > WATCHDOG_SEC:
            if driver and current_cmd["state"] != "stop":
                driver.stop()
                current_cmd.update({"left": 0.0, "right": 0.0, "state": "stop"})


# ── HTML (inlined, served to phone) ──────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Robot Teleop</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#070B10;
  --surface:#0E1420;
  --card:#131928;
  --border:#1E2D45;
  --accent:#3B82F6;
  --accent-glow:rgba(59,130,246,0.35);
  --green:#22C55E;
  --green-glow:rgba(34,197,94,0.3);
  --red:#EF4444;
  --red-glow:rgba(239,68,68,0.35);
  --yellow:#F59E0B;
  --text:#F1F5F9;
  --muted:#64748B;
  --btn-size:clamp(72px,18vw,96px);
  --gap:clamp(8px,2vw,14px);
}
html,body{
  height:100%;width:100%;
  background:var(--bg);
  color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Segoe UI',sans-serif;
  overflow:hidden;
  touch-action:none;
  -webkit-user-select:none;user-select:none;
}
body{display:flex;flex-direction:column;align-items:center;height:100dvh}

/* ── Topbar ── */
.topbar{
  width:100%;
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 20px 12px;
  background:linear-gradient(180deg,#0D1628 0%,transparent 100%);
}
.topbar-title{font-size:.9rem;font-weight:700;letter-spacing:.08em;color:var(--text);display:flex;align-items:center;gap:8px}
.topbar-title svg{width:20px;height:20px;fill:var(--accent)}
.conn-pill{
  display:flex;align-items:center;gap:6px;
  padding:4px 10px;border-radius:999px;
  background:var(--surface);border:1px solid var(--border);
  font-size:.7rem;font-weight:600;letter-spacing:.05em;color:var(--muted);
  transition:all .3s;
}
.conn-pill.connected{color:var(--green);border-color:rgba(34,197,94,.4);background:rgba(34,197,94,.08)}
.conn-pill .dot{width:7px;height:7px;border-radius:50%;background:currentColor}

/* ── State banner ── */
.state-banner{
  font-size:.7rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;
  color:var(--muted);margin-top:2px;transition:color .15s;
}

/* ── Speed control ── */
.speed-wrap{
  width:88%;max-width:380px;margin-top:10px;
  background:var(--surface);border:1px solid var(--border);
  border-radius:16px;padding:10px 18px;
  display:flex;align-items:center;gap:12px;
}
.speed-icon{font-size:.85rem;color:var(--muted)}
input[type=range]{
  flex:1;-webkit-appearance:none;appearance:none;
  height:4px;border-radius:2px;outline:none;
  background:linear-gradient(90deg,var(--accent) var(--pct,40%),var(--border) var(--pct,40%));
}
input[type=range]::-webkit-slider-thumb{
  -webkit-appearance:none;width:20px;height:20px;border-radius:50%;
  background:var(--accent);cursor:pointer;
  box-shadow:0 0 10px var(--accent-glow);
  transition:transform .1s;
}
input[type=range]:active::-webkit-slider-thumb{transform:scale(1.25)}
.speed-val{font-size:.85rem;font-weight:800;color:var(--accent);min-width:36px;text-align:right}

/* ── Motor bars ── */
.motor-row{
  display:flex;gap:20px;align-items:flex-end;margin-top:10px;
}
.motor-col{display:flex;flex-direction:column;align-items:center;gap:4px}
.motor-label{font-size:.6rem;letter-spacing:.1em;font-weight:700;color:var(--muted)}
.bar-track{
  width:10px;height:60px;background:var(--border);border-radius:5px;
  overflow:hidden;position:relative;display:flex;align-items:center;justify-content:center;
}
.bar-fill{
  position:absolute;bottom:50%;width:100%;border-radius:4px;
  background:var(--green);transition:height .08s,background .12s;height:0%;
}
.motor-pct{font-size:.62rem;font-weight:800;color:var(--accent);min-width:34px;text-align:center}

/* ── D-pad ── */
.dpad-area{
  flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  width:100%;padding-bottom:env(safe-area-inset-bottom,12px);
}
.dpad{
  display:grid;
  grid-template-columns:repeat(3,var(--btn-size));
  grid-template-rows:repeat(3,var(--btn-size));
  gap:var(--gap);
}
.btn{
  display:flex;align-items:center;justify-content:center;
  border-radius:20px;border:1.5px solid var(--border);
  background:var(--card);cursor:pointer;
  font-size:clamp(1.4rem,4vw,1.9rem);
  transition:background .1s,border-color .1s,box-shadow .1s,transform .08s;
  -webkit-tap-highlight-color:transparent;
  touch-action:none;
}
.btn:active,.btn.on{
  background:#0E2040;
  border-color:var(--accent);
  box-shadow:0 0 22px var(--accent-glow),inset 0 0 12px rgba(59,130,246,.15);
  transform:scale(.92);
}
.btn.arc{color:var(--yellow);border-color:#2a2200}
.btn.arc.on,.btn.arc:active{
  background:#1a1500;border-color:var(--yellow);
  box-shadow:0 0 22px rgba(245,158,11,.3);
}
.btn-stop{
  background:rgba(239,68,68,.08);
  border-color:rgba(239,68,68,.4);
  color:var(--red);
}
.btn-stop.on,.btn-stop:active{
  background:rgba(239,68,68,.18);border-color:var(--red);
  box-shadow:0 0 24px var(--red-glow);transform:scale(.92);
}
.empty{visibility:hidden}
</style>
</head>
<body>

<!-- Top bar -->
<div class="topbar">
  <div class="topbar-title">
    <svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 012 2 2 2 0 01-2 2 2 2 0 01-2-2 2 2 0 012-2m-1 5h2v1h3a1 1 0 011 1v9a1 1 0 01-1 1H8a1 1 0 01-1-1V9a1 1 0 011-1h3V7m-3 4v7h8v-7H8m1 1h2v2H9v-2m4 0h2v2h-2v-2z"/></svg>
    ROBOT TELEOP
  </div>
  <div class="conn-pill" id="conn">
    <span class="dot"></span><span id="conn-text">CONNECTING</span>
  </div>
</div>

<!-- State -->
<div class="state-banner" id="state-lbl">STOPPED</div>

<!-- Speed -->
<div class="speed-wrap">
  <span class="speed-icon">🐢</span>
  <input type="range" id="spd" min="10" max="100" value="40" step="5">
  <span class="speed-icon">🐇</span>
  <span class="speed-val" id="spd-val">40%</span>
</div>

<!-- Motor bars -->
<div class="motor-row">
  <div class="motor-col">
    <span class="motor-label">LEFT</span>
    <div class="bar-track"><div class="bar-fill" id="bar-l"></div></div>
    <span class="motor-pct" id="pct-l">0%</span>
  </div>
  <div class="motor-col">
    <span class="motor-label">RIGHT</span>
    <div class="bar-track"><div class="bar-fill" id="bar-r"></div></div>
    <span class="motor-pct" id="pct-r">0%</span>
  </div>
</div>

<!-- D-pad -->
<div class="dpad-area">
  <div class="dpad" id="dpad">
    <button class="btn arc"      id="b-arc_left"  >↰</button>
    <button class="btn"          id="b-forward"   >▲</button>
    <button class="btn arc"      id="b-arc_right" >↱</button>
    <button class="btn"          id="b-left"      >◄</button>
    <button class="btn btn-stop" id="b-stop"      >■</button>
    <button class="btn"          id="b-right"     >►</button>
    <div class="empty"></div>
    <button class="btn"          id="b-backward"  >▼</button>
    <div class="empty"></div>
  </div>
</div>

<script>
// ── Elements
const spdSlider = document.getElementById('spd');
const spdVal    = document.getElementById('spd-val');
const stateLbl  = document.getElementById('state-lbl');
const connEl    = document.getElementById('conn');
const connTxt   = document.getElementById('conn-text');
const barL      = document.getElementById('bar-l');
const barR      = document.getElementById('bar-r');
const pctL      = document.getElementById('pct-l');
const pctR      = document.getElementById('pct-r');

let speed    = 0.40;
let activeId = null;   // currently pressed button ID
let loopTick = null;   // single setInterval for command sending
let lastOk   = Date.now();

// ── Speed slider
spdSlider.addEventListener('input', () => {
  speed = spdSlider.value / 100;
  spdVal.textContent = spdSlider.value + '%';
  spdSlider.style.setProperty('--pct', spdSlider.value + '%');
  // re-send current command with new speed
  if (activeId && activeId !== 'stop') send(activeId);
});
spdSlider.style.setProperty('--pct', '40%');

// ── HUD update
const STATES = {
  forward:'▲ FORWARD', backward:'▼ BACKWARD', left:'◄ SPIN LEFT',
  right:'► SPIN RIGHT', arc_left:'↰ ARC LEFT', arc_right:'↱ ARC RIGHT',
  stop:'■ STOPPED'
};
function hud(cmd, l, r) {
  stateLbl.textContent = STATES[cmd] || cmd.toUpperCase();

  const al = Math.abs(l), ar = Math.abs(r);
  const cl = l >= 0 ? 'var(--green)' : 'var(--red)';
  const cr = r >= 0 ? 'var(--green)' : 'var(--red)';
  barL.style.height = (al * 100) + '%';
  barR.style.height = (ar * 100) + '%';
  barL.style.background = cl;
  barR.style.background = cr;
  pctL.textContent = (l >= 0 ? '+' : '') + Math.round(l * 100) + '%';
  pctR.textContent = (r >= 0 ? '+' : '') + Math.round(r * 100) + '%';
}

// ── Fire-and-forget send (never awaits — can't block next command)
function send(cmd) {
  const body = JSON.stringify({cmd, speed});
  // Use sendBeacon when stopping (guaranteed delivery on finger-lift)
  if (cmd === 'stop' && navigator.sendBeacon) {
    const blob = new Blob([body], {type:'application/json'});
    navigator.sendBeacon('/cmd', blob);
    hud('stop', 0, 0);
    return;
  }
  fetch('/cmd', {method:'POST', headers:{'Content-Type':'application/json'}, body})
    .then(r => r.json())
    .then(d => { lastOk = Date.now(); hud(cmd, d.left, d.right); connOk(); })
    .catch(() => connLost());
}

function connOk()   { connEl.className='conn-pill connected'; connTxt.textContent='CONNECTED'; }
function connLost() { connEl.className='conn-pill'; connTxt.textContent='LOST'; }

// ── Single command loop — sends every 90ms while a button is held
function startLoop(cmd) {
  stopLoop();   // always kill the old loop first
  activeId = cmd;
  send(cmd);
  loopTick = setInterval(() => send(cmd), 90);
}
function stopLoop() {
  if (loopTick) { clearInterval(loopTick); loopTick = null; }
  activeId = null;
}
function pressStop() {
  stopLoop();
  activeId = 'stop';
  send('stop');
  hud('stop', 0, 0);
}

// ── Mark button visual state
function setOn(id)  { document.getElementById('b-' + id)?.classList.add('on'); }
function setOff(id) { document.getElementById('b-' + id)?.classList.remove('on'); }

// ── Pointer Events (handles touch + mouse + stylus uniformly, no race conditions)
document.querySelectorAll('.btn').forEach(btn => {
  const cmd = btn.id.replace('b-', '');

  btn.addEventListener('pointerdown', e => {
    e.preventDefault();
    btn.setPointerCapture(e.pointerId); // lock events to this element
    if (activeId && activeId !== cmd) setOff(activeId);
    setOn(cmd);
    if (cmd === 'stop') { pressStop(); }
    else                { startLoop(cmd); }
  });

  btn.addEventListener('pointerup', e => {
    e.preventDefault();
    setOff(cmd);
    if (cmd !== 'stop') pressStop();
  });

  btn.addEventListener('pointercancel', e => {
    e.preventDefault();
    setOff(cmd);
    pressStop();
  });
});

// ── Keyboard (desktop / SSH testing)
const KEY = {
  ArrowUp:'forward', ArrowDown:'backward', ArrowLeft:'left', ArrowRight:'right',
  w:'forward', s:'backward', a:'left', d:'right',
  q:'arc_left', e:'arc_right', ' ':'stop'
};
const held = new Set();
addEventListener('keydown', ev => {
  const cmd = KEY[ev.key];
  if (!cmd || held.has(ev.key)) return;
  held.add(ev.key);
  if (cmd === 'stop') pressStop();
  else { setOn(cmd); startLoop(cmd); }
});
addEventListener('keyup', ev => {
  const cmd = KEY[ev.key];
  if (!cmd) return;
  held.delete(ev.key);
  setOff(cmd);
  if (cmd !== 'stop') pressStop();
});

// ── Connection watchdog on client side
setInterval(() => {
  if (Date.now() - lastOk > 3000) connLost();
}, 1000);

// ── Initial ping
fetch('/cmd', {method:'POST', headers:{'Content-Type':'application/json'},
  body:JSON.stringify({cmd:'stop', speed})})
  .then(() => connOk()).catch(() => connLost());
</script>
</body>
</html>"""


# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/cmd", methods=["POST"])
def command():
    global _last_cmd_ts
    _last_cmd_ts = time.time()

    data = request.get_json(force=True, silent=True) or {}
    cmd  = data.get("cmd", "stop")
    spd  = max(0.0, min(1.0, float(data.get("speed", base_speed))))

    left = right = 0.0
    if   cmd == "forward"   : left =  spd; right =  spd
    elif cmd == "backward"  : left = -spd; right = -spd
    elif cmd == "left"      : left = -spd; right =  spd
    elif cmd == "right"     : left =  spd; right = -spd
    elif cmd == "arc_left"  : left =  spd * 0.3; right = spd
    elif cmd == "arc_right" : left =  spd; right = spd * 0.3

    if driver:
        driver.stop() if cmd == "stop" else driver.set_motors(left, right)

    current_cmd.update({"left": left, "right": right, "state": cmd})
    log.info("%-12s  L=%+.2f  R=%+.2f  spd=%.0f%%", cmd, left, right, spd * 100)
    return jsonify({"ok": True, "cmd": cmd, "left": left, "right": right})


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    global driver, base_speed

    parser = argparse.ArgumentParser(description="Mobile Web Teleop Server v2")
    parser.add_argument("--port",  type=int,   default=5000)
    parser.add_argument("--host",  type=str,   default="0.0.0.0")
    parser.add_argument("--speed", type=float, default=0.40)
    args = parser.parse_args()
    base_speed = args.speed

    if MOTORS_AVAILABLE:
        driver = MotorDriver()
        log.info("MotorDriver initialized ✓")
    else:
        log.warning("Simulation mode — no GPIO hardware")

    threading.Thread(target=_watchdog, daemon=True, name="Watchdog").start()

    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "YOUR_PI_IP"

    print("\n" + "═" * 52)
    print("   🤖  ROBOT MOBILE TELEOP  (v2)")
    print("═" * 52)
    print(f"   http://{ip}:{args.port}")
    print(f"   http://{socket.gethostname()}.local:{args.port}")
    print("   (Phone must be on same WiFi as Pi)")
    print("═" * 52 + "\n")

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
