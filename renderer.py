"""
Real-time plot renderer using OpenCV drawing primitives.
Zero external dependencies beyond cv2 and numpy.
Renders time-series, phase-space, and statistics panels.
"""

from typing import Tuple

import cv2
import numpy as np

# Color palette (BGR)
C_BG = (30, 30, 30)
C_GRID = (60, 60, 60)
C_TEXT = (220, 220, 220)
C_DIM = (140, 140, 140)
C_THETA = (0, 200, 255)
C_OMEGA = (255, 180, 0)
C_ALPHA = (100, 255, 100)
C_NUMERIC = (80, 80, 255)
C_UNCERT = (60, 100, 60)
C_INNOV = (200, 100, 255)
C_GAMMA = (255, 255, 0)
C_PHASE = (0, 200, 200)
C_ACCENT = (0, 180, 255)
C_OK = (80, 220, 120)
C_WARN = (0, 90, 255)


def _unit_text(label: str, unit: str) -> str:
    return f"{label} ({unit})" if unit else label


def draw_top_bar(canvas: np.ndarray, stats: dict, w: int):
    """Draw a compact workflow/status bar."""
    cv2.rectangle(canvas, (0, 0), (w, 42), (18, 18, 18), -1)
    cv2.line(canvas, (0, 42), (w, 42), C_GRID, 1)
    experiment = stats.get("experiment", "Estimator")
    source = stats.get("source", "")
    status = stats.get("status", "No marker")
    tracking = stats.get("tracking", False)
    status_color = C_OK if tracking else C_WARN

    cv2.putText(canvas, "PhysicsLens", (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.72, C_ACCENT, 2, cv2.LINE_AA)
    cv2.putText(canvas, f"{experiment}  |  {source}", (190, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.48, C_TEXT, 1, cv2.LINE_AA)

    status_text = str(status)
    status_font = 0.5
    status_text_w, _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, status_font, 1)[0]
    status_x = max(w - status_text_w - 16, int(w * 0.78))
    dot_x = max(status_x - 17, 0)

    shortcuts = "P pick   C calibrate   M mask   S save   Q quit"
    shortcut_font = 0.45
    shortcut_text_w, _ = cv2.getTextSize(shortcuts, cv2.FONT_HERSHEY_SIMPLEX, shortcut_font, 1)[0]
    shortcut_right = dot_x - 24
    shortcut_x = max(420, shortcut_right - shortcut_text_w)
    if shortcut_x + shortcut_text_w < shortcut_right:
        cv2.putText(canvas, shortcuts, (shortcut_x, 27), cv2.FONT_HERSHEY_SIMPLEX, shortcut_font, C_DIM, 1, cv2.LINE_AA)

    cv2.circle(canvas, (dot_x, 21), 7, status_color, -1, cv2.LINE_AA)
    cv2.putText(canvas, status_text, (status_x, 27), cv2.FONT_HERSHEY_SIMPLEX, status_font, C_TEXT, 1, cv2.LINE_AA)


def draw_line_plot(
    canvas: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    data: list,
    color: tuple = C_THETA,
    title: str = "",
    y_label: str = "",
    band_upper: list = None,
    band_lower: list = None,
    band_color: tuple = C_UNCERT,
    data2: list = None,
    color2: tuple = C_NUMERIC,
    label1: str = "",
    label2: str = "",
    max_points: int = 300,
):
    """Draw a time-series line plot on the canvas."""
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_BG, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_GRID, 1)

    if title:
        cv2.putText(
            canvas,
            title,
            (x + 8, y + 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            C_TEXT,
            1,
            cv2.LINE_AA,
        )

    if len(data) < 2:
        return

    d = data[-max_points:]
    n = len(d)

    all_vals = list(d)
    if data2 and len(data2) >= 2:
        all_vals += list(data2[-max_points:])
    if band_upper and len(band_upper) >= 2:
        all_vals += list(band_upper[-max_points:])
    if band_lower and len(band_lower) >= 2:
        all_vals += list(band_lower[-max_points:])

    y_min = min(all_vals)
    y_max = max(all_vals)
    margin = max(abs(y_max - y_min) * 0.15, 0.01)
    y_min -= margin
    y_max += margin

    pad_top = 28
    pad_bot = 20
    pad_left = 50
    pad_right = 10
    px = x + pad_left
    py = y + pad_top
    pw = w - pad_left - pad_right
    ph = h - pad_top - pad_bot

    if pw <= 0 or ph <= 0:
        return

    def to_screen(i: int, v: float) -> Tuple[int, int]:
        sx = px + int(i / max(n - 1, 1) * pw)
        sy = py + int((1 - (v - y_min) / max(y_max - y_min, 1e-9)) * ph)
        return sx, sy

    cv2.line(canvas, (px, py), (px, py + ph), C_GRID, 1)
    cv2.line(canvas, (px, py + ph), (px + pw, py + ph), C_GRID, 1)

    for frac in [0.0, 0.5, 1.0]:
        val = y_min + frac * (y_max - y_min)
        sy = py + int((1 - frac) * ph)
        cv2.line(canvas, (px - 4, sy), (px, sy), C_GRID, 1)
        txt = f"{val:.2f}" if abs(val) < 10 else f"{val:.1f}"
        cv2.putText(
            canvas,
            txt,
            (x + 2, sy + 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.3,
            C_DIM,
            1,
            cv2.LINE_AA,
        )

    if band_upper and band_lower and len(band_upper) >= 2:
        bu = band_upper[-max_points:]
        bl = band_lower[-max_points:]
        nn = min(len(bu), len(bl), n)
        pts_upper = [to_screen(i, bu[i]) for i in range(nn)]
        pts_lower = [to_screen(i, bl[i]) for i in range(nn - 1, -1, -1)]
        pts_poly = np.array(pts_upper + pts_lower, dtype=np.int32)
        if len(pts_poly) > 2:
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [pts_poly], band_color)
            cv2.addWeighted(overlay, 0.4, canvas, 0.6, 0, canvas)

    pts = [to_screen(i, d[i]) for i in range(n)]
    if len(pts) >= 2:
        cv2.polylines(canvas, [np.array(pts, dtype=np.int32)], False, color, 1, cv2.LINE_AA)

    if data2 and len(data2) >= 2:
        d2 = data2[-max_points:]
        nn2 = min(len(d2), n)
        pts2 = [to_screen(i, d2[i]) for i in range(nn2)]
        if len(pts2) >= 2:
            cv2.polylines(canvas, [np.array(pts2, dtype=np.int32)], False, color2, 1, cv2.LINE_AA)

    if label1 or label2:
        lx = px + max(pw - 160, 10)
        ly = py + 5
        if label1:
            cv2.line(canvas, (lx, ly + 6), (lx + 20, ly + 6), color, 2)
            cv2.putText(
                canvas,
                label1,
                (lx + 25, ly + 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                C_TEXT,
                1,
                cv2.LINE_AA,
            )
            ly += 16
        if label2:
            cv2.line(canvas, (lx, ly + 6), (lx + 20, ly + 6), color2, 2)
            cv2.putText(
                canvas,
                label2,
                (lx + 25, ly + 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                C_TEXT,
                1,
                cv2.LINE_AA,
            )

    if y_label:
        cv2.putText(
            canvas,
            y_label,
            (x + pad_left + 5, y + pad_top + 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            C_DIM,
            1,
            cv2.LINE_AA,
        )


def draw_phase_space(
    canvas: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    theta_data: list,
    omega_data: list,
    title: str = "Phase Space (theta vs omega)",
    x_label: str = "theta",
    y_label: str = "omega",
    max_points: int = 500,
):
    """Draw phase-space portrait."""
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_BG, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_GRID, 1)
    cv2.putText(canvas, title, (x + 8, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, C_TEXT, 1, cv2.LINE_AA)

    if len(theta_data) < 2 or len(omega_data) < 2:
        return

    td = theta_data[-max_points:]
    od = omega_data[-max_points:]
    n = min(len(td), len(od))

    pad = 35
    px = x + pad
    py = y + 28
    pw = w - 2 * pad
    ph = h - 28 - pad

    if pw <= 0 or ph <= 0:
        return

    th_min, th_max = min(td), max(td)
    om_min, om_max = min(od), max(od)
    th_margin = max(abs(th_max - th_min) * 0.15, 0.05)
    om_margin = max(abs(om_max - om_min) * 0.15, 0.1)
    th_min -= th_margin
    th_max += th_margin
    om_min -= om_margin
    om_max += om_margin

    def to_screen(th: float, om: float) -> Tuple[int, int]:
        sx = px + int((th - th_min) / max(th_max - th_min, 1e-9) * pw)
        sy = py + int((1 - (om - om_min) / max(om_max - om_min, 1e-9)) * ph)
        return sx, sy

    cv2.putText(canvas, x_label, (x + max(w // 2 - 30, 8), y + h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, C_DIM, 1, cv2.LINE_AA)
    cv2.putText(canvas, y_label, (x + 5, y + h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, C_DIM, 1, cv2.LINE_AA)

    ox, oy = to_screen(0, 0)
    if px <= ox <= px + pw:
        cv2.line(canvas, (ox, py), (ox, py + ph), C_GRID, 1)
    if py <= oy <= py + ph:
        cv2.line(canvas, (px, oy), (px + pw, oy), C_GRID, 1)

    pts = [to_screen(td[i], od[i]) for i in range(n)]
    for i in range(1, len(pts)):
        alpha = i / len(pts)
        c = tuple(int(alpha * cc) for cc in C_PHASE)
        cv2.line(canvas, pts[i - 1], pts[i], c, 1, cv2.LINE_AA)

    if pts:
        cv2.circle(canvas, pts[-1], 5, (0, 255, 255), -1)


def draw_stats_panel(
    canvas: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    stats: dict,
):
    """Draw statistics / info panel."""
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_BG, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_GRID, 1)
    experiment = stats.get("experiment", "Estimator")
    cv2.putText(canvas, experiment, (x + 8, y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, C_ACCENT, 1, cv2.LINE_AA)

    est_g = stats.get("est_g", "-")
    if isinstance(est_g, str):
        est_g_value = est_g
    else:
        est_g_value = f"{est_g:.3f} m/s^2"

    primary = stats.get("primary_label", "theta")
    velocity = stats.get("velocity_label", "omega")
    acceleration = stats.get("acceleration_label", "alpha")
    primary_unit = stats.get("primary_unit", "rad")
    velocity_unit = stats.get("velocity_unit", "rad/s")
    acceleration_unit = stats.get("acceleration_unit", "rad/s^2")

    items = [
        (primary, f"{stats.get('theta', 0):.4f} {primary_unit}"),
        (velocity, f"{stats.get('omega', 0):.4f} {velocity_unit}"),
        (acceleration, f"{stats.get('alpha', 0):.4f} {acceleration_unit}"),
        ("Innovation", f"{stats.get('innovation', 0):.5f}"),
        ("FPS", f"{stats.get('fps', 0):.1f}"),
    ]
    if "gamma" in stats:
        items.insert(3, ("gamma (damping)", f"{stats.get('gamma', 0):.5f}"))
        items.insert(5, ("Estimated g", est_g_value))
    if "force" in stats:
        items.insert(3, ("Force", f"{stats.get('force', 0):.4f} N"))
        items.insert(4, ("Speed", f"{stats.get('speed', 0):.4f} m/s"))

    ly = y + 45
    row_gap = 42
    for label, value in items:
        if not label:
            ly += 8
            cv2.line(canvas, (x + 10, ly), (x + w - 10, ly), C_GRID, 1)
            ly += 8
            continue
        if ly + row_gap > y + h - 8:
            break
        cv2.putText(canvas, label, (x + 12, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.42, C_DIM, 1, cv2.LINE_AA)
        cv2.putText(canvas, str(value), (x + 12, ly + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, C_TEXT, 1, cv2.LINE_AA)
        ly += row_gap


def draw_help_overlay(canvas: np.ndarray, x: int, y: int, w: int, h: int):
    """Draw keyboard shortcut help."""
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_BG, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C_GRID, 1)
    cv2.putText(canvas, "Next steps", (x + 8, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, C_ACCENT, 1, cv2.LINE_AA)

    shortcuts = [
        "1. Put marker in frame",
        "2. Press P, click marker (set color)",
        "3. Press C, click points (calibrate)",
        "S save    M mask    Q quit",
    ]
    ly = y + 42
    for txt in shortcuts:
        if ly > y + h - 8:
            break
        cv2.putText(canvas, txt, (x + 12, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.38, C_DIM, 1, cv2.LINE_AA)
        ly += 20


def compose_dashboard(
    video_frame: np.ndarray,
    history,
    stats: dict,
    window_w: int = 1400,
    window_h: int = 800,
) -> np.ndarray:
    """Compose the full dashboard layout."""
    canvas = np.full((window_h, window_w, 3), 20, dtype=np.uint8)
    draw_top_bar(canvas, stats, window_w)

    gap = 10
    bar_h = 44
    top_h = int(window_h * 0.52) - bar_h
    left_w = int(window_w * 0.39)
    right_w = window_w - left_w - gap
    bottom_y = bar_h + top_h + gap
    bottom_h = window_h - bottom_y - gap

    video_target_w = left_w
    video_target_h = top_h
    frame_h, frame_w = video_frame.shape[:2]
    scale = min(video_target_w / frame_w, video_target_h / frame_h)
    vid_w = max(1, int(frame_w * scale))
    vid_h = max(1, int(frame_h * scale))
    video_x = 0
    video_y = bar_h
    vid = cv2.resize(video_frame, (vid_w, vid_h))
    canvas[video_y:video_y + vid_h, video_x:video_x + vid_w] = vid

    plot_x = left_w + gap
    plot_h = max((top_h - 2 * gap) // 3, 110)
    plot_w = right_w

    theta_upper = [t + s for t, s in zip(history.theta, history.theta_std)] if history.theta_std else None
    theta_lower = [t - s for t, s in zip(history.theta, history.theta_std)] if history.theta_std else None
    primary = stats.get("primary_label", "theta")
    velocity = stats.get("velocity_label", "omega")
    acceleration = stats.get("acceleration_label", "alpha")
    primary_unit = stats.get("primary_unit", "rad")
    velocity_unit = stats.get("velocity_unit", "rad/s")
    acceleration_unit = stats.get("acceleration_unit", "rad/s^2")

    draw_line_plot(canvas, plot_x, bar_h, plot_w, plot_h, history.theta, C_THETA, title=_unit_text(primary, primary_unit), y_label=primary, band_upper=theta_upper, band_lower=theta_lower)
    draw_line_plot(canvas, plot_x, bar_h + plot_h + gap, plot_w, plot_h, history.omega, C_OMEGA, title=_unit_text(velocity, velocity_unit), data2=history.numerical_omega, color2=C_NUMERIC, label1="Kalman", label2=f"d{primary}/dt")
    draw_line_plot(canvas, plot_x, bar_h + (plot_h + gap) * 2, plot_w, plot_h, history.alpha, C_ALPHA, title=_unit_text(acceleration, acceleration_unit), data2=history.numerical_alpha, color2=C_NUMERIC, label1="Kalman", label2=f"d2{primary}/dt2")

    phase_w = left_w
    stats_w = right_w
    draw_phase_space(canvas, 0, bottom_y, phase_w, bottom_h, history.theta, history.omega, title=f"Phase Space ({primary} vs {velocity})", x_label=primary, y_label=velocity)

    stats_h = max((bottom_h - gap) // 2, 150)
    draw_stats_panel(canvas, plot_x, bottom_y, stats_w, stats_h, stats)

    gamma_y = bottom_y + stats_h + gap
    gamma_h = window_h - gamma_y - gap
    if history.gamma:
        g_upper = [g + s for g, s in zip(history.gamma, history.gamma_std)]
        g_lower = [g - s for g, s in zip(history.gamma, history.gamma_std)]
        draw_line_plot(canvas, plot_x, gamma_y, stats_w, gamma_h, history.gamma, C_GAMMA, title="gamma convergence", band_upper=g_upper, band_lower=g_lower, band_color=(60, 80, 60))
    else:
        draw_line_plot(canvas, plot_x, gamma_y, stats_w, gamma_h, history.innovation, C_INNOV, title="Innovation (residual)")

    # Onboarding help only -- hide once tracking starts or a mode banner is shown.
    # Placed in the (empty) bottom-left phase-space panel, never over the live
    # video, so the user can always see the marker while setting up.
    if stats.get("show_help", True):
        overlay_w = min(phase_w - 20, 380)
        overlay_h = min(130, bottom_h - 20)
        overlay_x = 10
        overlay_y = bottom_y + 10
        draw_help_overlay(canvas, overlay_x, overlay_y, overlay_w, overlay_h)

    return canvas
