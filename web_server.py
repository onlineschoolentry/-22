"""Web server for the measurement console."""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import sys
import threading
import time
from urllib.parse import urlparse

import numpy as np

from equation_discovery import fit_pendulum_equation


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


def get_lan_ip() -> str:
    """Best-effort LAN IP (no external deps; works on cloud hosts too)."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

PHONE_PAGE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phone Camera</title>
  <style>
    body { margin: 0; background: #0b0c0d; color: #e7edf3; font-family: Arial, sans-serif; }
    main { max-width: 720px; margin: auto; padding: 18px; }
    video { width: 100%; background: #000; border: 1px solid #30363d; }
    button { width: 100%; padding: 14px; margin: 12px 0; font-size: 17px; }
    .muted { color: #9aa4af; line-height: 1.45; }
    #status { font-family: Consolas, monospace; }
  </style>
</head>
<body>
<main>
  <h2>Phone Camera Uplink</h2>
  <p class="muted">PC 화면에서 <b>Phone Camera</b>를 누른 뒤, 이 페이지에서 Start를 누르세요.</p>
  <button id="start">Start Camera</button>
  <p id="status">IDLE</p>
  <video id="video" autoplay playsinline muted></video>
  <canvas id="canvas" width="640" height="480" hidden></canvas>
</main>
<script>
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const statusEl = document.getElementById("status");
let running = false;

async function start() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    });
    video.srcObject = stream;
    await video.play();
    running = true;
    statusEl.textContent = "STREAMING";
    sendLoop();
  } catch (err) {
    statusEl.textContent = "CAMERA ERROR: " + err.message;
  }
}

function sendLoop() {
  if (!running) return;
  const ctx = canvas.getContext("2d");
  const w = video.videoWidth || 640;
  const h = video.videoHeight || 480;
  canvas.width = w;
  canvas.height = h;
  ctx.drawImage(video, 0, 0, w, h);
  canvas.toBlob(async (blob) => {
    if (blob) {
      try {
        await fetch("/frame", { method: "POST", body: blob, headers: { "Content-Type": "image/jpeg" } });
      } catch (err) {
        statusEl.textContent = "SEND ERROR";
      }
    }
    setTimeout(sendLoop, 60);
  }, "image/jpeg", 0.72);
}

document.getElementById("start").addEventListener("click", start);
</script>
</body>
</html>
"""


class FrameStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.payload: bytes | None = None
        self.last_update = 0.0

    def set(self, payload: bytes):
        with self._lock:
            self.payload = payload
            self.last_update = time.time()

    def get(self) -> tuple[bytes | None, float]:
        with self._lock:
            return self.payload, self.last_update


FRAME_STORE = FrameStore()


class MeasurementWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/phone":
            self._html_response(PHONE_PAGE)
            return
        if path == "/api/frame.jpg":
            self._frame_response()
            return
        if path == "/api/phone-status":
            _, ts = FRAME_STORE.get()
            self._json_response(200, {"age": time.time() - ts if ts else None, "has_frame": bool(ts)})
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/frame":
            self._receive_frame()
            return
        if path != "/api/discover":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20_000_000:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = analyze_payload(payload)
            self._json_response(200, result)
        except Exception as exc:
            self._json_response(400, {"error": str(exc)})

    def _receive_frame(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 8_000_000:
            self.send_error(400)
            return
        FRAME_STORE.set(self.rfile.read(length))
        self.send_response(204)
        self.end_headers()

    def _frame_response(self):
        payload, _ = FRAME_STORE.get()
        if not payload:
            self.send_error(404, "no phone frame")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _html_response(self, body: str):
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _json_response(self, code: int, body: dict):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        sys.stdout.write("[WEB] " + (fmt % args) + "\n")


def analyze_payload(payload: dict) -> dict:
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) < 30:
        raise ValueError("not enough rows for equation discovery")

    t = np.array([float(row["time"]) for row in rows], dtype=float)
    theta = np.array([float(row["measured"]) for row in rows], dtype=float)
    if np.any(~np.isfinite(t)) or np.any(~np.isfinite(theta)):
        raise ValueError("time/theta contains non-finite values")
    if np.any(np.diff(t) <= 0):
        order = np.argsort(t)
        t = t[order]
        theta = theta[order]

    lambda_threshold = float(payload.get("lambda_threshold", 0.3))
    edge_drop = min(12, max(0, len(t) // 20))
    result, smooth = fit_pendulum_equation(
        t,
        theta,
        lambda_threshold=lambda_threshold,
        edge_drop=edge_drop,
    )

    return {
        "equation": result.equation(),
        "coefficients": [
            {"name": name, "value": float(value), "active": bool(active)}
            for name, value, active in zip(result.feature_names, result.coefficients, result.active)
        ],
        "lambda_threshold": float(result.lambda_threshold),
        "train_rmse": float(result.train_rmse),
        "test_rmse": float(result.test_rmse),
        "iterations": int(result.iterations),
        "sigma_meas": float(smooth.sigma_meas),
        "q_jerk": float(smooth.q_jerk),
    }


def serve(host: str, port: int, use_https: bool):
    server = ThreadingHTTPServer((host, port), MeasurementWebHandler)
    lan_ip = get_lan_ip()
    scheme = "http"

    if use_https:
        # Lazy import: only local/HTTPS runs need cv2+cryptography. Cloud hosts
        # (Render) run --http behind their own TLS, so they never import these.
        from phone_camera import create_self_signed_cert

        cert_path, key_path = create_self_signed_cert(lan_ip)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"

    url = f"{scheme}://{lan_ip}:{server.server_port}/"
    localhost = f"{scheme}://127.0.0.1:{server.server_port}/"
    phone = f"{scheme}://{lan_ip}:{server.server_port}/phone"
    print("=" * 72)
    print("Kinematic Measurement Console")
    print("=" * 72)
    print(f"PC    : {localhost}")
    print(f"LAN   : {url}")
    print(f"Phone : {phone}")
    if use_https:
        print("If the phone shows a certificate warning, open details and continue.")
    print("Stop  : Ctrl+C")
    print("=" * 72)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def parse_args():
    parser = argparse.ArgumentParser(description="Measurement web server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8843)
    parser.add_argument("--http", action="store_true", help="Use HTTP instead of HTTPS")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    serve(args.host, args.port, use_https=not args.http)
