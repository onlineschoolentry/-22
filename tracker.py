"""
Computer Vision color-object tracker.
Detects a colored bob via HSV thresholding, extracts sub-pixel centroid,
and optionally converts pixel coordinates to pendulum angle in radians.
"""

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass
class TrackingResult:
    """Single frame tracking result."""

    detected: bool
    angle: float = 0.0
    pixel_x: float = 0.0
    pixel_y: float = 0.0
    contour_area: float = 0.0


class PendulumTracker:
    """
    Track a colored object in a real-time webcam feed.

    Workflow:
      1. Detect colored object centroid
      2. Optionally calibrate a pivot and compute pendulum angle
    """

    COLOR_PRESETS = {
        "orange": ((5, 120, 120), (25, 255, 255)),
        "green": ((35, 100, 100), (85, 255, 255)),
        "red": ((0, 120, 100), (10, 255, 255)),
        "blue": ((100, 120, 80), (130, 255, 255)),
        "yellow": ((20, 100, 100), (35, 255, 255)),
        "magenta": ((140, 80, 80), (170, 255, 255)),
        "pink": ((140, 60, 120), (172, 255, 255)),
    }

    def __init__(self, color: str = "orange"):
        self.color_name = color
        preset = self.COLOR_PRESETS.get(color, self.COLOR_PRESETS["orange"])
        self.hsv_lower = np.array(preset[0])
        self.hsv_upper = np.array(preset[1])
        # Optional second range for hue wraparound (red/magenta near 0/180).
        self.hsv_lower2 = None
        self.hsv_upper2 = None
        if self.hsv_lower[0] <= 10 and self.hsv_upper[0] <= 15:
            self.hsv_lower2 = np.array([170, self.hsv_lower[1], self.hsv_lower[2]])
            self.hsv_upper2 = np.array([180, self.hsv_upper[1], self.hsv_upper[2]])

        self.pivot = None
        self.v_left = None
        self.v_right = None
        self.px_per_m = None
        self.L_pixels = None

        self.min_contour_area = 200
        self.morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

        # Spatial lock: once a target is acquired, prefer the blob nearest the
        # last known position so detection does not hop to other same-color
        # objects. Released only after the target is lost for a while.
        self.last_position = None
        self.target_seed = None
        self.max_jump = 110          # px; keep lock tight so face/lips are not reacquired
        self.reacquire_after = 60    # frames lost before the lock is released
        self._lost_frames = 0
        self.color_center_h = None
        self.color_h_tol = 13
        self.color_s_lo = int(self.hsv_lower[1])
        self.color_v_lo = int(self.hsv_lower[2])

        self.calibration_mode = False
        self._calib_clicks = []

    def set_pivot(self, px: int, py: int):
        """Set the pivot point in pixel coordinates."""
        self.pivot = (px, py)

    def set_v_anchors(self, left: tuple, right: tuple):
        """Set two top anchors for a V-shaped pendulum support."""
        self.v_left = left
        self.v_right = right
        self.pivot = (
            int((left[0] + right[0]) / 2),
            int((left[1] + right[1]) / 2),
        )

    def set_string_length_pixels(self, L_px: float):
        """Set string length in pixels for pixel-to-angle conversion."""
        self.L_pixels = L_px

    def auto_calibrate(self, frame: np.ndarray) -> bool:
        """
        Auto-detect pivot assuming the bob hangs straight down at rest.
        """
        result = self._detect_bob(frame)
        if not result.detected:
            return False

        if self.L_pixels is None:
            self.L_pixels = frame.shape[0] * 0.5
        self.pivot = (int(result.pixel_x), int(result.pixel_y - self.L_pixels))
        return True

    def track(self, frame: np.ndarray) -> TrackingResult:
        """Track the pendulum bob in a single frame."""
        result = self._detect_bob(frame)
        if not result.detected or self.pivot is None:
            return result

        dx = result.pixel_x - self.pivot[0]
        dy = result.pixel_y - self.pivot[1]
        result.angle = np.arctan2(dx, dy)
        return result

    def _compute_mask(self, hsv: np.ndarray) -> np.ndarray:
        """Build a cleaned binary mask, including the optional wraparound range."""
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        if self.hsv_lower2 is not None:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, self.hsv_lower2, self.hsv_upper2))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.morph_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.morph_kernel)
        return mask

    def pick_color_at(self, frame: np.ndarray, px: int, py: int,
                      half: int = 12, h_tol: int = 13) -> tuple:
        """
        Sample the marker color at a clicked pixel and set the HSV range around it.

        Works for any color and handles hue wraparound, so the user is not limited
        to the fixed presets. Returns the sampled median (H, S, V).
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, w = hsv.shape[:2]
        x1, x2 = max(0, px - half), min(w, px + half + 1)
        y1, y2 = max(0, py - half), min(h, py + half + 1)
        patch = hsv[y1:y2, x1:x2].reshape(-1, 3)
        strong = patch[(patch[:, 1] >= 55) & (patch[:, 2] >= 35)]
        if len(strong) >= 8:
            patch = strong
        h_med = int(round(self._circular_hue_mean(patch[:, 0].astype(float))))
        s_med = int(np.median(patch[:, 1]))
        v_med = int(np.median(patch[:, 2]))

        s_lo = max(60, s_med - 85)
        v_lo = max(40, v_med - 130)
        lo_h, hi_h = h_med - h_tol, h_med + h_tol

        self.hsv_lower2 = None
        self.hsv_upper2 = None
        if lo_h < 0:
            self.hsv_lower = np.array([0, s_lo, v_lo])
            self.hsv_upper = np.array([hi_h, 255, 255])
            self.hsv_lower2 = np.array([180 + lo_h, s_lo, v_lo])
            self.hsv_upper2 = np.array([180, 255, 255])
        elif hi_h > 180:
            self.hsv_lower = np.array([lo_h, s_lo, v_lo])
            self.hsv_upper = np.array([180, 255, 255])
            self.hsv_lower2 = np.array([0, s_lo, v_lo])
            self.hsv_upper2 = np.array([hi_h - 180, 255, 255])
        else:
            self.hsv_lower = np.array([lo_h, s_lo, v_lo])
            self.hsv_upper = np.array([hi_h, 255, 255])

        # New target color: drop any existing lock so it re-acquires cleanly,
        # seeding the lock at the click so it grabs the clicked object first.
        self.color_name = "sampled"
        self.color_center_h = float(h_med)
        self.color_h_tol = h_tol
        self.color_s_lo = int(s_lo)
        self.color_v_lo = int(v_lo)
        self.last_position = (float(px), float(py))
        self.target_seed = (float(px), float(py))
        self._lost_frames = 0
        return h_med, s_med, v_med

    def _lose_target(self) -> TrackingResult:
        """Register a missed frame and release the lock after a grace period."""
        self._lost_frames += 1
        if self._lost_frames > self.reacquire_after:
            self.last_position = None
        return TrackingResult(detected=False)

    def _detect_bob(self, frame: np.ndarray) -> TrackingResult:
        """Detect the colored bob and return pixel coordinates."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = self._compute_mask(hsv)
        quality_map = self._quality_map(hsv)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Candidate centroids for every blob above the area threshold.
        candidates = []
        frame_h, frame_w = frame.shape[:2]
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_contour_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if w > frame_w * 0.45 or h > frame_h * 0.45:
                continue
            aspect = max(w, h) / max(min(w, h), 1)
            if aspect > 4.5:
                continue
            density = area / max(w * h, 1)
            if density < 0.12:
                continue
            m = cv2.moments(cnt)
            if m["m00"] == 0:
                continue
            local_mask = np.zeros((h, w), dtype=np.uint8)
            shifted = cnt - np.array([[[x, y]]])
            cv2.drawContours(local_mask, [shifted], -1, 255, -1)
            q_roi = quality_map[y:y + h, x:x + w]
            avg_q = float(cv2.mean(q_roi, mask=local_mask)[0]) / 1000.0
            aspect_score = 1.0 / aspect
            density_score = np.clip((density - 0.12) / 0.55, 0.0, 1.0)
            score = np.sqrt(area) * 4.2 + avg_q * 120.0 + density_score * 50.0 + aspect_score * 40.0
            cx = m["m10"] / m["m00"]
            cy = m["m01"] / m["m00"]
            if self.last_position is not None:
                lx, ly = self.last_position
                d = np.sqrt((cx - lx) ** 2 + (cy - ly) ** 2)
                score += max(0.0, 85.0 - d * 0.55)
            if self.target_seed is not None:
                sx, sy = self.target_seed
                d = np.sqrt((cx - sx) ** 2 + (cy - sy) ** 2)
                score += max(0.0, 140.0 - d * 0.7)
            candidates.append((cx, cy, area, score))

        if not candidates:
            return self._lose_target()

        cx, cy, area, _ = max(candidates, key=lambda c: c[3])

        cx_sub, cy_sub = self._subpixel_refine(frame, cx, cy, mask)
        self.last_position = (cx_sub, cy_sub)
        self._lost_frames = 0
        return TrackingResult(
            detected=True,
            pixel_x=cx_sub,
            pixel_y=cy_sub,
            contour_area=area,
        )

    def _quality_map(self, hsv: np.ndarray) -> np.ndarray:
        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)

        if self.color_center_h is not None:
            center = self.color_center_h
            h_tol = max(float(self.color_h_tol), 1.0)
            s_lo = float(self.color_s_lo)
            v_lo = float(self.color_v_lo)
            matched = self._compute_mask(hsv) > 0
            h_score = np.clip(1.0 - self._hue_distance(h, center) / h_tol, 0.0, 1.0)
        elif self.color_name == "red":
            d = np.minimum(h, 180.0 - h)
            matched = (d <= 14.0) & (s >= 85.0) & (v >= 55.0)
            h_score = np.clip(1.0 - d / 14.0, 0.0, 1.0)
            s_lo = 85.0
            v_lo = 55.0
        else:
            lo_h = float(self.hsv_lower[0])
            hi_h = float(self.hsv_upper[0])
            center = (lo_h + hi_h) / 2.0
            h_tol = max((hi_h - lo_h) / 2.0, 1.0)
            matched = self._compute_mask(hsv) > 0
            h_score = np.clip(1.0 - np.abs(h - center) / h_tol, 0.0, 1.0)
            s_lo = float(self.hsv_lower[1])
            v_lo = float(self.hsv_lower[2])

        s_score = np.clip((s - s_lo) / max(255.0 - s_lo, 1.0), 0.0, 1.0)
        v_score = np.clip((v - v_lo) / max(255.0 - v_lo, 1.0), 0.0, 1.0)
        quality = (0.55 * h_score + 0.27 * s_score + 0.18 * v_score) * 1000.0
        quality[~matched] = 0.0
        return quality.astype(np.uint16)

    @staticmethod
    def _hue_distance(a: np.ndarray, b: float) -> np.ndarray:
        d = np.abs(a - b)
        return np.minimum(d, 180.0 - d)

    @staticmethod
    def _circular_hue_mean(values: np.ndarray) -> float:
        if len(values) == 0:
            return 0.0
        angles = values * np.pi / 90.0
        x = float(np.cos(angles).mean())
        y = float(np.sin(angles).mean())
        angle = np.arctan2(y, x)
        if angle < 0:
            angle += np.pi * 2
        return float(angle * 90.0 / np.pi)

    def _subpixel_refine(
        self,
        frame: np.ndarray,
        cx: float,
        cy: float,
        mask: np.ndarray,
    ) -> Tuple[float, float]:
        """Refine centroid using weighted moments on masked grayscale."""
        h, w = frame.shape[:2]
        roi_size = 30
        x1 = max(0, int(cx) - roi_size)
        x2 = min(w, int(cx) + roi_size)
        y1 = max(0, int(cy) - roi_size)
        y2 = min(h, int(cy) + roi_size)

        roi_mask = mask[y1:y2, x1:x2].astype(np.float32)
        if roi_mask.sum() == 0:
            return cx, cy

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
        weighted = gray * roi_mask
        total = weighted.sum()
        if total == 0:
            return cx, cy

        yy, xx = np.mgrid[0:roi_mask.shape[0], 0:roi_mask.shape[1]]
        cx_ref = (xx * weighted).sum() / total + x1
        cy_ref = (yy * weighted).sum() / total + y1
        return cx_ref, cy_ref

    def draw_overlay(self, frame: np.ndarray, result: TrackingResult) -> np.ndarray:
        """Draw tracking visualization on the frame."""
        vis = frame.copy()

        if self.pivot is not None:
            if self.v_left is not None:
                cv2.drawMarker(vis, self.v_left, (0, 255, 255), cv2.MARKER_CROSS, 16, 2)
                cv2.putText(
                    vis,
                    "L",
                    (self.v_left[0] + 10, self.v_left[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 255),
                    1,
                )
            if self.v_right is not None:
                cv2.drawMarker(vis, self.v_right, (0, 255, 255), cv2.MARKER_CROSS, 16, 2)
                cv2.putText(
                    vis,
                    "R",
                    (self.v_right[0] + 10, self.v_right[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 255),
                    1,
                )
            cv2.drawMarker(vis, self.pivot, (0, 255, 255), cv2.MARKER_CROSS, 20, 2)
            cv2.putText(
                vis,
                "PIVOT",
                (self.pivot[0] + 10, self.pivot[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
            )

        if result.detected:
            bx, by = int(result.pixel_x), int(result.pixel_y)
            cv2.circle(vis, (bx, by), 12, (0, 255, 0), 2)
            cv2.circle(vis, (bx, by), 3, (0, 255, 0), -1)

            if self.pivot is not None:
                if self.v_left is not None and self.v_right is not None:
                    cv2.line(vis, self.v_left, (bx, by), (200, 200, 200), 1, cv2.LINE_AA)
                    cv2.line(vis, self.v_right, (bx, by), (200, 200, 200), 1, cv2.LINE_AA)
                else:
                    cv2.line(vis, self.pivot, (bx, by), (200, 200, 200), 1, cv2.LINE_AA)
                angle_deg = np.degrees(result.angle)
                radius = 60
                cv2.ellipse(
                    vis,
                    self.pivot,
                    (radius, radius),
                    0,
                    90,
                    90 - angle_deg,
                    (0, 200, 255),
                    2,
                    cv2.LINE_AA,
                )

                label = f"theta = {np.degrees(result.angle):.1f} deg"
            else:
                label = f"x={result.pixel_x:.0f}, y={result.pixel_y:.0f}"

            cv2.putText(vis, label, (bx + 15, by - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Note: "no marker" state is shown by the dashboard top bar, so we do not
        # draw a redundant (and overlapping) banner on the video here.
        return vis

    def set_hsv_range(self, lower: tuple, upper: tuple):
        """Manually set HSV detection range."""
        self.hsv_lower = np.array(lower)
        self.hsv_upper = np.array(upper)
        self.color_name = "custom"
        self.color_center_h = None

    def get_mask_preview(self, frame: np.ndarray) -> np.ndarray:
        """Return the binary mask for HSV tuning."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        return self._compute_mask(hsv)
