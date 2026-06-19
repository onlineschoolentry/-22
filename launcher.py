"""
PhysicsLens launcher.

Simple GUI for choosing the experiment and camera source before starting the
OpenCV dashboard.
"""

from argparse import Namespace
import tkinter as tk
from tkinter import ttk


class PhysicsLensLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PhysicsLens")
        self.root.geometry("600x450")
        self.root.resizable(False, False)

        self.experiment = tk.StringVar(value="pendulum")
        self.source = tk.StringVar(value="Local webcam / Iriun (recommended)")
        self.color = tk.StringVar(value="orange")
        self.camera = tk.StringVar(value="0")
        self.video = tk.StringVar(value="")
        self.stream_url = tk.StringVar(value="")
        self.length = tk.StringVar(value="0.70")
        self.mass = tk.StringVar(value="0.05")
        self.pixels_per_meter = tk.StringVar(value="300")
        self.scale_distance = tk.StringVar(value="1.0")
        self.phone_port = tk.StringVar(value="8765")
        self.show_advanced = tk.BooleanVar(value=False)

        self._build()

    def _build(self):
        self.root.configure(bg="#f4f6f8")
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Hint.TLabel", foreground="#56616f")
        style.configure("Primary.TButton", font=("Segoe UI", 12, "bold"))

        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="PhysicsLens", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="여러 물리 실험에서 측정할 물리량과 카메라 입력을 선택하세요.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        quick = ttk.LabelFrame(outer, text="Quick setup", padding=12)
        quick.pack(fill="x")

        self._row_combo(
            quick,
            0,
            "Experiment",
            self.experiment,
            [
                "pendulum",
                "freefall",
                "projectile",
                "linear_motion",
                "spring_mass",
                "circular_motion",
                "motion2d",
            ],
        )
        self._row_combo(
            quick,
            1,
            "Camera",
            self.source,
            [
                "Local webcam / Iriun (recommended)",
                "IP camera stream URL",
                "Phone QR browser",
                "Video file",
            ],
        )
        self._row_combo(quick, 2, "Marker color", self.color, ["orange", "green", "red", "blue", "yellow"])

        ttk.Label(
            outer,
            text=(
                "진자는 회전축-추 보정이 필요하고, 나머지 실험은 원점과 기준 거리 보정 후 "
                "위치/속도/가속도/힘을 공통 파이프라인으로 측정합니다."
            ),
            style="Hint.TLabel",
            wraplength=500,
        ).pack(anchor="w", pady=(10, 4))

        ttk.Checkbutton(
            outer,
            text="Show advanced settings",
            variable=self.show_advanced,
            command=self._toggle_advanced,
        ).pack(anchor="w", pady=(6, 0))

        self.advanced = ttk.LabelFrame(outer, text="Advanced", padding=10)
        self._entry(self.advanced, 0, "Local camera index", self.camera)
        self._entry(self.advanced, 1, "Video path", self.video)
        self._entry(self.advanced, 2, "Stream URL", self.stream_url)
        self._entry(self.advanced, 3, "Phone port", self.phone_port)
        self._entry(self.advanced, 4, "Pendulum length (m)", self.length)
        self._entry(self.advanced, 5, "Object mass (kg)", self.mass)
        self._entry(self.advanced, 6, "Pixels per meter", self.pixels_per_meter)
        self._entry(self.advanced, 7, "Scale distance (m)", self.scale_distance)

        ttk.Button(
            outer,
            text="Start",
            command=self.start,
            style="Primary.TButton",
        ).pack(fill="x", pady=(16, 0), ipady=8)

    def _row_combo(self, parent, row, label, variable, values):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=28).grid(
            row=row,
            column=1,
            sticky="ew",
            pady=8,
        )
        parent.columnconfigure(1, weight=1)

    def _entry(self, parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(parent, textvariable=variable, width=36).grid(row=row, column=1, sticky="ew", pady=4)
        parent.columnconfigure(1, weight=1)

    def _toggle_advanced(self):
        if self.show_advanced.get():
            self.advanced.pack(fill="x", pady=(8, 0))
            self.root.geometry("600x660")
        else:
            self.advanced.pack_forget()
            self.root.geometry("600x450")

    def _float(self, value, fallback):
        try:
            return float(value)
        except ValueError:
            return fallback

    def _int(self, value, fallback):
        try:
            return int(value)
        except ValueError:
            return fallback

    def _args(self):
        source = self._source_code()
        return Namespace(
            experiment=self.experiment.get(),
            camera=self._int(self.camera.get(), 0),
            video=self.video.get().strip() if source == "video" else None,
            phone_camera=source == "phone",
            phone_host="0.0.0.0",
            phone_port=self._int(self.phone_port.get(), 8765),
            phone_https=True,
            show_qr=True,
            stream_url=self.stream_url.get().strip() if source == "stream" else None,
            color=self.color.get(),
            length=self._float(self.length.get(), 0.70),
            gravity=9.81,
            gamma=0.05,
            augmented=True,
            pixels_per_meter=self._float(self.pixels_per_meter.get(), 300.0),
            scale_distance=self._float(self.scale_distance.get(), 1.0),
            mass=self._float(self.mass.get(), 0.05),
        )

    def _source_code(self):
        selected = self.source.get()
        if selected.startswith("Local webcam"):
            return "local"
        if selected.startswith("IP camera"):
            return "stream"
        if selected.startswith("Phone QR"):
            return "phone"
        if selected.startswith("Video"):
            return "video"
        return selected

    def start(self):
        from main import PhysicsLensApp

        args = self._args()
        self.root.destroy()
        PhysicsLensApp(args).run()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    PhysicsLensLauncher().run()
