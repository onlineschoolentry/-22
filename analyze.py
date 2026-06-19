"""
Post-experiment Analysis & Report Figure Generator
Reads CSV data saved from main.py and generates publication-quality figures
for the scientific writing section of the hackathon report.

Usage:
  python analyze.py kalman_data_XXXXXXX.csv
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from scipy import stats

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox_inches": "tight",
})


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    generic_to_legacy = {
        "primary_kalman": "theta_kalman",
        "velocity_kalman": "omega_kalman",
        "acceleration_kalman": "alpha_kalman",
        "primary_measured": "theta_measured",
        "velocity_numerical": "omega_numerical",
        "acceleration_numerical": "alpha_numerical",
        "primary_std": "theta_std",
        "velocity_std": "omega_std",
    }
    for src, dst in generic_to_legacy.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]
    print(f"Loaded {len(df)} frames from {path}")
    return df


def fig1_timeseries_comparison(df: pd.DataFrame):
    """Figure 1: Kalman vs Numerical — θ, ω, α time series comparison."""
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)

    t = df["time"]

    # θ
    ax = axes[0]
    ax.plot(t, np.degrees(df["theta_kalman"]), color="#FF8C00", linewidth=1.2, label="Kalman estimate")
    ax.fill_between(t,
                    np.degrees(df["theta_kalman"] - df["theta_std"]),
                    np.degrees(df["theta_kalman"] + df["theta_std"]),
                    alpha=0.25, color="#FF8C00", label="±1σ uncertainty")
    ax.scatter(t, np.degrees(df["theta_measured"]), s=2, alpha=0.3, color="gray", label="Measurement")
    ax.set_ylabel("θ (degrees)")
    ax.legend(loc="upper right")
    ax.set_title("(a) Angular Position")
    ax.grid(True, alpha=0.3)

    # ω
    ax = axes[1]
    ax.plot(t, df["omega_kalman"], color="#00BFFF", linewidth=1.2, label="Kalman estimate")
    ax.plot(t, df["omega_numerical"], color="#FF4444", linewidth=0.6, alpha=0.6, label="Numerical (Δθ/Δt)")
    ax.set_ylabel("ω (rad/s)")
    ax.legend(loc="upper right")
    ax.set_title("(b) Angular Velocity — Kalman Filter vs Numerical Differentiation")
    ax.grid(True, alpha=0.3)

    # α
    ax = axes[2]
    ax.plot(t, df["alpha_kalman"], color="#44CC44", linewidth=1.2, label="Kalman estimate")
    ax.plot(t, df["alpha_numerical"], color="#FF4444", linewidth=0.6, alpha=0.4, label="Numerical (Δ²θ/Δt²)")
    ax.set_ylabel("α (rad/s²)")
    ax.set_xlabel("Time (s)")
    ax.legend(loc="upper right")
    ax.set_title("(c) Angular Acceleration")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("fig1_timeseries_comparison.png")
    print("Saved: fig1_timeseries_comparison.png")
    plt.close()


def fig2_phase_space(df: pd.DataFrame):
    """Figure 2: Phase space portrait (θ vs ω)."""
    fig, ax = plt.subplots(figsize=(8, 6))

    theta = df["theta_kalman"].values
    omega = df["omega_kalman"].values
    t = df["time"].values

    # Color by time
    sc = ax.scatter(np.degrees(theta), omega, c=t, cmap="viridis",
                    s=3, alpha=0.7)
    plt.colorbar(sc, ax=ax, label="Time (s)")

    ax.set_xlabel("θ (degrees)")
    ax.set_ylabel("ω (rad/s)")
    ax.set_title("Phase Space Portrait — Damped Pendulum")
    ax.axhline(y=0, color="gray", linewidth=0.5)
    ax.axvline(x=0, color="gray", linewidth=0.5)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("fig2_phase_space.png")
    print("Saved: fig2_phase_space.png")
    plt.close()


def fig3_uncertainty_convergence(df: pd.DataFrame):
    """Figure 3: Uncertainty convergence over time."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    t = df["time"]

    axes[0].plot(t, df["theta_std"], color="#FF8C00", linewidth=1)
    axes[0].set_ylabel("σ_θ (rad)")
    axes[0].set_title("(a) Angular Position Uncertainty")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(t, df["omega_std"], color="#00BFFF", linewidth=1)
    axes[1].set_ylabel("σ_ω (rad/s)")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_title("(b) Angular Velocity Uncertainty")
    axes[1].set_yscale("log")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("fig3_uncertainty_convergence.png")
    print("Saved: fig3_uncertainty_convergence.png")
    plt.close()


def fig4_gamma_convergence(df: pd.DataFrame):
    """Figure 4: Damping coefficient estimation convergence."""
    if "gamma" not in df.columns:
        print("Skipping fig4: no gamma data (non-augmented mode)")
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    t = df["time"]
    g = df["gamma"]
    gs = df["gamma_std"]

    ax.plot(t, g, color="#00CCCC", linewidth=1.5, label="γ estimate")
    ax.fill_between(t, g - gs, g + gs, alpha=0.25, color="#00CCCC", label="±1σ")
    ax.axhline(y=g.iloc[-1], color="gray", linewidth=0.5, linestyle="--",
               label=f"Final: {g.iloc[-1]:.5f}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("γ (damping coefficient)")
    ax.set_title("Damping Coefficient Estimation Convergence")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("fig4_gamma_convergence.png")
    print("Saved: fig4_gamma_convergence.png")
    plt.close()


def fig5_innovation_analysis(df: pd.DataFrame):
    """Figure 5: Innovation (residual) analysis for model validation."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    innov = df["innovation"]

    # Time series
    axes[0].plot(df["time"], innov, color="#CC66FF", linewidth=0.5, alpha=0.7)
    axes[0].axhline(y=0, color="gray", linewidth=0.5)
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Innovation (rad)")
    axes[0].set_title("(a) Innovation Sequence")
    axes[0].grid(True, alpha=0.3)

    # Histogram + normality
    axes[1].hist(innov, bins=50, density=True, alpha=0.7, color="#CC66FF")
    mu, std = innov.mean(), innov.std()
    x = np.linspace(innov.min(), innov.max(), 100)
    axes[1].plot(x, stats.norm.pdf(x, mu, std), 'k--', linewidth=1,
                 label=f"N({mu:.4f}, {std:.4f}²)")
    axes[1].set_xlabel("Innovation (rad)")
    axes[1].set_ylabel("Density")
    axes[1].set_title("(b) Innovation Distribution")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Normality test
    if len(innov) > 20:
        _, p_value = stats.shapiro(innov[:5000])  # Shapiro-Wilk (max 5000)
        print(f"Innovation normality test: Shapiro-Wilk p-value = {p_value:.4f}")
        if p_value > 0.05:
            print("  → Innovation is consistent with Gaussian (model is adequate)")
        else:
            print("  → Innovation deviates from Gaussian (model may need refinement)")

    plt.tight_layout()
    plt.savefig("fig5_innovation_analysis.png")
    print("Saved: fig5_innovation_analysis.png")
    plt.close()


def compute_metrics(df: pd.DataFrame):
    """Print quantitative comparison metrics."""
    print("\n" + "=" * 60)
    print("  QUANTITATIVE ANALYSIS")
    print("=" * 60)

    # SNR comparison for ω
    omega_k = df["omega_kalman"].values
    omega_n = df["omega_numerical"].values

    # Use Kalman as reference (smoother)
    if len(omega_k) > 10:
        noise_k = np.diff(omega_k)
        noise_n = np.diff(omega_n)
        snr_k = np.std(omega_k) / max(np.std(noise_k), 1e-10)
        snr_n = np.std(omega_n) / max(np.std(noise_n), 1e-10)
        print(f"\nAngular velocity SNR:")
        print(f"  Kalman filter:     {snr_k:.1f}")
        print(f"  Numerical (Δθ/Δt): {snr_n:.1f}")
        print(f"  Improvement:       {snr_k/max(snr_n, 0.01):.1f}x")

    # α comparison
    alpha_k = df["alpha_kalman"].values
    alpha_n = df["alpha_numerical"].values
    if len(alpha_k) > 10:
        noise_ak = np.diff(alpha_k)
        noise_an = np.diff(alpha_n)
        snr_ak = np.std(alpha_k) / max(np.std(noise_ak), 1e-10)
        snr_an = np.std(alpha_n) / max(np.std(noise_an), 1e-10)
        print(f"\nAngular acceleration SNR:")
        print(f"  Kalman filter:       {snr_ak:.1f}")
        print(f"  Numerical (Δ²θ/Δt²): {snr_an:.1f}")
        print(f"  Improvement:         {snr_ak/max(snr_an, 0.01):.1f}x")

    # γ estimation
    if "gamma" in df.columns:
        gamma_final = df["gamma"].iloc[-1]
        gamma_std_final = df["gamma_std"].iloc[-1]
        print(f"\nDamping coefficient estimation:")
        print(f"  γ = {gamma_final:.6f} ± {gamma_std_final:.6f}")

    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <data.csv>")
        print("  Generates publication-quality figures from experiment data.")
        sys.exit(1)

    path = sys.argv[1]
    df = load_data(path)

    fig1_timeseries_comparison(df)
    fig2_phase_space(df)
    fig3_uncertainty_convergence(df)
    fig4_gamma_convergence(df)
    fig5_innovation_analysis(df)
    compute_metrics(df)

    print("\nAll figures saved. Use in the report's Results section.")


if __name__ == "__main__":
    main()
