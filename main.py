"""
PhysicsLens main application.

Tracks a colored object from camera/video input and estimates hidden physical
state variables with a selected Kalman-based experiment model.
"""

import argparse
import csv
import sys
import time

import cv2
import numpy as np

from estimators import Motion2DEstimator, PendulumEstimator, create_estimator
from phone_camera import PhoneCameraCapture
from renderer import compose_dashboard
from tracker import PendulumTracker


class PhysicsLensApp:
    """Main application controller."""

    WINDOW_NAME = "PhysicsLens"
    WINDOW_W = 1400
    WINDOW_H = 800

    def __init__(self, args):
        self.args = args
        self.source_kind = self._source_kind()
        self.cap = self._open_capture()
        self._stream_failures = 0

        if not self.cap.isOpened():
            print("[ERROR] Cannot open input. Check --camera, --video, or --stream-url.")
            sys.exit(1)

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.dt = 1.0 / self.fps

        self.tracker = PendulumTracker(color=args.color)
        self.estimator = create_estimator(args, self.dt)

        self.show_mask = False
        self.calibrating = False
        self.picking_color = False
        self.calib_step = 0
        self._pendulum_left_anchor = None
        self.running = True
        self.frame_count = 0
        self.fps_actual = 0.0
        self._fps_timer = time.time()
        self._fps_count = 0
        self.last_stats = {
            **self.estimator.dashboard_metadata(),
            "source": self._source_label(),
            "status": "Waiting for marker",
            "tracking": False,
        }
        self._last_frame = None
        self._motion_scale_start = None

        cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.WINDOW_NAME, self.WINDOW_W, self.WINDOW_H)
        cv2.setMouseCallback(self.WINDOW_NAME, self._on_mouse)

    def _source_kind(self) -> str:
        if self.args.phone_camera:
            return "phone"
        if self.args.stream_url:
            return "stream"
        if self.args.video:
            return "video"
        return "camera"

    def _open_capture(self):
        if self.source_kind == "phone":
            return PhoneCameraCapture(
                host=self.args.phone_host,
                port=self.args.phone_port,
                show_qr=self.args.show_qr,
                https=self.args.phone_https,
            )
        if self.source_kind == "stream":
            cap = cv2.VideoCapture(self.args.stream_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        if self.source_kind == "video":
            return cv2.VideoCapture(self.args.video)

        cap = cv2.VideoCapture(self.args.camera)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _source_label(self) -> str:
        labels = {
            "phone": "Phone QR camera",
            "stream": "IP stream",
            "video": "Video file",
            "camera": f"Webcam {self.args.camera}",
        }
        return labels.get(self.source_kind, self.source_kind)

    def _video_rect(self):
        """Return displayed video rectangle in dashboard coordinates.

        Must mirror compose_dashboard's geometry exactly, otherwise calibration
        clicks map to the wrong frame pixels.
        """
        if self._last_frame is None:
            frame_h, frame_w = 480, 640
        else:
            frame_h, frame_w = self._last_frame.shape[:2]

        bar_h = 44  # top status bar height in renderer.compose_dashboard
        top_h = int(self.WINDOW_H * 0.52) - bar_h
        left_w = int(self.WINDOW_W * 0.39)
        scale = min(left_w / frame_w, top_h / frame_h)
        vid_w = max(1, int(frame_w * scale))
        vid_h = max(1, int(frame_h * scale))
        return 0, bar_h, vid_w, vid_h

    def _window_to_frame(self, x: int, y: int):
        vx, vy, vw, vh = self._video_rect()
        if not (vx <= x <= vx + vw and vy <= y <= vy + vh):
            return None
        frame_h, frame_w = self._last_frame.shape[:2]
        fx = int((x - vx) / vw * frame_w)
        fy = int((y - vy) / vh * frame_h)
        return fx, fy

    def _on_mouse(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if not (self.calibrating or self.picking_color):
            return

        point = self._window_to_frame(x, y)
        if point is None:
            return
        fx, fy = point

        if self.picking_color:
            if self._last_frame is not None:
                hsv = self.tracker.pick_color_at(self._last_frame, fx, fy)
                print(f"[COLOR] Picked marker HSV={hsv}; detection range updated.")
            self.picking_color = False
            return

        if isinstance(self.estimator, PendulumEstimator):
            self._calibrate_pendulum(fx, fy)
        elif isinstance(self.estimator, Motion2DEstimator):
            self._calibrate_motion2d(fx, fy)

    def _calibrate_pendulum(self, fx: int, fy: int):
        if self.calib_step == 0:
            self._pendulum_left_anchor = (fx, fy)
            print(f"[CALIB] Left V-anchor set at ({fx}, {fy})")
            self.calib_step = 1
            return

        if self.calib_step == 1:
            right_anchor = (fx, fy)
            self.tracker.set_v_anchors(self._pendulum_left_anchor, right_anchor)
            print(f"[CALIB] Right V-anchor set at ({fx}, {fy}); effective pivot={self.tracker.pivot}")
            self.calib_step = 2
            return

        px, py = self.tracker.pivot
        bob = (fx, fy)
        if self._last_frame is not None:
            hsv = self.tracker.pick_color_at(self._last_frame, fx, fy)
            print(f"[COLOR] Bob marker HSV={hsv}; detection range locked to bob.")
        left = self.tracker.v_left
        right = self.tracker.v_right
        half_span_px = np.sqrt((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) / 2
        string_px = (
            np.sqrt((bob[0] - left[0]) ** 2 + (bob[1] - left[1]) ** 2)
            + np.sqrt((bob[0] - right[0]) ** 2 + (bob[1] - right[1]) ** 2)
        ) / 2
        length_px = np.sqrt(max(string_px**2 - half_span_px**2, 0.0))
        self.tracker.set_string_length_pixels(length_px)
        if string_px > 0:
            self.estimator.set_length(self.args.length * (length_px / string_px))
        self.calibrating = False
        self.calib_step = 0
        self.estimator.reset()
        self.tracker.last_position = (float(fx), float(fy))
        self.tracker._lost_frames = 0
        print(
            f"[CALIB] Bob set at ({fx}, {fy}), "
            f"L_eff_pixels={length_px:.1f}, L_eff={self.estimator.L:.3f}m"
        )

    def _calibrate_motion2d(self, fx: int, fy: int):
        if self.calib_step == 0:
            self._motion_scale_start = (fx, fy)
            self.estimator.set_origin(fx, fy)
            print(f"[CALIB] Origin set at ({fx}, {fy})")
            self.calib_step = 1
            return

        self.estimator.set_scale_from_points(
            self._motion_scale_start,
            (fx, fy),
            self.args.scale_distance,
        )
        self.estimator.reset()
        self.calibrating = False
        self.calib_step = 0
        print(
            "[CALIB] Scale set: "
            f"{self.estimator.pixels_per_meter:.1f} px/m "
            f"from {self.args.scale_distance:.2f} m reference"
        )

    def run(self):
        print("=" * 60)
        print("  PhysicsLens")
        print(f"  Experiment: {self.args.experiment}")
        print(f"  Source: {self.source_kind}")
        print(f"  Color: {self.args.color} | Camera FPS: {self.fps:.0f}")
        print("  Press [C] to calibrate, [S] to save CSV, [Q] to quit")
        print("=" * 60)

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                if self.source_kind == "video":
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                if self.source_kind == "stream":
                    self._reconnect_stream()
                    continue
                print("[ERROR] Camera read failed")
                break
            self._stream_failures = 0

            self._last_frame = frame
            self.frame_count += 1
            result = self.tracker.track(frame)

            if self._measurement_ready(result):
                observation = {
                    "angle": result.angle,
                    "pixel_x": result.pixel_x,
                    "pixel_y": result.pixel_y,
                }
                state = self.estimator.update(observation)
                est_g = self.estimator.estimated_g()
                self.last_stats = {
                    **state,
                    "est_g": f"{est_g:.3f}" if est_g else "-",
                    "frames": self.frame_count,
                    "fps": self.fps_actual,
                    "source": self._source_label(),
                    "status": "Tracking",
                    "tracking": True,
                }
            else:
                self.estimator.predict()
                self.last_stats = {
                    **self.last_stats,
                    **self.estimator.dashboard_metadata(),
                    "frames": self.frame_count,
                    "fps": self.fps_actual,
                    "source": self._source_label(),
                    "status": self._waiting_status(result),
                    "tracking": False,
                }

            self._update_fps()
            dashboard = self._render(frame, result)
            cv2.imshow(self.WINDOW_NAME, dashboard)
            self._handle_key(cv2.waitKey(1) & 0xFF)

        self.cap.release()
        cv2.destroyAllWindows()

    def _measurement_ready(self, result) -> bool:
        if not result.detected:
            return False
        if isinstance(self.estimator, PendulumEstimator):
            return self.tracker.pivot is not None
        return True

    def _waiting_status(self, result) -> str:
        if not result.detected:
            return "No marker"
        if isinstance(self.estimator, PendulumEstimator) and self.tracker.pivot is None:
            return "Press C to calibrate"
        return "Waiting"

    def _reconnect_stream(self):
        self._stream_failures += 1
        if self._stream_failures == 1 or self._stream_failures % 30 == 0:
            print("[STREAM] Frame read failed. Reconnecting phone camera stream...")
        self.cap.release()
        time.sleep(0.2)
        self.cap = self._open_capture()

    def _update_fps(self):
        self._fps_count += 1
        elapsed = time.time() - self._fps_timer
        if elapsed >= 1.0:
            self.fps_actual = self._fps_count / elapsed
            self._fps_count = 0
            self._fps_timer = time.time()

    def _render(self, frame, result):
        if self.show_mask:
            mask = self.tracker.get_mask_preview(frame)
            vis_frame = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        else:
            vis_frame = self.tracker.draw_overlay(frame, result)

        if self.calibrating:
            msg = self._calibration_message()
            cv2.putText(
                vis_frame,
                f"[CALIBRATING] {msg}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
        elif self.picking_color:
            cv2.putText(
                vis_frame,
                "[PICK COLOR] Click the marker",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 255),
                2,
            )

        # Show the onboarding help only before the user is set up: hide it once
        # tracking is live or while a calibration/color-pick banner is on screen.
        self.last_stats["show_help"] = not (
            self.last_stats.get("tracking")
            or self.calibrating
            or self.picking_color
        )

        return compose_dashboard(
            vis_frame,
            self.estimator.history,
            self.last_stats,
            self.WINDOW_W,
            self.WINDOW_H,
        )

    def _calibration_message(self) -> str:
        if isinstance(self.estimator, PendulumEstimator):
            if self.calib_step == 0:
                return "Click left V-anchor"
            if self.calib_step == 1:
                return "Click right V-anchor"
            return "Click bob at rest"
        return "Click origin" if self.calib_step == 0 else "Click scale reference point"

    def _handle_key(self, key: int):
        if key in (ord("q"), ord("Q"), 27):
            self.running = False
        elif key in (ord("c"), ord("C")):
            self.calibrating = True
            self.picking_color = False
            self.calib_step = 0
            self._pendulum_left_anchor = None
            if isinstance(self.estimator, PendulumEstimator):
                self.tracker.v_left = None
                self.tracker.v_right = None
                self.tracker.pivot = None
            print(f"[CALIB] {self._calibration_message()}.")
        elif key in (ord("p"), ord("P")):
            self.picking_color = True
            self.calibrating = False
            print("[COLOR] Click the marker to sample its color.")
        elif key in (ord("r"), ord("R")):
            self.estimator.reset()
            print("[RESET] Estimator reset.")
        elif key in (ord("m"), ord("M")):
            self.show_mask = not self.show_mask
            print(f"[MASK] {'ON' if self.show_mask else 'OFF'}")
        elif key in (ord("a"), ord("A")) and isinstance(self.estimator, PendulumEstimator):
            self.estimator.toggle_augmented()
            print(f"[MODE] Pendulum augmented EKF: {self.estimator.augmented}")
        elif key in (ord("+"), ord("=")) and isinstance(self.estimator, PendulumEstimator):
            self.estimator.set_length(self.estimator.L + 0.05)
            print(f"[PARAM] L = {self.estimator.L:.2f}m")
        elif key in (ord("-"), ord("_")) and isinstance(self.estimator, PendulumEstimator):
            self.estimator.set_length(self.estimator.L - 0.05)
            print(f"[PARAM] L = {self.estimator.L:.2f}m")
        elif key in (ord("s"), ord("S")):
            self._save_csv()

    def _save_csv(self):
        h = self.estimator.history
        if not h.time:
            print("[SAVE] No data to save.")
            return

        fname = f"{self.args.experiment}_kalman_data_{int(time.time())}.csv"
        with open(fname, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.estimator.csv_headers())
            for i in range(len(h.time)):
                writer.writerow(self.estimator.csv_row(i))

        print(f"[SAVE] Data saved to {fname} ({len(h.time)} frames)")


def parse_args():
    parser = argparse.ArgumentParser(
        description="PhysicsLens: camera-based physical state estimation"
    )
    parser.add_argument(
        "--experiment",
        choices=[
            "pendulum",
            "freefall",
            "projectile",
            "linear_motion",
            "spring_mass",
            "circular_motion",
            "motion2d",
        ],
        default="pendulum",
        help="Experiment preset to run.",
    )
    parser.add_argument("--camera", type=int, default=0, help="Local webcam index.")
    parser.add_argument("--video", type=str, default=None, help="Video file path for repeatable tests.")
    parser.add_argument(
        "--phone-camera",
        action="store_true",
        help="Use the built-in phone browser camera receiver and show a QR code.",
    )
    parser.add_argument("--phone-host", type=str, default="0.0.0.0", help="Phone receiver bind host.")
    parser.add_argument("--phone-port", type=int, default=8765, help="Phone receiver port.")
    parser.add_argument("--phone-https", action="store_true", default=True, help="Use HTTPS for built-in phone camera.")
    parser.add_argument("--phone-http", action="store_false", dest="phone_https", help="Use HTTP for built-in phone camera.")
    parser.add_argument("--show-qr", action="store_true", default=True, help="Show QR window for phone camera mode.")
    parser.add_argument("--no-qr", action="store_false", dest="show_qr", help="Do not show QR window.")
    parser.add_argument(
        "--stream-url",
        type=str,
        default=None,
        help="Phone/IP camera stream URL, e.g. http://192.168.0.10:8080/video or rtsp://...",
    )
    parser.add_argument(
        "--color",
        type=str,
        default="orange",
        choices=["orange", "green", "red", "blue", "yellow", "magenta", "pink"],
        help="Tracked object color.",
    )
    parser.add_argument("--length", type=float, default=0.70, help="Pendulum length in meters.")
    parser.add_argument("--gravity", type=float, default=9.81, help="Gravity constant.")
    parser.add_argument("--gamma", type=float, default=0.05, help="Initial damping estimate.")
    parser.add_argument("--augmented", action="store_true", default=True, help="Estimate damping in pendulum mode.")
    parser.add_argument("--no-augmented", action="store_false", dest="augmented", help="Disable damping estimation.")
    parser.add_argument("--pixels-per-meter", type=float, default=300.0, help="Initial pixel-to-meter scale for motion2d.")
    parser.add_argument("--scale-distance", type=float, default=1.0, help="Calibration distance in meters for motion2d.")
    parser.add_argument("--mass", type=float, default=0.05, help="Tracked object mass in kg for force estimate.")
    return parser.parse_args()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        from launcher import PhysicsLensLauncher

        PhysicsLensLauncher().run()
    else:
        app = PhysicsLensApp(parse_args())
        app.run()
