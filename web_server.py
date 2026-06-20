"""Local web server for the measurement console."""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlparse

import numpy as np

from equation_discovery import fit_pendulum_equation


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


class MeasurementWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/discover", "/api/discover_neural"):
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20_000_000:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = neural_payload(payload) if path == "/api/discover_neural" else analyze_payload(payload)
            self._json_response(200, result)
        except Exception as exc:
            self._json_response(400, {"error": str(exc)})

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


def neural_payload(payload: dict) -> dict:
    """Run the local Neural ODE + GP symbolic regression pipeline."""
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) < 60:
        raise ValueError("not enough rows for Neural ODE discovery (need 60+)")

    t = np.array([float(r["time"]) for r in rows], dtype=float)
    series = payload.get("series", "measured")
    if series == "y":
        values = [r.get("measuredY", r.get("y")) for r in rows]
    else:
        values = [r.get("measured", r.get("primary")) for r in rows]
    theta = np.array([float(v) for v in values], dtype=float)
    if np.any(~np.isfinite(t)) or np.any(~np.isfinite(theta)):
        raise ValueError("time/series contains non-finite values")
    if np.any(np.diff(t) <= 0):
        order = np.argsort(t)
        t, theta = t[order], theta[order]

    try:
        from discover_pipeline import discover_from_series
    except Exception as exc:
        raise RuntimeError(f"Neural ODE deps unavailable. Install requirements-ml.txt: {exc}")

    frac = float(payload.get("frac", 0.5))
    mode = payload.get("mode", "pendulum")
    return discover_from_series(t, theta, frac=frac, mode=mode)


def serve(host: str, port: int):
    server = ThreadingHTTPServer((host, port), MeasurementWebHandler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print("=" * 72)
    print("Kinematic Measurement Console")
    print("=" * 72)
    print(f"UI   : {url}")
    print("Stop : Ctrl+C")
    print("=" * 72)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def parse_args():
    parser = argparse.ArgumentParser(description="Local measurement web server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8843)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    serve(args.host, args.port)
