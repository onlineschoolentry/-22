"""
관측 시계열에서 지배 방정식을 산출하는 최소 구현.

핵심은 STLSQ(Sequential Thresholded Least Squares)를 직접 구현하는 것이다.
최소자승으로 계수를 구하고, 임계값보다 작은 계수를 0으로 밀어낸 뒤,
남은 항만으로 다시 최소자승을 푸는 과정을 반복한다.

기본 사용:
  python equation_discovery.py --synthetic
  python equation_discovery.py --csv pendulum_kalman_data_XXXXXXXXXX.csv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from smoother import KinematicSmoother, estimate_measurement_noise


@dataclass
class STLSQResult:
    """STLSQ 산출 결과와 검증 지표."""

    coefficients: np.ndarray
    active: np.ndarray
    feature_names: list[str]
    lambda_threshold: float
    train_rmse: float
    test_rmse: float
    iterations: int

    def equation(self, target_name: str = "theta_ddot") -> str:
        terms = []
        for coef, name in zip(self.coefficients, self.feature_names):
            if abs(coef) < 1e-12:
                continue
            terms.append(f"{coef:+.6g}*{name}")
        rhs = " ".join(terms).lstrip("+") if terms else "0"
        return f"{target_name} = {rhs}"


def simulate_damped_pendulum(
    g: float = 9.81,
    length: float = 0.7,
    gamma: float = 0.25,
    theta0: float = 0.55,
    omega0: float = 0.0,
    fps: float = 60.0,
    duration: float = 12.0,
    substeps: int = 12,
) -> dict[str, np.ndarray | float]:
    """합성 감쇠진자 데이터를 RK4로 생성한다."""
    dt = 1.0 / fps
    h = dt / substeps
    n = int(duration * fps)
    t = np.arange(n) * dt
    theta = np.zeros(n)
    omega = np.zeros(n)
    alpha = np.zeros(n)
    state = np.array([theta0, omega0], dtype=float)

    def deriv(s: np.ndarray) -> np.ndarray:
        th, om = s
        return np.array([om, -(g / length) * np.sin(th) - gamma * om])

    for k in range(n):
        theta[k] = state[0]
        omega[k] = state[1]
        alpha[k] = deriv(state)[1]
        for _ in range(substeps):
            k1 = deriv(state)
            k2 = deriv(state + 0.5 * h * k1)
            k3 = deriv(state + 0.5 * h * k2)
            k4 = deriv(state + h * k3)
            state = state + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

    return {
        "t": t,
        "theta": theta,
        "omega": omega,
        "alpha": alpha,
        "g": g,
        "length": length,
        "gamma": gamma,
    }


def build_pendulum_library(theta: np.ndarray, omega: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    진자 방정식 후보항 라이브러리.

    실제 기대식은 theta_ddot = -(g/L) sin(theta) - gamma omega 이다.
    상수항, 감쇠항, 복원력 후보항, 약한 비선형 잡음항만 둔다.
    cos(theta)나 theta^2는 작은 각도에서 상수항과 강하게 공선적이라
    MVP 검증용 라이브러리에서는 제외한다.
    """
    theta = np.asarray(theta, dtype=float)
    omega = np.asarray(omega, dtype=float)
    features = [
        np.ones_like(theta),
        omega,
        np.sin(theta),
        theta * omega,
        omega * omega,
    ]
    names = ["1", "omega", "sin(theta)", "theta*omega", "omega^2"]
    return np.column_stack(features), names


def build_oscillator_library(x: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    1D 진동(용수철 등) 후보항 라이브러리.
    기대식: x_ddot = -(k/m) x - c v  (선형 복원). 비선형 후보(x^2, x^3)도 둬서
    데이터가 선형 x를 고르는지 확인.
    """
    x = np.asarray(x, dtype=float)
    v = np.asarray(v, dtype=float)
    features = [np.ones_like(x), x, x * x, x * x * x, v, x * v]
    names = ["1", "x", "x^2", "x^3", "v", "x*v"]
    return np.column_stack(features), names


def stlsq(
    theta_lib: np.ndarray,
    target: np.ndarray,
    feature_names: Iterable[str],
    lambda_threshold: float = 0.3,
    max_iter: int = 12,
    train_fraction: float = 0.7,
) -> STLSQResult:
    """
    직접 구현한 STLSQ.

    1. 후보항 행렬을 열 크기로 정규화한다.
    2. train 구간에서 최소자승을 푼다.
    3. abs(coef) < lambda 인 항을 제거한다.
    4. 활성 항만으로 다시 푼다.
    """
    theta_lib = np.asarray(theta_lib, dtype=float)
    target = np.asarray(target, dtype=float)
    names = list(feature_names)
    if theta_lib.ndim != 2:
        raise ValueError("theta_lib must be a 2D matrix")
    if theta_lib.shape[0] != target.shape[0]:
        raise ValueError("theta_lib and target must have the same row count")
    if theta_lib.shape[1] != len(names):
        raise ValueError("feature_names length must match theta_lib columns")

    n = len(target)
    split = int(n * train_fraction)
    split = min(max(split, theta_lib.shape[1] + 1), n - 1)
    x_train = theta_lib[:split]
    y_train = target[:split]
    x_test = theta_lib[split:]
    y_test = target[split:]

    scales = np.linalg.norm(x_train, axis=0)
    scales[scales == 0.0] = 1.0
    x_train_n = x_train / scales
    x_test_n = x_test / scales

    active = np.ones(theta_lib.shape[1], dtype=bool)
    coef_n = np.zeros(theta_lib.shape[1])
    iterations = 0

    for iterations in range(1, max_iter + 1):
        prev_active = active.copy()
        coef_n[:] = 0.0
        coef_active, *_ = np.linalg.lstsq(x_train_n[:, active], y_train, rcond=None)
        coef_n[active] = coef_active
        small = np.abs(coef_n) < lambda_threshold
        active = active & ~small
        if not active.any():
            strongest = int(np.argmax(np.abs(coef_n)))
            active[strongest] = True
        if np.array_equal(active, prev_active):
            break

    coef_n[:] = 0.0
    coef_active, *_ = np.linalg.lstsq(x_train_n[:, active], y_train, rcond=None)
    coef_n[active] = coef_active
    coefficients = coef_n / scales

    train_pred = x_train @ coefficients
    test_pred = x_test @ coefficients
    train_rmse = rmse(train_pred, y_train)
    test_rmse = rmse(test_pred, y_test)

    return STLSQResult(
        coefficients=coefficients,
        active=active,
        feature_names=names,
        lambda_threshold=lambda_threshold,
        train_rmse=train_rmse,
        test_rmse=test_rmse,
        iterations=iterations,
    )


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    """RMSE 계산."""
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def fit_pendulum_equation(
    t: np.ndarray,
    measured_theta: np.ndarray,
    lambda_threshold: float,
    edge_drop: int = 12,
) -> tuple[STLSQResult, object]:
    """관측 theta에서 smoother를 거쳐 진자 지배 방정식을 산출한다."""
    dt = float(np.median(np.diff(t)))
    sigma = estimate_measurement_noise(measured_theta)
    smoother = KinematicSmoother(sigma_meas=sigma)
    smoother.tune_q(measured_theta, t=t)
    smooth = smoother.smooth(measured_theta, t=t, dt=dt)

    sl = slice(edge_drop, -edge_drop if edge_drop else None)
    theta_lib, names = build_pendulum_library(smooth.s[sl], smooth.s_dot[sl])
    result = stlsq(theta_lib, smooth.s_ddot[sl], names, lambda_threshold=lambda_threshold)
    return result, smooth


def run_synthetic(args) -> None:
    """합성 데이터로 관측 -> smoothing -> STLSQ -> 이론식 비교 루프를 닫는다."""
    truth = simulate_damped_pendulum(
        g=args.gravity,
        length=args.length,
        gamma=args.gamma,
        theta0=args.theta0,
        fps=args.fps,
        duration=args.duration,
    )
    rng = np.random.default_rng(args.seed)
    theta = truth["theta"]
    measured = theta + rng.normal(0.0, args.noise_std, size=theta.shape)

    result, smooth = fit_pendulum_equation(
        np.asarray(truth["t"]),
        measured,
        lambda_threshold=args.lambda_threshold,
        edge_drop=args.edge_drop,
    )
    true_sin = -args.gravity / args.length
    true_omega = -args.gamma

    print("=" * 72)
    print("합성 감쇠진자 STLSQ 방정식 산출")
    print("=" * 72)
    print(f"입력 노이즈 std        : {args.noise_std:.5f} rad")
    print(f"smoother sigma_hat     : {smooth.sigma_meas:.5f}")
    print(f"smoother q_jerk        : {smooth.q_jerk:.3e}")
    print(f"STLSQ lambda           : {args.lambda_threshold:.4f}")
    print(f"반복 횟수              : {result.iterations}")
    print("-" * 72)
    print(result.equation())
    print("-" * 72)
    print(f"이론 계수 sin(theta)   : {true_sin:+.6f}")
    print(f"이론 계수 omega        : {true_omega:+.6f}")
    print(f"train RMSE             : {result.train_rmse:.6f}")
    print(f"test RMSE              : {result.test_rmse:.6f}")
    print("-" * 72)
    print("lambda sweep")
    for lam in args.sweep:
        theta_lib, names = build_pendulum_library(
            smooth.s[args.edge_drop:-args.edge_drop],
            smooth.s_dot[args.edge_drop:-args.edge_drop],
        )
        sweep = stlsq(theta_lib, smooth.s_ddot[args.edge_drop:-args.edge_drop], names, lambda_threshold=lam)
        active_names = [name for name, is_active in zip(sweep.feature_names, sweep.active) if is_active]
        print(f"  lambda={lam:<6g} terms={active_names} test_rmse={sweep.test_rmse:.6f}")
    print("=" * 72)
    maybe_validate_with_pysindy(smooth, args.edge_drop)


def run_csv(args) -> None:
    """실험 CSV에서 theta 관측열을 읽어 방정식을 산출한다."""
    path = Path(args.csv)
    df = pd.read_csv(path)
    if "time" not in df.columns:
        raise ValueError("CSV must contain a time column")
    theta_col = pick_first_column(df, ["theta_measured", "primary_measured", "theta_kalman", "primary_kalman"])
    t = df["time"].to_numpy(dtype=float)
    measured = df[theta_col].to_numpy(dtype=float)
    result, smooth = fit_pendulum_equation(t, measured, args.lambda_threshold, args.edge_drop)

    print("=" * 72)
    print("CSV 기반 STLSQ 방정식 산출")
    print("=" * 72)
    print(f"file                   : {path}")
    print(f"theta column           : {theta_col}")
    print(f"smoother sigma_hat     : {smooth.sigma_meas:.5f}")
    print(f"smoother q_jerk        : {smooth.q_jerk:.3e}")
    print(f"STLSQ lambda           : {args.lambda_threshold:.4f}")
    print("-" * 72)
    print(result.equation())
    print("-" * 72)
    print(f"train RMSE             : {result.train_rmse:.6f}")
    print(f"test RMSE              : {result.test_rmse:.6f}")
    print("=" * 72)
    maybe_validate_with_pysindy(smooth, args.edge_drop)


def pick_first_column(df: pd.DataFrame, candidates: list[str]) -> str:
    """후보 중 실제 존재하는 첫 컬럼명을 고른다."""
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(f"CSV must contain one of these columns: {', '.join(candidates)}")


def maybe_validate_with_pysindy(smooth, edge_drop: int) -> None:
    """PySINDy가 설치된 경우에만 참고 검증을 수행한다."""
    try:
        import pysindy as ps  # type: ignore
    except Exception:
        print("PySINDy 검증: pysindy 미설치라 건너뜀")
        return

    sl = slice(edge_drop, -edge_drop if edge_drop else None)
    x = np.column_stack([smooth.s[sl], smooth.s_dot[sl]])
    x_dot = np.column_stack([smooth.s_dot[sl], smooth.s_ddot[sl]])
    library = ps.CustomLibrary(
        library_functions=[
            lambda x: x,
            lambda x: np.sin(x),
        ],
        function_names=[
            lambda x: x,
            lambda x: f"sin({x})",
        ],
    )
    model = ps.SINDy(
        feature_library=library,
        optimizer=ps.STLSQ(threshold=0.08),
        feature_names=["theta", "omega"],
    )
    model.fit(x, x_dot=x_dot)
    print("PySINDy 검증:")
    model.print()


def parse_args():
    parser = argparse.ArgumentParser(description="직접 구현 STLSQ 기반 방정식 산출")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--synthetic", action="store_true", help="합성 감쇠진자 데이터로 end-to-end 검증")
    mode.add_argument("--csv", type=str, help="실험 CSV로 방정식 산출")
    parser.add_argument("--lambda-threshold", type=float, default=0.3, help="STLSQ 희소화 임계값")
    parser.add_argument("--sweep", type=float, nargs="*", default=[0.01, 0.03, 0.08, 0.15, 0.3, 0.6])
    parser.add_argument("--edge-drop", type=int, default=12, help="smoother 경계부 샘플 제거 개수")
    parser.add_argument("--gravity", type=float, default=9.81)
    parser.add_argument("--length", type=float, default=0.7)
    parser.add_argument("--gamma", type=float, default=0.25)
    parser.add_argument("--theta0", type=float, default=0.55)
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--duration", type=float, default=12.0)
    parser.add_argument("--noise-std", type=float, default=0.002)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.csv:
        run_csv(args)
    else:
        run_synthetic(args)


if __name__ == "__main__":
    main()
