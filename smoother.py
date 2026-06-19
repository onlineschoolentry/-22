"""
Model-free kinematic smoother (constant-acceleration Kalman + RTS).

No physics assumptions. The state is purely kinematic -- position, velocity,
acceleration -- driven by white-noise jerk:

    x = [s, s_dot, s_ddot],   s_dddot ~ white noise

Given a noisy scalar series (e.g. the tracked angle theta), it returns clean
estimates of s, s_dot, s_ddot. This is the preprocessing stage for equation
discovery (SINDy): we need clean derivatives WITHOUT assuming the governing law,
which is exactly why the physics EKF cannot be used here (it would bake in the
answer).

RTS smoothing is offline -- it uses the whole recorded series, running a forward
Kalman pass and then a backward Rauch-Tung-Striebel pass. The backward pass
removes the forward filter's phase lag, so derivatives are unbiased (a plain
forward filter biases s_ddot, which SINDy would then misread as a real term).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class SmoothResult:
    """Smoothed kinematic series plus uncertainties."""

    t: np.ndarray
    measured: np.ndarray
    s: np.ndarray          # smoothed position  (e.g. theta)
    s_dot: np.ndarray      # smoothed velocity  (e.g. omega)
    s_ddot: np.ndarray     # smoothed accel     (e.g. alpha)
    s_std: np.ndarray
    s_dot_std: np.ndarray
    s_ddot_std: np.ndarray
    log_likelihood: float
    q_jerk: float
    sigma_meas: float


def _transition(dt: float) -> np.ndarray:
    """Constant-acceleration state transition over dt."""
    return np.array([
        [1.0, dt, 0.5 * dt * dt],
        [0.0, 1.0, dt],
        [0.0, 0.0, 1.0],
    ])


def _process_noise(dt: float, q: float) -> np.ndarray:
    """Continuous white-noise-jerk process covariance over dt (spectral density q)."""
    dt2 = dt * dt
    dt3 = dt2 * dt
    dt4 = dt3 * dt
    dt5 = dt4 * dt
    return q * np.array([
        [dt5 / 20.0, dt4 / 8.0, dt3 / 6.0],
        [dt4 / 8.0,  dt3 / 3.0, dt2 / 2.0],
        [dt3 / 6.0,  dt2 / 2.0, dt],
    ])


class KinematicSmoother:
    """
    Constant-acceleration Kalman filter + RTS smoother for a 1D noisy series.

    Parameters
    ----------
    sigma_meas : measurement noise std of the observed series (same units as input).
    q_jerk     : spectral density of the white-noise jerk. The smoothing knob:
                 larger -> tracks data more closely (rougher), smaller -> smoother.
                 Prefer `tune_q` over hand-picking it.
    """

    def __init__(self, sigma_meas: float = 0.01, q_jerk: float = 1.0e3):
        self.sigma_meas = float(sigma_meas)
        self.q_jerk = float(q_jerk)

    # ------------------------------------------------------------------

    def _resolve_time(self, z: np.ndarray, t, dt):
        n = len(z)
        if t is not None:
            t = np.asarray(t, dtype=float)
            dts = np.diff(t)
            if np.any(dts <= 0):
                raise ValueError("time vector must be strictly increasing")
        else:
            step = 1.0 if dt is None else float(dt)
            dts = np.full(n - 1, step)
            t = np.arange(n) * step
        return t, dts

    def smooth(self, z, t=None, dt: Optional[float] = None) -> SmoothResult:
        """Run forward KF + backward RTS over the series `z`."""
        z = np.asarray(z, dtype=float)
        n = len(z)
        if n < 3:
            raise ValueError("need at least 3 samples to estimate acceleration")

        t, dts = self._resolve_time(z, t, dt)
        H = np.array([[1.0, 0.0, 0.0]])
        R = self.sigma_meas ** 2

        # Forward pass storage
        x_filt = np.zeros((n, 3))
        P_filt = np.zeros((n, 3, 3))
        x_pred = np.zeros((n, 3))
        P_pred = np.zeros((n, 3, 3))
        F_store = np.zeros((n, 3, 3))  # F_store[k]: transition k -> k+1

        # Diffuse init: trust the first measurement for position, stay open on
        # velocity/acceleration so the filter learns them from the data.
        x = np.array([z[0], 0.0, 0.0])
        P = np.diag([R, 100.0, 1000.0])

        log_lik = 0.0
        for k in range(n):
            if k > 0:
                F = _transition(dts[k - 1])
                Q = _process_noise(dts[k - 1], self.q_jerk)
                x = F @ x
                P = F @ P @ F.T + Q
                F_store[k - 1] = F
            x_pred[k] = x
            P_pred[k] = P

            # Measurement update (scalar)
            innov = z[k] - x[0]
            S = P[0, 0] + R
            K = P[:, 0] / S
            x = x + K * innov
            P = (np.eye(3) - np.outer(K, H[0])) @ P
            x_filt[k] = x
            P_filt[k] = P

            log_lik += -0.5 * (np.log(2.0 * np.pi * S) + innov * innov / S)

        # Backward RTS pass
        x_smooth = x_filt.copy()
        P_smooth = P_filt.copy()
        for k in range(n - 2, -1, -1):
            F = F_store[k]
            A = P_filt[k] @ F.T @ np.linalg.inv(P_pred[k + 1])
            x_smooth[k] = x_filt[k] + A @ (x_smooth[k + 1] - x_pred[k + 1])
            P_smooth[k] = P_filt[k] + A @ (P_smooth[k + 1] - P_pred[k + 1]) @ A.T

        var = np.array([np.diag(P_smooth[k]) for k in range(n)])
        std = np.sqrt(np.clip(var, 0.0, None))

        return SmoothResult(
            t=t,
            measured=z,
            s=x_smooth[:, 0],
            s_dot=x_smooth[:, 1],
            s_ddot=x_smooth[:, 2],
            s_std=std[:, 0],
            s_dot_std=std[:, 1],
            s_ddot_std=std[:, 2],
            log_likelihood=log_lik,
            q_jerk=self.q_jerk,
            sigma_meas=self.sigma_meas,
        )

    def tune_q(self, z, t=None, dt=None, bounds=(1.0e-2, 1.0e8)) -> float:
        """
        Pick q by maximizing the filter's marginal log-likelihood (innovations).

        This is the principled, defensible choice -- no hand-tuning q to make the
        downstream answer look right.
        """
        from scipy.optimize import minimize_scalar

        def neg_ll(log_q: float) -> float:
            smoother = KinematicSmoother(self.sigma_meas, 10.0 ** log_q)
            return -smoother.smooth(z, t=t, dt=dt).log_likelihood

        res = minimize_scalar(
            neg_ll,
            bounds=(np.log10(bounds[0]), np.log10(bounds[1])),
            method="bounded",
        )
        self.q_jerk = float(10.0 ** res.x)
        return self.q_jerk


def estimate_measurement_noise(z) -> float:
    """
    Robust estimate of measurement-noise std from the discrete Laplacian.

    For a smooth signal sampled finely, the second difference is dominated by
    measurement noise; using the MAD makes it robust to the (rare) large true
    curvature. var(2nd diff of white noise) = 6 * sigma^2.
    """
    z = np.asarray(z, dtype=float)
    if len(z) < 3:
        return 0.01
    d2 = z[2:] - 2.0 * z[1:-1] + z[:-2]
    mad = np.median(np.abs(d2 - np.median(d2)))
    sigma_d2 = 1.4826 * mad  # MAD -> std for Gaussian
    return float(sigma_d2 / np.sqrt(6.0)) or 1e-4


def central_difference(z, dt: float):
    """Naive central finite differences (the baseline SINDy preprocessing to beat)."""
    z = np.asarray(z, dtype=float)
    v = np.gradient(z, dt)
    a = np.gradient(v, dt)
    return v, a


# ----------------------------------------------------------------------
# Self-test: synthetic damped pendulum, recover derivatives from noisy angle.
# ----------------------------------------------------------------------

def _simulate_damped_pendulum(g=9.81, L=0.7, gamma=0.25, theta0=0.5,
                              fps=30.0, duration=8.0, substeps=20):
    """Ground-truth integration (fine RK4) of the damped pendulum."""
    dt = 1.0 / fps
    h = dt / substeps

    def deriv(state):
        th, om = state
        return np.array([om, -(g / L) * np.sin(th) - gamma * om])

    n = int(duration * fps)
    t = np.arange(n) * dt
    theta = np.zeros(n)
    omega = np.zeros(n)
    alpha = np.zeros(n)
    s = np.array([theta0, 0.0])
    for k in range(n):
        theta[k] = s[0]
        omega[k] = s[1]
        alpha[k] = -(g / L) * np.sin(s[0]) - gamma * s[1]
        for _ in range(substeps):  # advance one frame with fine substeps
            k1 = deriv(s)
            k2 = deriv(s + 0.5 * h * k1)
            k3 = deriv(s + 0.5 * h * k2)
            k4 = deriv(s + h * k3)
            s = s + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    return t, theta, omega, alpha, dt


def _self_test():
    rng = np.random.default_rng(0)
    t, theta, omega, alpha, dt = _simulate_damped_pendulum()
    noise_std = 0.01  # ~0.57 deg measurement noise on the angle
    z = theta + rng.normal(0.0, noise_std, size=theta.shape)

    sigma_hat = estimate_measurement_noise(z)
    sm = KinematicSmoother(sigma_meas=sigma_hat)
    q = sm.tune_q(z, dt=dt)
    res = sm.smooth(z, dt=dt)

    v_fd, a_fd = central_difference(z, dt)

    def rmse(a, b):
        return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))

    # Drop edges where every method degrades, for a fair interior comparison.
    sl = slice(5, -5)
    print("=" * 60)
    print("  Kinematic smoother self-test (damped pendulum)")
    print("=" * 60)
    print(f"  true measurement noise std : {noise_std:.5f}")
    print(f"  estimated sigma_meas       : {sigma_hat:.5f}")
    print(f"  tuned q_jerk (max-loglik)  : {q:.3e}")
    print("-" * 60)
    print(f"  {'series':<12}{'finite-diff RMSE':>20}{'smoother RMSE':>18}")
    print(f"  {'velocity':<12}{rmse(v_fd[sl], omega[sl]):>20.5f}"
          f"{rmse(res.s_dot[sl], omega[sl]):>18.5f}")
    print(f"  {'accel':<12}{rmse(a_fd[sl], alpha[sl]):>20.5f}"
          f"{rmse(res.s_ddot[sl], alpha[sl]):>18.5f}")
    print(f"  {'position':<12}{rmse(z[sl], theta[sl]):>20.5f}"
          f"{rmse(res.s[sl], theta[sl]):>18.5f}")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
