"""
Experiment estimators for PhysicsLens.

Each estimator accepts one camera observation per frame and exposes the same
history fields so the dashboard and CSV export can stay experiment-agnostic.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

MOTION_EXPERIMENT_PROFILES = {
    "motion2d": ("2D Motion KF", "x", "vx", "ax", "m", "m/s", "m/s^2"),
    "freefall": ("Free Fall KF", "y", "vy", "ay", "m", "m/s", "m/s^2"),
    "projectile": ("Projectile Motion KF", "x", "speed", "|a|", "m", "m/s", "m/s^2"),
    "linear_motion": ("Linear Motion KF", "x", "vx", "ax", "m", "m/s", "m/s^2"),
    "spring_mass": ("Spring-Mass Motion KF", "x", "vx", "ax", "m", "m/s", "m/s^2"),
    "circular_motion": ("Circular Motion KF", "x", "speed", "|a|", "m", "m/s", "m/s^2"),
}


@dataclass
class EstimatorHistory:
    """Stores time-series data for visualization and export."""

    time: list = field(default_factory=list)
    theta: list = field(default_factory=list)
    omega: list = field(default_factory=list)
    alpha: list = field(default_factory=list)
    theta_std: list = field(default_factory=list)
    omega_std: list = field(default_factory=list)
    gamma: list = field(default_factory=list)
    gamma_std: list = field(default_factory=list)
    innovation: list = field(default_factory=list)
    measured_theta: list = field(default_factory=list)
    numerical_omega: list = field(default_factory=list)
    numerical_alpha: list = field(default_factory=list)

    def clear(self):
        for field_name in self.__dataclass_fields__:
            getattr(self, field_name).clear()


class BaseEstimator:
    """Common interface used by the app."""

    name = "base"
    display_name = "Base Estimator"
    primary_label = "position"
    velocity_label = "velocity"
    acceleration_label = "acceleration"
    primary_unit = ""
    velocity_unit = ""
    acceleration_unit = ""

    def __init__(self, dt: float):
        self.dt = dt
        self.history = EstimatorHistory()

    def update(self, observation: dict) -> dict:
        raise NotImplementedError

    def predict(self):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError

    def estimated_g(self) -> Optional[float]:
        return None

    def csv_headers(self) -> list:
        headers = [
            "time",
            "primary_kalman",
            "velocity_kalman",
            "acceleration_kalman",
            "primary_measured",
            "velocity_numerical",
            "acceleration_numerical",
            "primary_std",
            "velocity_std",
            "innovation",
        ]
        if self.history.gamma:
            headers += ["gamma", "gamma_std"]
        return headers

    def csv_row(self, i: int) -> list:
        h = self.history
        row = [
            f"{h.time[i]:.4f}",
            f"{h.theta[i]:.6f}",
            f"{h.omega[i]:.6f}",
            f"{h.alpha[i]:.6f}",
            f"{h.measured_theta[i]:.6f}",
            f"{h.numerical_omega[i]:.6f}",
            f"{h.numerical_alpha[i]:.6f}",
            f"{h.theta_std[i]:.6f}",
            f"{h.omega_std[i]:.6f}",
            f"{h.innovation[i]:.6f}",
        ]
        if h.gamma:
            row += [f"{h.gamma[i]:.6f}", f"{h.gamma_std[i]:.6f}"]
        return row

    def dashboard_metadata(self) -> dict:
        return {
            "experiment": self.display_name,
            "primary_label": self.primary_label,
            "velocity_label": self.velocity_label,
            "acceleration_label": self.acceleration_label,
            "primary_unit": self.primary_unit,
            "velocity_unit": self.velocity_unit,
            "acceleration_unit": self.acceleration_unit,
        }


class PendulumEstimator(BaseEstimator):
    """Extended Kalman Filter for a damped pendulum."""

    name = "pendulum"
    display_name = "Pendulum EKF"
    primary_label = "theta"
    velocity_label = "omega"
    acceleration_label = "alpha"
    primary_unit = "rad"
    velocity_unit = "rad/s"
    acceleration_unit = "rad/s^2"

    def __init__(
        self,
        dt: float,
        length: float = 0.7,
        gravity: float = 9.81,
        gamma0: float = 0.05,
        augmented: bool = True,
    ):
        super().__init__(dt)
        self.L = length
        self.g = gravity
        self.augmented = augmented
        self.gamma_fixed = gamma0
        self.gamma0 = gamma0
        self._prev_theta = None
        self._prev_omega_num = None
        self._initialized = False
        self.t = 0.0
        self._init_filter()

    def _init_filter(self):
        if self.augmented:
            self.n = 3
            self.x = np.array([0.0, 0.0, self.gamma0])
            self.P = np.diag([0.01, 1.0, 0.5])
            self.Q = np.diag([1e-7, 5e-4, 1e-7])
        else:
            self.n = 2
            self.x = np.array([0.0, 0.0])
            self.P = np.diag([0.01, 1.0])
            self.Q = np.diag([1e-7, 5e-4])
        self.H = np.zeros((1, self.n))
        self.H[0, 0] = 1.0
        self.R = np.array([[5e-4]])

    def _gamma(self, x: np.ndarray) -> float:
        return x[2] if self.augmented else self.gamma_fixed

    def _deriv(self, state: np.ndarray) -> np.ndarray:
        th, om = state[0], state[1]
        gm = self._gamma(state)
        dth = om
        dom = -(self.g / self.L) * np.sin(th) - gm * om
        if self.augmented:
            return np.array([dth, dom, 0.0])
        return np.array([dth, dom])

    def _f(self, x: np.ndarray) -> np.ndarray:
        dt = self.dt
        k1 = self._deriv(x)
        k2 = self._deriv(x + 0.5 * dt * k1)
        k3 = self._deriv(x + 0.5 * dt * k2)
        k4 = self._deriv(x + dt * k3)
        return x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

    def _F_jacobian(self, x: np.ndarray) -> np.ndarray:
        th, om = x[0], x[1]
        gm = self._gamma(x)
        dt = self.dt
        if self.augmented:
            return np.array(
                [
                    [1.0, dt, 0.0],
                    [-(self.g / self.L) * np.cos(th) * dt, 1.0 - gm * dt, -om * dt],
                    [0.0, 0.0, 1.0],
                ]
            )
        return np.array(
            [
                [1.0, dt],
                [-(self.g / self.L) * np.cos(th) * dt, 1.0 - gm * dt],
            ]
        )

    def predict(self):
        F = self._F_jacobian(self.x)
        self.x = self._f(self.x)
        self.P = F @ self.P @ F.T + self.Q

    def update(self, observation: dict) -> dict:
        z_theta = observation["angle"]
        if not self._initialized:
            self.x[0] = z_theta
            self._prev_theta = z_theta
            self._initialized = True

        self.predict()
        z = np.array([z_theta])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + (K @ y).flatten()
        i_kh = np.eye(self.n) - K @ self.H
        self.P = i_kh @ self.P @ i_kh.T + K @ self.R @ K.T

        th = self.x[0]
        om = self.x[1]
        gm = self._gamma(self.x)
        al = -(self.g / self.L) * np.sin(th) - gm * om

        num_omega = 0.0
        num_alpha = 0.0
        if self._prev_theta is not None:
            num_omega = (z_theta - self._prev_theta) / self.dt
        if self._prev_omega_num is not None:
            num_alpha = (num_omega - self._prev_omega_num) / self.dt
        self._prev_theta = z_theta
        self._prev_omega_num = num_omega

        self.t += self.dt
        h = self.history
        h.time.append(self.t)
        h.theta.append(th)
        h.omega.append(om)
        h.alpha.append(al)
        h.theta_std.append(np.sqrt(max(self.P[0, 0], 0)))
        h.omega_std.append(np.sqrt(max(self.P[1, 1], 0)))
        h.innovation.append(float(y[0]))
        h.measured_theta.append(z_theta)
        h.numerical_omega.append(num_omega)
        h.numerical_alpha.append(num_alpha)
        if self.augmented:
            h.gamma.append(self.x[2])
            h.gamma_std.append(np.sqrt(max(self.P[2, 2], 0)))

        return {
            **self.dashboard_metadata(),
            "theta": th,
            "omega": om,
            "alpha": al,
            "gamma": gm,
            "theta_std": h.theta_std[-1],
            "omega_std": h.omega_std[-1],
            "innovation": float(y[0]),
            "num_omega": num_omega,
            "num_alpha": num_alpha,
        }

    def reset(self):
        self._init_filter()
        self.t = 0.0
        self._prev_theta = None
        self._prev_omega_num = None
        self._initialized = False
        self.history.clear()

    def set_length(self, length: float):
        self.L = max(0.1, length)

    def toggle_augmented(self):
        self.augmented = not self.augmented
        self.reset()

    def estimated_g(self) -> Optional[float]:
        ths = np.array(self.history.theta)
        if len(ths) < 60:
            return None
        crossings = np.where(np.diff(np.sign(ths)))[0]
        if len(crossings) < 4:
            return None
        ts = np.array(self.history.time)
        half_periods = np.diff(ts[crossings])
        period = np.mean(half_periods) * 2
        if period <= 0:
            return None
        omega0 = 2 * np.pi / period
        return omega0**2 * self.L


class Motion2DEstimator(BaseEstimator):
    """
    Linear Kalman filter for general 2D motion.

    State: [x, y, vx, vy, ax, ay].
    Observation: [x, y] from the camera tracker.
    Dashboard primary series uses the x-axis components for direct comparison,
    while status also exposes speed, acceleration magnitude, and force magnitude.
    """

    name = "motion2d"
    display_name = "2D Motion KF"
    primary_label = "x"
    velocity_label = "vx"
    acceleration_label = "ax"
    primary_unit = "m"
    velocity_unit = "m/s"
    acceleration_unit = "m/s^2"

    def __init__(
        self,
        dt: float,
        pixels_per_meter: float = 300.0,
        mass: float = 0.05,
        experiment: str = "motion2d",
    ):
        super().__init__(dt)
        display, primary, velocity, acceleration, p_unit, v_unit, a_unit = MOTION_EXPERIMENT_PROFILES.get(
            experiment,
            MOTION_EXPERIMENT_PROFILES["motion2d"],
        )
        self.display_name = display
        self.primary_label = primary
        self.velocity_label = velocity
        self.acceleration_label = acceleration
        self.primary_unit = p_unit
        self.velocity_unit = v_unit
        self.acceleration_unit = a_unit
        self.pixels_per_meter = max(pixels_per_meter, 1e-6)
        self.mass = mass
        self.experiment = experiment
        self.origin_px = None
        self.t = 0.0
        self._prev_x = None
        self._prev_y = None
        self._prev_vx_num = None
        self._prev_vy_num = None
        self._initialized = False
        self._init_filter()

    def _init_filter(self):
        dt = self.dt
        self.x = np.zeros(6)
        self.P = np.diag([0.1, 0.1, 2.0, 2.0, 5.0, 5.0])
        self.F = np.array(
            [
                [1.0, 0.0, dt, 0.0, 0.5 * dt * dt, 0.0],
                [0.0, 1.0, 0.0, dt, 0.0, 0.5 * dt * dt],
                [0.0, 0.0, 1.0, 0.0, dt, 0.0],
                [0.0, 0.0, 0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            ]
        )
        self.H = np.array(
            [
                [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            ]
        )
        self.Q = np.diag([1e-5, 1e-5, 1e-3, 1e-3, 5e-2, 5e-2])
        self.R = np.diag([2e-4, 2e-4])

    def set_origin(self, px: float, py: float):
        self.origin_px = (px, py)

    def set_scale_from_points(self, p1: tuple, p2: tuple, distance_m: float):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist_px = float(np.sqrt(dx * dx + dy * dy))
        if dist_px > 0 and distance_m > 0:
            self.pixels_per_meter = dist_px / distance_m
            self.origin_px = p1

    def _meters_from_pixels(self, px: float, py: float) -> tuple:
        if self.origin_px is None:
            self.origin_px = (px, py)
        ox, oy = self.origin_px
        x_m = (px - ox) / self.pixels_per_meter
        y_m = -(py - oy) / self.pixels_per_meter
        return x_m, y_m

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, observation: dict) -> dict:
        x_m, y_m = self._meters_from_pixels(observation["pixel_x"], observation["pixel_y"])
        if not self._initialized:
            self.x[0] = x_m
            self.x[1] = y_m
            self._prev_x = x_m
            self._prev_y = y_m
            self._initialized = True

        self.predict()
        z = np.array([x_m, y_m])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        i_kh = np.eye(6) - K @ self.H
        self.P = i_kh @ self.P @ i_kh.T + K @ self.R @ K.T

        x, y_pos, vx, vy, ax, ay = self.x
        accel_mag = float(np.sqrt(ax * ax + ay * ay))
        speed = float(np.sqrt(vx * vx + vy * vy))
        force = self.mass * accel_mag

        num_vx = 0.0
        num_ax = 0.0
        num_vy = 0.0
        num_ay = 0.0
        if self._prev_x is not None:
            num_vx = (x_m - self._prev_x) / self.dt
        if self._prev_y is not None:
            num_vy = (y_m - self._prev_y) / self.dt
        if self._prev_vx_num is not None:
            num_ax = (num_vx - self._prev_vx_num) / self.dt
        if self._prev_vy_num is not None:
            num_ay = (num_vy - self._prev_vy_num) / self.dt
        self._prev_x = x_m
        self._prev_y = y_m
        self._prev_vx_num = num_vx
        self._prev_vy_num = num_vy

        self.t += self.dt
        h = self.history
        h.time.append(self.t)
        primary_value = float(y_pos) if self.experiment == "freefall" else float(x)
        velocity_value = float(vy) if self.experiment == "freefall" else float(vx)
        if self.experiment in ("projectile", "circular_motion"):
            velocity_value = speed
        acceleration_value = float(ay) if self.experiment == "freefall" else float(ax)
        if self.experiment in ("projectile", "circular_motion"):
            acceleration_value = accel_mag
        primary_index = 1 if self.experiment == "freefall" else 0
        velocity_index = 3 if self.experiment == "freefall" else 2

        h.theta.append(primary_value)
        h.omega.append(velocity_value)
        h.alpha.append(acceleration_value)
        h.theta_std.append(np.sqrt(max(self.P[primary_index, primary_index], 0)))
        h.omega_std.append(np.sqrt(max(self.P[velocity_index, velocity_index], 0)))
        h.innovation.append(float(np.linalg.norm(y)))
        h.measured_theta.append(float(y_m if self.experiment == "freefall" else x_m))
        h.numerical_omega.append(float(num_vy if self.experiment == "freefall" else num_vx))
        h.numerical_alpha.append(float(num_ay if self.experiment == "freefall" else num_ax))

        return {
            **self.dashboard_metadata(),
            "theta": primary_value,
            "omega": velocity_value,
            "alpha": acceleration_value,
            "theta_std": h.theta_std[-1],
            "omega_std": h.omega_std[-1],
            "innovation": float(np.linalg.norm(y)),
            "num_omega": float(num_vx),
            "num_alpha": float(num_ax),
            "num_vy": float(num_vy),
            "num_ay": float(num_ay),
            "y": float(y_pos),
            "vy": float(vy),
            "ay": float(ay),
            "speed": speed,
            "accel_mag": accel_mag,
            "force": force,
            "mass": self.mass,
            "pixels_per_meter": self.pixels_per_meter,
        }

    def reset(self):
        self._init_filter()
        self.t = 0.0
        self._prev_x = None
        self._prev_y = None
        self._prev_vx_num = None
        self._prev_vy_num = None
        self._initialized = False
        self.history.clear()


def create_estimator(args, dt: float) -> BaseEstimator:
    if args.experiment == "pendulum":
        return PendulumEstimator(
            dt=dt,
            length=args.length,
            gravity=args.gravity,
            gamma0=args.gamma,
            augmented=args.augmented,
        )
    if args.experiment in MOTION_EXPERIMENT_PROFILES:
        return Motion2DEstimator(
            dt=dt,
            pixels_per_meter=args.pixels_per_meter,
            mass=args.mass,
            experiment=args.experiment,
        )
    raise ValueError(f"Unknown experiment: {args.experiment}")
