"""Local HTTP dashboard and JSON telemetry endpoint."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Type

from .monitor import TelemetryMonitor

_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Embedded Sensor Monitor</title><style>
:root{font:16px system-ui;color:#172033;background:#f3f6fa}body{max-width:1100px;margin:2rem auto;padding:0 1rem}
h1{margin-bottom:.2rem}.muted{color:#64748b}.cards{display:flex;gap:1rem;flex-wrap:wrap}.card,section{background:white;border:1px solid #dce3ec;border-radius:12px;padding:1rem;margin:1rem 0;box-shadow:0 2px 8px #1720330a}
.card{min-width:190px;flex:1}.value{font-size:1.8rem;font-weight:650}.alarm{color:#b42318}.online{color:#16794b}canvas{width:100%;height:260px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:.5rem;border-bottom:1px solid #e4e9f0}
</style></head><body><h1>Embedded Sensor Monitor</h1><div class="muted">Local ESP32 telemetry simulation · refreshes twice per second</div>
<div class="cards"><div class="card"><div>Connection</div><div id="status" class="value">waiting</div></div>
<div class="card"><div>Temperature</div><div id="temperature" class="value">—</div></div>
<div class="card"><div>Vibration</div><div id="vibration" class="value">—</div></div>
<div class="card"><div>Packets / errors</div><div id="packets" class="value">0 / 0</div></div></div>
<section><h2>Recent telemetry</h2><canvas id="chart" width="1000" height="260"></canvas></section>
<section><h2>Threshold events</h2><table><thead><tr><th>Sequence</th><th>Sensor</th><th>Reading</th></tr></thead><tbody id="alarms"></tbody></table></section>
<script>
async function refresh(){try{const r=await fetch('/api/live',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();
const s=d.latest;const status=document.querySelector('#status');status.textContent=d.status;status.className='value '+d.status;
if(s){document.querySelector('#temperature').textContent=s.temperature_c.toFixed(2)+' °C';document.querySelector('#vibration').textContent=s.vibration_g.toFixed(3)+' g';}
document.querySelector('#packets').textContent=d.received_packets+' / '+(d.errors.invalid_frames+d.errors.missing_packets);
document.querySelector('#alarms').innerHTML=d.alarms.slice(-8).reverse().map(a=>`<tr><td>${a.sequence}</td><td>${a.kind}</td><td>${Number(a.value).toFixed(3)}</td></tr>`).join('')||'<tr><td colspan="3">No threshold events</td></tr>';
const c=document.querySelector('#chart'),x=c.getContext('2d'),w=c.width,h=c.height;x.clearRect(0,0,w,h);x.font='14px system-ui';
function line(key,color,min,max,label){x.strokeStyle=color;x.lineWidth=2;x.beginPath();d.history.forEach((p,i)=>{const px=30+i*(w-60)/Math.max(1,d.history.length-1),py=h-30-(p[key]-min)/(max-min)*(h-60);i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.fillStyle=color;x.fillText(label,36,20+(color==='#1769aa'?0:18));}
if(d.history.length){line('temperature_c','#1769aa',15,75,'Temperature °C');line('vibration_g','#d04a35',0,1,'Vibration g');}
}catch(e){document.querySelector('#status').textContent='disconnected';document.querySelector('#status').className='value alarm';}}
refresh();setInterval(refresh,500);
</script></body></html>"""


def make_handler(monitor: TelemetryMonitor) -> Type[BaseHTTPRequestHandler]:
    """Bind an HTTP handler to a monitor without exposing mutable internals."""
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/":
                body = _HTML.encode("utf-8")
                content_type = "text/html; charset=utf-8"
            elif self.path == "/api/live":
                body = json.dumps(monitor.snapshot(), separators=(",", ":")).encode("utf-8")
                content_type = "application/json; charset=utf-8"
            elif self.path == "/api/healthz":
                body = b'{"ok":true}'
                content_type = "application/json; charset=utf-8"
            else:
                self.send_error(404, "Not found")
                return

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # A browser tab may close during a refresh; the next poll is independent.
                return

        def log_message(self, format: str, *args: object) -> None:
            return

    return DashboardHandler


def serve_dashboard(monitor: TelemetryMonitor, host: str = "127.0.0.1",
                    port: int = 8765) -> ThreadingHTTPServer:
    """Create the dashboard server; loopback is the safe default binding."""
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    return ThreadingHTTPServer((host, port), make_handler(monitor))
