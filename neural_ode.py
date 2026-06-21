"""
Neural ODE for pendulum dynamics (proposal stage 2).

We learn the continuous-time dynamics of the pendulum as a neural vector field:

    dtheta/dt = omega
    domega/dt = f_NN(theta, omega)        <- learned by an MLP

The kinematic identity dtheta/dt = omega is fixed; only the acceleration
function f is learned, so the network has exactly the structure of a damped
pendulum without being told the physics. Training matches the integrated
trajectory (RK4 via torchdiffeq) to the observed [theta, omega] series.

After training, f_NN is sampled on a (theta, omega) grid and handed to symbolic
regression (stage 3) to recover an explicit equation such as
    domega/dt = -(g/L) sin(theta) - gamma * omega
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from torchdiffeq import odeint


class ODEFunc(nn.Module):
    """Neural vector field. State x = [theta, omega]; learns only d(omega)/dt."""

    def __init__(self, hidden: int = 64, theta_scale: float = 1.0, omega_scale: float = 1.0):
        super().__init__()
        self.ts = theta_scale
        self.os = omega_scale
        self.net = nn.Sequential(
            nn.Linear(2, hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
            nn.Tanh(),
            nn.Linear(hidden, 1),
        )

    def forward(self, t, x):
        theta = x[..., 0:1]
        omega = x[..., 1:2]
        inp = torch.cat([theta / self.ts, omega / self.os], dim=-1)
        domega = self.net(inp).squeeze(-1)
        return torch.stack([omega.squeeze(-1), domega], dim=-1)

    def accel(self, theta, omega):
        """Learned angular acceleration f_NN(theta, omega) (numpy in/out)."""
        with torch.no_grad():
            inp = torch.tensor(
                np.stack([np.asarray(theta) / self.ts, np.asarray(omega) / self.os], axis=-1),
                dtype=torch.float32,
            )
            return self.net(inp).squeeze(-1).numpy()


def train_neural_ode(t, theta, omega, accel=None, accel_weight=25.0, hidden=64,
                     iters=600, window=12, batch=128, lr=5e-3, seed=0, verbose=True):
    """
    Fit the neural vector field to a [theta, omega] trajectory.

    If `accel` (the smoothed angular acceleration omega_dot) is given, an extra
    supervision term anchors the field's d(omega)/dt to it. On noisy / low-fps
    data, trajectory matching alone can converge to a field with the wrong
    coefficient; the acceleration anchor keeps the learned g/L unbiased.
    """
    torch.manual_seed(seed)
    t = np.asarray(t, dtype=np.float64)
    theta = np.asarray(theta, dtype=np.float64)
    omega = np.asarray(omega, dtype=np.float64)

    states = torch.tensor(np.stack([theta, omega], axis=-1), dtype=torch.float32)
    n = len(t)
    dt = float(np.median(np.diff(t)))

    use_accel = accel is not None
    if use_accel:
        accel_t = torch.tensor(np.asarray(accel, dtype=np.float64), dtype=torch.float32)
        accel_var = float(np.var(accel)) + 1e-6

    func = ODEFunc(hidden, theta_scale=max(np.std(theta), 0.1),
                   omega_scale=max(np.std(omega), 0.1))
    opt = torch.optim.Adam(func.parameters(), lr=lr)

    for it in range(1, iters + 1):
        starts = torch.randint(0, n - window, (batch,))
        x0 = states[starts]                                   # (batch, 2)
        tlocal = torch.arange(window, dtype=torch.float32) * dt
        pred = odeint(func, x0, tlocal, method="rk4")         # (window, batch, 2)
        target = torch.stack([states[starts + k] for k in range(window)])
        loss = ((pred - target) ** 2).mean()

        if use_accel:
            idx = torch.randint(0, n, (batch,))
            field = func(0.0, states[idx])                    # [omega, domega/dt]
            loss = loss + accel_weight * ((field[:, 1] - accel_t[idx]) ** 2).mean() / accel_var

        opt.zero_grad()
        loss.backward()
        opt.step()
        if verbose and (it % 100 == 0 or it == 1):
            print(f"  iter {it:4d}  loss {loss.item():.5e}")
    return func


def sample_vector_field(func, theta, omega, n_grid=900, seed=0):
    """Sample f_NN over the data's (theta, omega) region for symbolic regression."""
    rng = np.random.default_rng(seed)
    th = rng.uniform(np.min(theta), np.max(theta), n_grid)
    om = rng.uniform(np.min(omega), np.max(omega), n_grid)
    acc = func.accel(th, om)
    return th, om, acc


def predict_trajectory(func, t, theta0, omega0, max_points=240):
    """Integrate the learned vector field from one initial state for UI validation."""
    t = np.asarray(t, dtype=np.float64)
    if len(t) > max_points:
        idx = np.linspace(0, len(t) - 1, max_points).astype(int)
        t_eval = t[idx]
    else:
        t_eval = t
    tt = torch.tensor(t_eval - t_eval[0], dtype=torch.float32)
    x0 = torch.tensor([[float(theta0), float(omega0)]], dtype=torch.float32)
    with torch.no_grad():
        pred = odeint(func, x0, tt, method="rk4").squeeze(1).cpu().numpy()
    return {
        "t": t_eval.tolist(),
        "pos": pred[:, 0].tolist(),
        "vel": pred[:, 1].tolist(),
    }


# ----------------------------------------------------------------------

def _simulate(g=9.81, L=0.7, gamma=0.25, theta0=0.6, fps=60, duration=10, substeps=12):
    dt = 1.0 / fps
    h = dt / substeps
    n = int(duration * fps)
    t = np.arange(n) * dt
    th = np.zeros(n); om = np.zeros(n)
    s = np.array([theta0, 0.0])

    def deriv(s):
        return np.array([s[1], -(g / L) * np.sin(s[0]) - gamma * s[1]])

    for k in range(n):
        th[k], om[k] = s
        for _ in range(substeps):
            k1 = deriv(s); k2 = deriv(s + 0.5 * h * k1)
            k3 = deriv(s + 0.5 * h * k2); k4 = deriv(s + h * k3)
            s = s + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    return t, th, om


def _self_test():
    g, L, gamma = 9.81, 0.7, 0.25
    t, th, om = _simulate(g=g, L=L, gamma=gamma)
    print("Training Neural ODE on synthetic damped pendulum...")
    func = train_neural_ode(t, th, om, iters=600)

    thg, omg, acc_nn = sample_vector_field(func, th, om)
    acc_true = -(g / L) * np.sin(thg) - gamma * omg
    rmse = np.sqrt(np.mean((acc_nn - acc_true) ** 2))
    amp = np.std(acc_true)
    print("=" * 60)
    print("Neural ODE vector-field recovery (vs true -(g/L)sin - gamma*om)")
    print(f"  true (g/L)={g/L:.3f}  gamma={gamma:.3f}")
    print(f"  vector-field RMSE = {rmse:.4f}  ({100*rmse/amp:.1f}% of signal)")
    # quick linear read of the learned field near small angle: d(acc)/d(omega)
    a0 = func.accel(np.zeros(5), np.linspace(-0.2, 0.2, 5))
    slope_gamma = -np.polyfit(np.linspace(-0.2, 0.2, 5), a0, 1)[0]
    a1 = func.accel(np.linspace(-0.4, 0.4, 5), np.zeros(5))
    slope_gl = -np.polyfit(np.sin(np.linspace(-0.4, 0.4, 5)), a1, 1)[0]
    print(f"  learned damping  ~ {slope_gamma:.3f}  (true {gamma})")
    print(f"  learned g/L      ~ {slope_gl:.3f}  (true {g/L:.3f})")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
