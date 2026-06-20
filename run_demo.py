"""
One-command demo: video CSV -> governing equation, with cross-validation figure.

Pipeline (matches proposal):
  tracked theta(t) -> kinematic smoother -> Neural ODE -> GP symbolic regression
  -> explicit equation, plus STLSQ and period-based cross-checks.

Usage:
  python run_demo.py --csv <pendulum_csv>
  python run_demo.py --synthetic
Outputs: console summary + results.png (4-panel presentation figure).
"""

from __future__ import annotations

import argparse

import numpy as np

from smoother import KinematicSmoother, estimate_measurement_noise
from equation_discovery import build_pendulum_library, stlsq
from neural_ode import train_neural_ode, sample_vector_field, _simulate
from discover_pipeline import run_gp_symbolic


def load_states(csv, frac):
    import pandas as pd

    df = pd.read_csv(csv)
    t = df["time"].to_numpy(float)
    th_meas = df["primary_measured"].to_numpy(float)
    cut = int(len(t) * frac)
    t, th_meas = t[:cut], th_meas[:cut]
    dt = float(np.median(np.diff(t)))
    sm = KinematicSmoother(sigma_meas=estimate_measurement_noise(th_meas))
    sm.tune_q(th_meas, t=t)
    s = sm.smooth(th_meas, t=t, dt=dt)
    sl = slice(15, -15)
    return t[sl], th_meas[sl], s.s[sl], s.s_dot[sl], s.s_ddot[sl]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, default=None)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--frac", type=float, default=0.5)
    args = ap.parse_args()

    if args.csv:
        t, theta_meas, theta, omega, accel = load_states(args.csv, args.frac)
        title = "Real pendulum (camera)"
        train_kw = dict(iters=1500, lr=1.5e-3, window=10)
    else:
        t, theta, omega = _simulate(g=9.81, L=0.7, gamma=0.25, theta0=1.0)
        theta_meas = theta + np.random.default_rng(0).normal(0, 0.01, theta.shape)
        accel = np.gradient(omega, t)
        title = "Synthetic pendulum"
        train_kw = dict(iters=600)

    amp = np.degrees(np.max(np.abs(theta - theta.mean())))
    print("=" * 64)
    print(f"  {title}  |  amplitude {amp:.0f} deg  |  {len(theta)} samples")
    print("=" * 64)

    # --- method 1: STLSQ baseline ---
    lib, names = build_pendulum_library(theta, omega)
    r = stlsq(lib, accel, names, lambda_threshold=2.0)
    gl_stlsq = -dict(zip(r.feature_names, r.coefficients)).get("sin(theta)", 0.0)

    # --- method 2: period ---
    x = theta - theta.mean()
    zc = np.where(np.diff(np.sign(x)))[0]
    period = 2 * np.median(np.diff(t[zc])) if len(zc) > 3 else np.nan
    gl_period = (2 * np.pi / period) ** 2 if period > 0 else np.nan

    # --- method 3: Neural ODE + GP-SR ---
    print("[Neural ODE training...]")
    func = train_neural_ode(t, theta, omega, verbose=False, **train_kw)
    thg, omg, acc = sample_vector_field(func, theta, omega, n_grid=600)
    est, coef = run_gp_symbolic(thg, omg, acc)
    gl_node, gamma_node = -coef[0], -coef[1]

    print("\nDISCOVERED:  theta'' = -%.2f * sin(theta) - %.3f * omega" % (gl_node, gamma_node))
    print("\n  g/L cross-validation (3 independent methods):")
    print(f"    Neural ODE + GP-SR : {gl_node:6.2f}")
    print(f"    STLSQ (SINDy)      : {gl_stlsq:6.2f}")
    print(f"    Period  (2pi/T)^2  : {gl_period:6.2f}")
    spread = np.nanstd([gl_node, gl_stlsq, gl_period])
    print(f"    spread (std)       : {spread:6.2f}  ({100*spread/np.nanmean([gl_node,gl_stlsq,gl_period]):.1f}%)")
    print("=" * 64)

    # --- figure ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(2, 2, figsize=(12, 8))
        ax[0, 0].plot(t, theta_meas, color="0.6", lw=0.8, label="measured")
        ax[0, 0].plot(t, theta, "C1", lw=1.6, label="smoothed")
        ax[0, 0].set_title("1. Tracked angle theta(t)")
        ax[0, 0].set_xlabel("time (s)"); ax[0, 0].set_ylabel("theta (rad)"); ax[0, 0].legend()

        TH, OM = np.meshgrid(np.linspace(theta.min(), theta.max(), 20),
                             np.linspace(omega.min(), omega.max(), 20))
        acc_f = func.accel(TH.ravel(), OM.ravel()).reshape(TH.shape)
        ax[0, 1].quiver(TH, OM, OM, acc_f, np.hypot(OM, acc_f), cmap="viridis", scale=None)
        ax[0, 1].plot(theta, omega, "r", lw=1)
        ax[0, 1].set_title("2. Neural ODE learned vector field")
        ax[0, 1].set_xlabel("theta"); ax[0, 1].set_ylabel("omega")

        ax[1, 0].axis("off")
        ax[1, 0].text(0.05, 0.7, "3. Discovered equation", fontsize=13, weight="bold")
        ax[1, 0].text(0.05, 0.45,
                      r"$\ddot\theta = -%.1f\,\sin(\theta) - %.3f\,\omega$" % (gl_node, gamma_node),
                      fontsize=18, color="C3")
        ax[1, 0].text(0.05, 0.2, "(GP symbolic regression on the learned field)", fontsize=10)

        labels = ["Neural ODE\n+ GP-SR", "STLSQ", "Period"]
        vals = [gl_node, gl_stlsq, gl_period]
        ax[1, 1].bar(labels, vals, color=["C3", "C0", "C2"])
        ax[1, 1].set_title("4. g/L cross-validation (3 methods agree)")
        ax[1, 1].set_ylabel("g / L")
        for i, v in enumerate(vals):
            ax[1, 1].text(i, v + 0.5, f"{v:.1f}", ha="center")

        fig.suptitle(f"{title}: data -> Neural ODE -> symbolic equation", fontsize=14)
        fig.tight_layout()
        fig.savefig("results.png", dpi=130)
        print("Saved figure -> results.png")
    except Exception as exc:
        print("(figure skipped:", exc, ")")


if __name__ == "__main__":
    main()
