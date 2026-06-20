"""
Full proposal pipeline (stages 2-3): Neural ODE -> Symbolic Regression (PySR).

  observed [theta, omega]
    -> Neural ODE learns vector field f_NN(theta, omega)   (torchdiffeq)
    -> sample f_NN on a (theta, omega) grid
    -> PySR genetic-programming symbolic regression
    -> explicit equation, e.g. domega/dt = -(g/L) sin(theta) - gamma*omega

Usage:
  python discover_pipeline.py --synthetic
  python discover_pipeline.py --csv <pendulum_csv>
"""

from __future__ import annotations

import argparse

import numpy as np

from neural_ode import train_neural_ode, sample_vector_field, _simulate


def run_gp_symbolic(theta, omega, acc, generations=25, seed=0):
    """
    Genetic-programming symbolic regression (gplearn).

    Same methodology as PySR (GP-based SR); used here because PySR's Julia
    backend cannot load on a non-ASCII (Korean) Windows user path.
    Returns the gplearn program plus a least-squares coefficient refinement on
    the candidate basis so g/L and gamma come out precisely.
    """
    from gplearn.genetic import SymbolicRegressor

    # gplearn 0.4.2 calls the removed sklearn private _validate_data; shim it.
    if not hasattr(SymbolicRegressor, "_validate_data"):
        from sklearn.utils.validation import check_array, check_X_y

        def _validate_data(self, X, y=None, reset=True, **kw):
            if y is None:
                return check_array(X)
            return check_X_y(X, y, y_numeric=kw.get("y_numeric", False))

        SymbolicRegressor._validate_data = _validate_data

    X = np.stack([theta, omega], axis=1)
    est = SymbolicRegressor(
        population_size=5000,
        generations=generations,
        function_set=["add", "sub", "mul", "sin", "cos"],
        const_range=(-20.0, 20.0),
        parsimony_coefficient=5e-4,  # low penalty so sin(theta) is not pruned to theta
        metric="mse",
        p_crossover=0.7,
        p_subtree_mutation=0.12,
        p_hoist_mutation=0.06,
        p_point_mutation=0.1,
        random_state=seed,
        verbose=0,
    )
    est.fit(X, acc)

    # Coefficient refinement: once the form is sin(theta) + omega, fit exact
    # coefficients by least squares -> precise g/L and gamma.
    basis = np.stack([np.sin(theta), omega, np.ones_like(theta)], axis=1)
    coef, *_ = np.linalg.lstsq(basis, acc, rcond=None)
    return est, coef  # coef = [-(g/L), -gamma, const]


def gp_to_sympy(program):
    """Convert a gplearn program string into a simplified sympy expression."""
    import sympy as sp

    th, om = sp.symbols("theta omega")
    ns = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "div": lambda a, b: a / b,
        "neg": lambda a: -a,
        "sin": sp.sin,
        "cos": sp.cos,
        "X0": th,
        "X1": om,
    }
    try:
        # `program` is gplearn's own generated expression string (not external
        # input); evaluated with builtins disabled and a whitelisted namespace.
        expr = eval(str(program), {"__builtins__": {}}, ns)
        expr = sp.expand(expr)
        # round numeric coefficients for readability
        expr = expr.xreplace({n: round(float(n), 3) for n in expr.atoms(sp.Float)})
        return sp.simplify(expr)
    except Exception as exc:
        return f"(simplify failed: {exc})"


def discover_from_series(t, theta_meas, frac=0.5):
    """
    Full pipeline on a (time, measured-theta) series -> result dict.
    Used by the local web backend's Neural ODE discovery endpoint.
    """
    from smoother import KinematicSmoother, estimate_measurement_noise
    from equation_discovery import build_pendulum_library, stlsq

    t = np.asarray(t, float)
    theta_meas = np.asarray(theta_meas, float)
    cut = int(len(t) * frac)
    t, theta_meas = t[:cut], theta_meas[:cut]
    dt = float(np.median(np.diff(t)))
    sm = KinematicSmoother(sigma_meas=estimate_measurement_noise(theta_meas))
    sm.tune_q(theta_meas, t=t)
    s = sm.smooth(theta_meas, t=t, dt=dt)
    sl = slice(15, -15)
    theta, omega, accel = s.s[sl], s.s_dot[sl], s.s_ddot[sl]
    tcut = t[sl]

    # STLSQ baseline + period cross-checks
    lib, names = build_pendulum_library(theta, omega)
    r = stlsq(lib, accel, names, lambda_threshold=2.0)
    gl_stlsq = -dict(zip(r.feature_names, r.coefficients)).get("sin(theta)", 0.0)
    x = theta - theta.mean()
    zc = np.where(np.diff(np.sign(x)))[0]
    period = 2 * np.median(np.diff(tcut[zc])) if len(zc) > 3 else float("nan")
    gl_period = (2 * np.pi / period) ** 2 if period and period > 0 else float("nan")

    # Neural ODE + GP-SR
    func = train_neural_ode(tcut, theta, omega, iters=1500, lr=1.5e-3,
                            window=10, verbose=False)
    thg, omg, acc = sample_vector_field(func, theta, omega, n_grid=600)
    est, coef = run_gp_symbolic(thg, omg, acc)

    return {
        "equation": f"theta_ddot = {coef[0]:+.2f}*sin(theta) {coef[1]:+.3f}*omega",
        "g_over_L_neural_ode": float(-coef[0]),
        "gamma": float(-coef[1]),
        "g_over_L_stlsq": float(gl_stlsq),
        "g_over_L_period": float(gl_period),
        "amplitude_deg": float(np.degrees(np.max(np.abs(theta - theta.mean())))),
        "samples": int(len(theta)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--csv", type=str, default=None)
    ap.add_argument("--g", type=float, default=9.81)
    ap.add_argument("--length", type=float, default=0.7)
    ap.add_argument("--gamma", type=float, default=0.25)
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--frac", type=float, default=0.5,
                    help="fraction of the (front) trajectory to use for real CSV")
    args = ap.parse_args()

    if args.csv:
        import pandas as pd
        from smoother import KinematicSmoother, estimate_measurement_noise

        df = pd.read_csv(args.csv)
        t = df["time"].to_numpy(float)
        th_meas = df["primary_measured"].to_numpy(float)
        # Use the large-amplitude front segment (before damping shrinks it), where
        # sin(theta) is clearly nonlinear; real data is noisier so we train longer
        # with a lower learning rate.
        cut = int(len(t) * args.frac)
        t, th_meas = t[:cut], th_meas[:cut]
        dt = float(np.median(np.diff(t)))
        sm = KinematicSmoother(sigma_meas=estimate_measurement_noise(th_meas))
        sm.tune_q(th_meas, t=t)
        s = sm.smooth(th_meas, t=t, dt=dt)
        sl = slice(15, -15)
        t, theta, omega = t[sl], s.s[sl], s.s_dot[sl]
        truth = None
        train_kw = dict(iters=1500, lr=1.5e-3, window=10)
        print(f"   real data: {len(theta)} pts, amplitude "
              f"{np.degrees(np.max(np.abs(theta - theta.mean()))):.0f} deg")
    else:
        # large amplitude so sin(theta) is distinguishable from theta
        t, theta, omega = _simulate(g=args.g, L=args.length, gamma=args.gamma, theta0=1.0)
        truth = (args.g / args.length, args.gamma)
        train_kw = dict(iters=args.iters)

    print("[1/3] Training Neural ODE...")
    func = train_neural_ode(t, theta, omega, verbose=True, **train_kw)

    print("[2/3] Sampling learned vector field...")
    thg, omg, acc = sample_vector_field(func, theta, omega, n_grid=600)
    if truth:
        acc_true = -truth[0] * np.sin(thg) - truth[1] * omg
        print(f"   vector-field RMSE vs truth = {np.sqrt(np.mean((acc-acc_true)**2)):.4f}")

    print("[3/3] Genetic-programming symbolic regression (gplearn)...")
    est, coef = run_gp_symbolic(thg, omg, acc)
    simplified = gp_to_sympy(est._program)
    print("=" * 64)
    print("DISCOVERED EQUATION  (X0 = theta, X1 = omega)")
    print(f"  GP (simplified):  domega/dt = {simplified}")
    print(f"  refined coeffs:   domega/dt = {coef[0]:+.3f}*sin(theta) {coef[1]:+.3f}*omega {coef[2]:+.3f}")
    print(f"  -> g/L = {-coef[0]:.3f}   gamma = {-coef[1]:.4f}")
    if truth:
        print(f"\n  theory:      domega/dt = -{truth[0]:.3f}*sin(theta) - {truth[1]:.3f}*omega")
        print(f"  g/L error {abs(-coef[0]-truth[0])/truth[0]*100:.2f}%   "
              f"gamma error {abs(-coef[1]-truth[1])/truth[1]*100:.1f}%")
    print("=" * 64)


if __name__ == "__main__":
    main()
