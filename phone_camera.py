"""
Phone camera receiver for PhysicsLens.

The PC serves a small browser page. A phone scans the QR code, opens the page,
and posts JPEG frames back to this process. The class mimics enough of
cv2.VideoCapture for the main app.
"""

import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
from urllib.parse import urlparse

import cv2
import numpy as np
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


PHONE_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PhysicsLens Phone Camera</title>
  <style>
    body { margin: 0; background: #111; color: #eee; font-family: sans-serif; }
    main { padding: 18px; max-width: 720px; margin: auto; }
    video, canvas { width: 100%; border-radius: 8px; background: #000; }
    button { font-size: 18px; padding: 12px 16px; margin: 12px 0; }
    .muted { color: #aaa; font-size: 14px; line-height: 1.45; }
  </style>
</head>
<body>
<main>
  <h2>PhysicsLens Phone Camera</h2>
  <p class="muted">Tap Start to stream this phone camera to the PC.</p>
  <button id="start">Start camera</button>
  <p id="status">Waiting</p>
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
    statusEl.textContent = "Streaming to PC";
    sendLoop();
  } catch (err) {
    statusEl.textContent = "Camera permission failed: " + err;
  }
}

async function sendLoop() {
  if (!running) return;
  const ctx = canvas.getContext("2d");
  const w = video.videoWidth || 640;
  const h = video.videoHeight || 480;
  canvas.width = w;
  canvas.height = h;
  ctx.drawImage(video, 0, 0, w, h);
  canvas.toBlob(async blob => {
    if (!blob) {
      setTimeout(sendLoop, 100);
      return;
    }
    try {
      await fetch("/frame", { method: "POST", body: blob, headers: { "Content-Type": "image/jpeg" } });
    } catch (err) {
      statusEl.textContent = "Send failed. Check Wi-Fi/firewall.";
    }
    setTimeout(sendLoop, 70);
  }, "image/jpeg", 0.72);
}

document.getElementById("start").addEventListener("click", start);
</script>
</body>
</html>
"""


def get_lan_ip() -> str:
    """Best-effort LAN IP discovery without sending packets."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def create_self_signed_cert(host_ip: str) -> tuple[str, str]:
    """Create a short-lived local TLS certificate for the phone receiver."""
    cert_dir = Path(tempfile.gettempdir()) / "physicslens"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "phone_camera_cert.pem"
    key_path = cert_dir / "phone_camera_key.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "KR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PhysicsLens"),
            x509.NameAttribute(NameOID.COMMON_NAME, host_ip),
        ]
    )

    alt_names = [x509.DNSName("localhost")]
    try:
        alt_names.append(x509.IPAddress(ipaddress.ip_address(host_ip)))
    except ValueError:
        alt_names.append(x509.DNSName(host_ip))

    now = dt.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return str(cert_path), str(key_path)


class PhoneFrameStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.frame = None
        self.last_update = 0.0

    def set_jpeg(self, payload: bytes):
        arr = np.frombuffer(payload, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return
        with self._lock:
            self.frame = frame
            self.last_update = time.time()

    def read(self):
        with self._lock:
            if self.frame is None:
                return False, None
            return True, self.frame.copy()


def make_handler(store: PhoneFrameStore):
    class PhoneCameraHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path not in ("/", "/phone"):
                self.send_error(404)
                return
            body = PHONE_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if urlparse(self.path).path != "/frame":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8_000_000:
                self.send_error(400)
                return
            store.set_jpeg(self.rfile.read(length))
            self.send_response(204)
            self.end_headers()

        def log_message(self, fmt, *args):
            return

    return PhoneCameraHandler


class PhoneCameraCapture:
    """Small cv2.VideoCapture-compatible wrapper around the phone receiver."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        show_qr: bool = True,
        https: bool = True,
    ):
        self.host = host
        self.port = port
        self.show_qr = show_qr
        self.https = https
        self.store = PhoneFrameStore()
        self.lan_ip = get_lan_ip()
        self.server = ThreadingHTTPServer((self.host, self.port), make_handler(self.store))
        if self.https:
            cert_path, key_path = create_self_signed_cert(self.lan_ip)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        scheme = "https" if self.https else "http"
        self.url = f"{scheme}://{self.lan_ip}:{self.server.server_port}/phone"
        self._opened = True
        self._qr_window_open = False
        if self.show_qr:
            self.show_qr_window()

    def isOpened(self):
        return self._opened

    def get(self, prop_id):
        if prop_id == cv2.CAP_PROP_FPS:
            return 15
        return 0

    def set(self, prop_id, value):
        return True

    def read(self):
        ret, frame = self.store.read()
        if ret:
            if self._qr_window_open:
                cv2.destroyWindow("PhysicsLens Phone QR")
                self._qr_window_open = False
            return True, frame

        waiting = np.full((480, 640, 3), 24, dtype=np.uint8)
        cv2.putText(waiting, "Scan QR with phone", (38, 140), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 220, 255), 2, cv2.LINE_AA)
        cv2.putText(waiting, self.url, (38, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(waiting, "On Safari, accept certificate warning first", (38, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (180, 180, 180), 1, cv2.LINE_AA)
        cv2.putText(waiting, "Then tap Start camera", (38, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (180, 180, 180), 1, cv2.LINE_AA)
        return True, waiting

    def release(self):
        self._opened = False
        self.server.shutdown()
        self.server.server_close()

    def show_qr_window(self):
        qr_img = self.qr_image()
        cv2.imshow("PhysicsLens Phone QR", qr_img)
        self._qr_window_open = True
        print(f"[PHONE] Scan this URL on the phone: {self.url}")
        if self.https:
            print("[PHONE] Safari may show a certificate warning. Open Details and continue.")

    def qr_image(self):
        try:
            import qrcode

            qr = qrcode.QRCode(border=2, box_size=10)
            qr.add_data(self.url)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            img = np.full((360, 360, 3), 255, dtype=np.uint8)
            cv2.putText(img, "QR unavailable", (45, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            cv2.putText(img, "install qrcode", (55, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 1)

        canvas = np.full((560, 520, 3), 245, dtype=np.uint8)
        img = cv2.resize(img, (400, 400), interpolation=cv2.INTER_NEAREST)
        canvas[35:435, 60:460] = img
        cv2.putText(canvas, "PhysicsLens Phone Camera", (42, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 1, cv2.LINE_AA)
        cv2.putText(canvas, self.url, (24, 500), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
        cv2.putText(canvas, "If warned, open Details and continue.", (24, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 60), 1, cv2.LINE_AA)
        return canvas
