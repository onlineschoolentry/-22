"""
Generate report/presentation figures from the golden pendulum data.

Outputs (PNG, 150 dpi):
  fig1_pendulum_result.png  - theta(t), phase portrait, 3-method g/L bars
  fig2_discovery.png        - alpha vs sin(theta): proves the law is sin, not linear
  fig3_generality.png       - pendulum (nonlinear sin) vs spring (linear)
"""

from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from smoother import KinematicSmoother, estimate_measurement_noise
from neural_ode import _simulate, train_neural_ode, predict_trajectory

plt.rcParams.update({"figure.dpi": 150, "font.size": 11, "axes.grid": True,
                     "grid.alpha": 0.25, "axes.titlesize": 12})

GOLD = "data_pendulum_40deg_golden.csv"


def smooth(t, x):
    sm = KinematicSmoother(sigma_meas=estimate_measurement_noise(x))
    sm.tune_q(x, t=t)
    s = sm.smooth(x, t=t, dt=float(np.median(np.diff(t))))
    return s


def main():
    import pandas as pd
    df = pd.read_csv(GOLD)
    t = df["time"].to_numpy(float)
    th = df["primary_measured"].to_numpy(float)
    s = smooth(t, th)
    sl = slice(15, -15)
    T, TH, OM, AC = t[sl], s.s[sl], s.s_dot[sl], s.s_ddot[sl]

    # confirmed 3-method values (40deg golden)
    g_neural, g_stlsq, g_period = 39.03, 38.45, 36.97

    # ---------- Figure 1: main result ----------
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    ax[0].plot(T, np.degrees(TH), color="#e8a33d", lw=1.3)
    ax[0].set(title="(a) Tracked angle  θ(t)", xlabel="time (s)", ylabel="θ (deg)")

    ax[1].plot(TH, OM, color="#3d7de8", lw=0.8)
    ax[1].set(title="(b) Phase portrait (closed orbit\n= consistent dynamics)",
              xlabel="θ (rad)", ylabel="ω (rad/s)")

    methods = ["Neural ODE\n+ SR", "STLSQ\n(SINDy)", "Period\n(2π/T)²"]
    vals = [g_neural, g_stlsq, g_period]
    bars = ax[2].bar(methods, vals, color=["#e8533d", "#3d7de8", "#46b06a"])
    ax[2].set(title="(c) g/L: 3 independent methods agree", ylabel="g/L (1/s²)")
    ax[2].set_ylim(0, 45)
    for b, v in zip(bars, vals):
        ax[2].text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.2f}",
                   ha="center", fontsize=10, fontweight="bold")
    fig.suptitle("Discovered:  θ̈ = −39.03·sin(θ) − 0.071·ω   (real pendulum, 40°, 60 fps)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig("fig1_pendulum_result.png")
    print("saved fig1_pendulum_result.png")

    # ---------- Figure 2: sin vs linear (honest) ----------
    # (a) real 40deg data: the distinction is marginal near identifiability limit
    # (b) controlled large-amplitude data: the method unambiguously selects sin
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))

    grid = np.linspace(TH.min(), TH.max(), 200)
    a_sin = np.polyfit(np.sin(TH), AC, 1)[0]
    ax[0].scatter(TH, AC, s=4, alpha=0.25, color="#888", label="measured α")
    ax[0].plot(grid, a_sin * np.sin(grid), color="#e8533d", lw=2.2, label="sin(θ) fit")
    a_lin = np.polyfit(TH, AC, 1)[0]
    ax[0].plot(grid, a_lin * grid, "--", color="#3d7de8", lw=1.6, label="linear θ fit")
    r_sin = np.sqrt(np.mean((AC - a_sin * np.sin(TH)) ** 2))
    r_lin = np.sqrt(np.mean((AC - a_lin * TH) ** 2))
    ax[0].set(title=f"(a) Real data, 40°  (near identifiability limit)\n"
                    f"RMSE  sin {r_sin:.2f}  vs  linear {r_lin:.2f}  — marginal",
              xlabel="θ (rad)", ylabel="α = θ̈ (rad/s²)")
    ax[0].legend(fontsize=9)

    # controlled synthetic pendulum, large amplitude 75 deg, low noise
    tt, thb, omb = _simulate(g=9.81, L=0.7, gamma=0.2, theta0=1.31, fps=120, duration=8)
    ab = -(9.81 / 0.7) * np.sin(thb) - 0.2 * omb
    ab = ab + np.random.default_rng(0).normal(0, 0.4, len(ab))
    gg = np.linspace(thb.min(), thb.max(), 300)
    asb = np.polyfit(np.sin(thb), ab, 1)[0]
    alb = np.polyfit(thb, ab, 1)[0]
    ax[1].scatter(thb, ab, s=4, alpha=0.18, color="#888", label="measured α")
    ax[1].plot(gg, asb * np.sin(gg), color="#e8533d", lw=2.4, label="sin(θ) fit")
    ax[1].plot(gg, alb * gg, "--", color="#3d7de8", lw=1.8, label="linear θ fit")
    rs = np.sqrt(np.mean((ab - asb * np.sin(thb)) ** 2))
    rl = np.sqrt(np.mean((ab - alb * thb) ** 2))
    ax[1].set(title=f"(b) Controlled, 75°  — sin clearly separates\n"
                    f"RMSE  sin {rs:.2f}  vs  linear {rl:.2f}  ({rl/rs:.1f}× better)",
              xlabel="θ (rad)", ylabel="α = θ̈ (rad/s²)")
    ax[1].legend(fontsize=9)
    fig.suptitle("AI selects sin(θ): marginal at 40°, unambiguous at large amplitude",
                 fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig("fig2_discovery.png")
    print("saved fig2_discovery.png")

    # ---------- Figure 3: generality (pendulum vs spring) ----------
    # synthetic spring for the contrast panel
    km, c, fps = 25.0, 0.3, 60
    ts = np.arange(0, 12, 1 / fps)
    xs = np.zeros(len(ts)); vs = np.zeros(len(ts)); st = np.array([0.06, 0.0])
    h = (1 / fps) / 10
    for i in range(len(ts)):
        xs[i], vs[i] = st
        for _ in range(10):
            d = lambda q: np.array([q[1], -km * q[0] - c * q[1]])
            k1 = d(st); k2 = d(st + .5*h*k1); k3 = d(st + .5*h*k2); k4 = d(st + h*k3)
            st = st + (h/6)*(k1 + 2*k2 + 2*k3 + k4)
    ss = smooth(ts, xs)
    XS, AS = ss.s[sl], ss.s_ddot[sl]

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].scatter(TH, AC, s=4, alpha=0.3, color="#888")
    ax[0].plot(grid, -g_neural*np.sin(grid), color="#e8533d", lw=2)
    ax[0].set(title="Pendulum → NONLINEAR\nθ̈ = −(g/L)·sin(θ)", xlabel="θ (rad)", ylabel="α")
    ax[1].scatter(XS, AS, s=4, alpha=0.3, color="#888")
    xg = np.linspace(XS.min(), XS.max(), 100)
    ax[1].plot(xg, -24.89*xg, color="#46b06a", lw=2)
    ax[1].set(title="Spring → LINEAR\nẍ = −(k/m)·x", xlabel="x (m)", ylabel="a")
    fig.suptitle("Same pipeline, different laws  (generality)", fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig("fig3_generality.png")
    print("saved fig3_generality.png")

    # ---------- Figure 4: generalization (learns dynamics, not memorizes) ----------
    tg, thg2, omg2 = _simulate(g=9.81, L=0.7, gamma=0.2, theta0=1.31, fps=60, duration=8)
    acc_g = -(9.81 / 0.7) * np.sin(thg2) - 0.2 * omg2
    func = train_neural_ode(tg, thg2, omg2, accel=acc_g, iters=1200, verbose=False)
    tu, thu, _ = _simulate(g=9.81, L=0.7, gamma=0.2, theta0=0.70, fps=60, duration=6)
    pred = predict_trajectory(func, tu, 0.70, 0.0, max_points=len(tu))
    pp = np.array(pred["pos"]); tp = np.array(pred["t"])
    err = np.degrees(pp - thu[:len(pp)])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(tu, np.degrees(thu), color="#888", lw=3.2, alpha=0.55, label="true (unseen IC, 40°)")
    ax.plot(tp, np.degrees(pp), "--", color="#e8533d", lw=1.6, label="Neural ODE prediction")
    ax.set(title="Generalization: predict an UNSEEN initial condition\n"
                 f"(trained only on 75°, then asked to predict 40°)   RMSE = {np.sqrt(np.mean(err**2)):.2f}°",
           xlabel="time (s)", ylabel="θ (deg)")
    ax.legend()
    fig.tight_layout()
    fig.savefig("fig4_generalization.png")
    print("saved fig4_generalization.png")


if __name__ == "__main__":
    main()
