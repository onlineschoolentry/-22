"""
Generalization check + visualization (proposal expected-effect 3).

Train the Neural ODE on ONE trajectory, then predict trajectories from
*unseen* initial conditions and compare to the true damped pendulum. If the
predictions match, the network learned the dynamics (vector field), not a
memorized trajectory. Also saves a vector-field + trajectory figure.
"""

from __future__ import annotations

import numpy as np
import torch
from torchdiffeq import odeint

from neural_ode import train_neural_ode, _simulate, ODEFunc


def predict(func: ODEFunc, theta0, omega0, t):
    x0 = torch.tensor([theta0, omega0], dtype=torch.float32)
    tt = torch.tensor(t - t[0], dtype=torch.float32)
    with torch.no_grad():
        traj = odeint(func, x0, tt, method="rk4").numpy()
    return traj[:, 0], traj[:, 1]


def main():
    g, L, gamma = 9.81, 0.7, 0.25

    # --- train on a single trajectory (theta0 = 1.0 rad) ---
    t, th, om = _simulate(g=g, L=L, gamma=gamma, theta0=1.0, duration=10)
    print("Training Neural ODE on one trajectory (theta0=1.0)...")
    func = train_neural_ode(t, th, om, iters=600, verbose=False)

    # --- predict UNSEEN initial conditions ---
    print("=" * 60)
    print("Generalization: predict trajectories from UNSEEN initial conditions")
    print(f"  (trained only on theta0=1.0 rad)")
    print("-" * 60)
    tv, _, _ = _simulate(g=g, L=L, gamma=gamma, theta0=1.0, duration=6)
    results = []
    for th0 in [0.4, 0.7, -0.8]:
        _, th_true, om_true = _simulate(g=g, L=L, gamma=gamma, theta0=th0, duration=6)
        th_pred, om_pred = predict(func, th0, 0.0, tv)
        rmse = np.sqrt(np.mean((th_pred - th_true) ** 2))
        print(f"  theta0={th0:+.1f} rad ({np.degrees(th0):+.0f} deg): "
              f"theta(t) prediction RMSE = {rmse:.4f} rad ({np.degrees(rmse):.2f} deg)")
        results.append((th0, tv, th_true, th_pred, om_true, om_pred))
    print("=" * 60)
    print("Low RMSE on unseen ICs => learned the dynamics, not a memorized path.")

    # --- figure: vector field + true vs predicted trajectory ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 2, figsize=(12, 5))

        # (a) learned vector field quiver
        TH, OM = np.meshgrid(np.linspace(-1.2, 1.2, 22), np.linspace(-4, 4, 22))
        acc = func.accel(TH.ravel(), OM.ravel()).reshape(TH.shape)
        ax[0].quiver(TH, OM, OM, acc, np.hypot(OM, acc), cmap="viridis", scale=120)
        th0, tvv, th_t, th_p, om_t, om_p = results[1]
        ax[0].plot(th_t, om_t, "w-", lw=2, label="true (unseen IC)")
        ax[0].plot(th_p, om_p, "r--", lw=2, label="Neural ODE predicted")
        ax[0].set_xlabel("theta (rad)"); ax[0].set_ylabel("omega (rad/s)")
        ax[0].set_title("Learned vector field + phase trajectory"); ax[0].legend()

        # (b) theta(t) true vs predicted for unseen IC
        ax[1].plot(tvv, th_t, "k-", lw=2, label="true")
        ax[1].plot(tvv, th_p, "r--", lw=2, label="Neural ODE predicted")
        ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("theta (rad)")
        ax[1].set_title(f"Prediction on unseen IC (theta0={th0})"); ax[1].legend()

        fig.tight_layout()
        fig.savefig("generalization.png", dpi=130)
        print("Saved figure -> generalization.png")
    except Exception as exc:
        print("(figure skipped:", exc, ")")


if __name__ == "__main__":
    main()
