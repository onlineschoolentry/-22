"""
OpenCV pendulum tracker (proposal pipeline stage 1).

Tracks a colored marker in a pendulum video with sub-pixel HSV color tracking,
calibrates pixel->angle from a clicked pivot, and writes theta(t) to a CSV that
feeds the Neural ODE + symbolic-regression discovery (discover_pipeline.py /
run_demo.py).

Usage:
  python cv_tracker.py --video pendulum.mp4 --out theta.csv
    -> a window opens: click the PIVOT, then click the BOB at rest.
       The bob click also samples the marker color. Tracking then runs.

Then:
  python discover_pipeline.py --csv theta.csv
"""

from __future__ import annotations

import argparse
import csv

import cv2
import numpy as np


def _sample_hsv(frame, px, py, half=10):
    """Median HSV around a clicked pixel -> tight color band (handles hue wrap)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    patch = hsv[max(0, py - half):min(h, py + half),
                max(0, px - half):min(w, px + half)].reshape(-1, 3)
    hm, sm, vm = (int(np.median(patch[:, i])) for i in range(3))
    h_tol, s_lo, v_lo = 14, max(40, sm - 90), max(35, vm - 130)
    lo, hi = np.array([hm - h_tol, s_lo, v_lo]), np.array([hm + h_tol, 255, 255])
    lo2 = hi2 = None
    if lo[0] < 0:
        lo2, hi2 = np.array([180 + lo[0], s_lo, v_lo]), np.array([180, 255, 255])
        lo[0] = 0
    elif hi[0] > 180:
        lo2, hi2 = np.array([0, s_lo, v_lo]), np.array([hi[0] - 180, 255, 255])
        hi[0] = 180
    return lo, hi, lo2, hi2


def _detect(frame, lo, hi, lo2, hi2, kernel):
    """Largest color blob -> sub-pixel centroid (intensity-weighted)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lo, hi)
    if lo2 is not None:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lo2, hi2))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 60:
        return None
    m = cv2.moments(c)
    if m["m00"] == 0:
        return None
    cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
    # sub-pixel refine: intensity-weighted centroid inside a small ROI
    h, w = mask.shape
    x1, x2 = max(0, int(cx) - 25), min(w, int(cx) + 25)
    y1, y2 = max(0, int(cy) - 25), min(h, int(cy) + 25)
    roi = mask[y1:y2, x1:x2].astype(np.float32)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
    wgt = gray * roi
    tot = wgt.sum()
    if tot > 0:
        yy, xx = np.mgrid[0:roi.shape[0], 0:roi.shape[1]]
        cx = (xx * wgt).sum() / tot + x1
        cy = (yy * wgt).sum() / tot + y1
    return cx, cy


def _wrap_pi(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default="theta.csv")
    ap.add_argument("--fps", type=float, default=None, help="override video fps")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")
    fps = args.fps or cap.get(cv2.CAP_PROP_FPS) or 30.0
    ok, frame0 = cap.read()
    if not ok:
        raise SystemExit("empty video")

    # --- calibration: click pivot, then bob (bob click also samples color) ---
    clicks = []
    disp = frame0.copy()

    def on_mouse(ev, x, y, flags, param):
        if ev == cv2.EVENT_LBUTTONDOWN and len(clicks) < 2:
            clicks.append((x, y))
            cv2.drawMarker(disp, (x, y), (0, 255, 255), cv2.MARKER_CROSS, 18, 2)

    cv2.namedWindow("calibrate")
    cv2.setMouseCallback("calibrate", on_mouse)
    print("Click PIVOT, then BOB at rest. (q to abort)")
    while len(clicks) < 2:
        cv2.imshow("calibrate", disp)
        if cv2.waitKey(20) & 0xFF == ord("q"):
            cv2.destroyAllWindows()
            return
    pivot, bob = clicks
    lo, hi, lo2, hi2 = _sample_hsv(frame0, bob[0], bob[1])
    rest_angle = np.arctan2(bob[0] - pivot[0], bob[1] - pivot[1])
    cv2.destroyWindow("calibrate")

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    rows = []
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        det = _detect(frame, lo, hi, lo2, hi2, kernel)
        if det is not None:
            dx, dy = det[0] - pivot[0], det[1] - pivot[1]
            theta = _wrap_pi(np.arctan2(dx, dy) - rest_angle)
            rows.append((fi / fps, theta))
            cv2.circle(frame, (int(det[0]), int(det[1])), 10, (0, 255, 0), 2)
            cv2.line(frame, pivot, (int(det[0]), int(det[1])), (200, 200, 200), 1)
            cv2.putText(frame, f"theta={np.degrees(theta):.1f} deg", (20, 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("tracking (q to stop)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        fi += 1
    cap.release()
    cv2.destroyAllWindows()

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "primary_measured"])
        for t, th in rows:
            w.writerow([f"{t:.5f}", f"{th:.6f}"])
    print(f"OpenCV tracking done: {len(rows)} frames -> {args.out}")
    print(f"Next: python discover_pipeline.py --csv {args.out}")


if __name__ == "__main__":
    main()
