"""
Extended Kalman Filter for Damped Pendulum System
Supports 2-state (θ, ω) and 3-state augmented (θ, ω, γ) estimation.

State equations:
  dθ/dt = ω
  dω/dt = -(g/L)·sin(θ) - γ·ω
  dγ/dt = 0  (augmented: treat damping as constant unknown)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EKFHistory:
    """Stores time-series data for visualization."""
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
        for f in self.__dataclass_fields__:
            getattr(self, f).clear()


class PendulumEKF:
    """
    Extended Kalman Filter for a damped pendulum.

    Augmented mode estimates the damping coefficient γ alongside θ and ω,
    enabling the system to *discover* the damping parameter from data alone.
    """

    def __init__(
        self,
        L: float = 0.7,
        g: float = 9.81,
        gamma0: float = 0.05,
        dt: float = 1 / 30,
        augmented: bool = True,
    ):
        self.L = L
        self.g = g
        self.dt = dt
        self.augmented = augmented
        self.gamma_fixed = gamma0

        # --- State & covariance ---
        if augmented:
            self.n = 3
            self.x = np.array([0.0, 0.0, gamma0])
            self.P = np.diag([0.01, 1.0, 0.5])
            self.Q = np.diag([1e-7, 5e-4, 1e-7])
        else:
            self.n = 2
            self.x = np.array([0.0, 0.0])
            self.P = np.diag([0.01, 1.0])
            self.Q = np.diag([1e-7, 5e-4])

        # Observation: we only measure θ
        self.H = np.zeros((1, self.n))
        self.H[0, 0] = 1.0
        self.R = np.array([[5e-4]])  # ~0.02 rad std

        self.history = EKFHistory()
        self.t = 0.0
        self._prev_theta = None
        self._prev_omega_num = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Core EKF
    # ------------------------------------------------------------------

    def _gamma(self, x: np.ndarray) -> float:
        return x[2] if self.augmented else self.gamma_fixed

    def _deriv(self, state: np.ndarray) -> np.ndarray:
        """Compute time derivative of state (continuous dynamics)."""
        th, om = state[0], state[1]
        gm = self._gamma(state)
        g, L = self.g, self.L
        dth = om
        dom = -(g / L) * np.sin(th) - gm * om
        if self.augmented:
            return np.array([dth, dom, 0.0])
        return np.array([dth, dom])

    def _f(self, x: np.ndarray) -> np.ndarray:
        """Nonlinear state transition using RK4 integration."""
        dt = self.dt
        k1 = self._deriv(x)
        k2 = self._deriv(x + 0.5 * dt * k1)
        k3 = self._deriv(x + 0.5 * dt * k2)
        k4 = self._deriv(x + dt * k3)
        return x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

    def _F_jacobian(self, x: np.ndarray) -> np.ndarray:
        """Jacobian of state transition at x."""
        th, om = x[0], x[1]
        gm = self._gamma(x)
        dt = self.dt
        g, L = self.g, self.L

        if self.augmented:
            return np.array([
                [1.0, dt, 0.0],
                [-(g / L) * np.cos(th) * dt, 1.0 - gm * dt, -om * dt],
                [0.0, 0.0, 1.0],
            ])
        return np.array([
            [1.0, dt],
            [-(g / L) * np.cos(th) * dt, 1.0 - gm * dt],
        ])

    def predict(self):
        """EKF prediction step."""
        F = self._F_jacobian(self.x)
        self.x = self._f(self.x)
        self.P = F @ self.P @ F.T + self.Q

    def update(self, z_theta: float) -> dict:
        """
        EKF update step with angle measurement.

        Returns dict with current estimates and uncertainties.
        """
        if not self._initialized:
            self.x[0] = z_theta
            self._prev_theta = z_theta
            self._initialized = True

        # --- Predict ---
        self.predict()

        # --- Update ---
        z = np.array([z_theta])
        y = z - self.H @ self.x                        # innovation
        S = self.H @ self.P @ self.H.T + self.R        # innovation cov
        K = self.P @ self.H.T @ np.linalg.inv(S)       # Kalman gain

        self.x = self.x + (K @ y).flatten()
        I_KH = np.eye(self.n) - K @ self.H
        # Joseph form for numerical stability
        self.P = I_KH @ self.P @ I_KH.T + K @ self.R @ K.T

        # --- Derived quantities ---
        th = self.x[0]
        om = self.x[1]
        gm = self._gamma(self.x)
        al = -(self.g / self.L) * np.sin(th) - gm * om

        # --- Numerical differentiation for comparison ---
        num_omega = 0.0
        num_alpha = 0.0
        if self._prev_theta is not None:
            num_omega = (z_theta - self._prev_theta) / self.dt
        if self._prev_omega_num is not None:
            num_alpha = (num_omega - self._prev_omega_num) / self.dt

        self._prev_theta = z_theta
        self._prev_omega_num = num_omega

        # --- Record history ---
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
            "theta": th, "omega": om, "alpha": al,
            "gamma": gm,
            "theta_std": h.theta_std[-1],
            "omega_std": h.omega_std[-1],
            "innovation": float(y[0]),
            "num_omega": num_omega,
            "num_alpha": num_alpha,
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def reset(self, theta0: float = 0.0, gamma0: float = 0.05):
        """Reset filter to initial state."""
        if self.augmented:
            self.x = np.array([theta0, 0.0, gamma0])
            self.P = np.diag([0.01, 1.0, 0.5])
        else:
            self.x = np.array([theta0, 0.0])
            self.P = np.diag([0.01, 1.0])
        self.t = 0.0
        self._prev_theta = None
        self._prev_omega_num = None
        self._initialized = False
        self.history.clear()

    def set_params(self, L: float = None, g: float = None, gamma: float = None):
        """Update physical parameters."""
        if L is not None:
            self.L = L
        if g is not None:
            self.g = g
        if gamma is not None:
            self.gamma_fixed = gamma
            if self.augmented:
                self.x[2] = gamma

    def estimated_g(self) -> Optional[float]:
        """Estimate g from oscillation data if enough cycles exist."""
        ths = np.array(self.history.theta)
        if len(ths) < 60:
            return None
        # Find zero crossings to estimate period
        crossings = np.where(np.diff(np.sign(ths)))[0]
        if len(crossings) < 4:
            return None
        ts = np.array(self.history.time)
        half_periods = np.diff(ts[crossings])
        T = np.mean(half_periods) * 2
        if T <= 0:
            return None
        omega0 = 2 * np.pi / T
        return omega0 ** 2 * self.L
