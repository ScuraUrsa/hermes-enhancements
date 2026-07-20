"""
Transforms Demo — Laplace, Fourier, Bode, Convolution.

Generates comprehensive plots to output/:
- Laplace transform pairs
- FFT of synthetic signals
- Bode plots for transfer functions
- Convolution visualization
- Spectrogram
- Filter design & application
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from transforms import Transforms

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

tr = Transforms()


def demo_laplace():
    """Demonstrate symbolic Laplace transforms."""
    print("\n--- 1. Laplace Transform ---")

    transforms = [
        ("sin(t)", "sin(t)"),
        ("cos(t)", "cos(t)"),
        ("exp(-a*t)", "exp(-a*t)"),
        ("t**2", "t²"),
        ("t*exp(-t)", "t·e⁻ᵗ"),
        ("Heaviside(t)", "u(t) (step)"),
        ("DiracDelta(t)", "δ(t) (impulse)"),
    ]

    results = []
    for expr, name in transforms:
        r = tr.laplace_transform(expr)
        if r.success:
            results.append((name, r.result["F_s"]))
            print(f"  L{{{name}}} = {r.result['F_s']}")
        else:
            print(f"  L{{{name}}}: {r.error}")

    # Inverse Laplace
    inv_tests = [
        ("1/(s**2 + 1)", "1/(s²+1)"),
        ("1/s**2", "1/s²"),
        ("1/(s + a)", "1/(s+a)"),
    ]
    for expr, name in inv_tests:
        r = tr.inverse_laplace_transform(expr)
        if r.success:
            print(f"  L⁻¹{{{name}}} = {r.result['f_t']}")

    return results


def demo_fourier():
    """Demonstrate FFT on synthetic signals."""
    print("\n--- 2. Fourier Transform (FFT) ---")

    # Signal 1: sum of sinusoids
    dt = 0.01
    t = np.arange(0, 2, dt)
    f1, f2, f3 = 5, 15, 30  # Hz
    signal1 = np.sin(2 * np.pi * f1 * t) + 0.5 * np.sin(2 * np.pi * f2 * t) + 0.3 * np.sin(2 * np.pi * f3 * t)

    r1 = tr.fourier_transform(signal1, dt=dt)
    freqs1 = np.array(r1.result["frequencies"])
    mag1 = np.array(r1.result["magnitude"])

    # Find peaks
    peak_indices = np.argsort(mag1)[-5:]
    peaks = [(freqs1[i], mag1[i]) for i in peak_indices if freqs1[i] < 50]
    print(f"  Signal: sin(2π·5t) + 0.5·sin(2π·15t) + 0.3·sin(2π·30t)")
    print(f"  Detected peaks: {[(f'{f:.1f} Hz', f'{m:.2f}') for f, m in sorted(peaks)]}")

    # Signal 2: square wave
    square = scipy_signal_square(t)
    r2 = tr.fourier_transform(square, dt=dt)
    freqs2 = np.array(r2.result["frequencies"])
    mag2 = np.array(r2.result["magnitude"])

    # Signal 3: chirp
    chirp = scipy_signal_chirp(t)
    r3 = tr.spectrogram(chirp, fs=1/dt, nperseg=128, noverlap=64)

    return t, signal1, freqs1, mag1, square, freqs2, mag2, chirp, r3


def demo_bode():
    """Demonstrate Bode plots for transfer functions."""
    print("\n--- 3. Bode Plots & Transfer Functions ---")

    systems = [
        ("Low-pass 1st order", [1], [1, 1], "1/(s+1)"),
        ("Low-pass 2nd order", [1], [1, 1.4, 1], "1/(s²+1.4s+1)"),
        ("High-pass", [1, 0], [1, 1], "s/(s+1)"),
        ("Band-pass", [1, 0], [1, 1, 1], "s/(s²+s+1)"),
    ]

    bode_results = []
    for name, num, den, desc in systems:
        r = tr.bode(num, den, freq_range=(0.01, 100), n_freqs=300)
        if r.success:
            bode_results.append((name, desc, r))
            # Find -3dB point
            mag = np.array(r.result["magnitude_dB"])
            freqs = np.array(r.result["frequencies_hz"])
            # DC gain
            dc_gain = mag[0]
            print(f"  {name} ({desc}): DC gain = {dc_gain:.1f} dB")

        # Step response
        r_step = tr.step_response(num, den, t_end=10)
        if r_step.success:
            bode_results.append((f"{name} (step)", desc, r_step))

    return bode_results


def demo_convolution():
    """Demonstrate convolution."""
    print("\n--- 4. Convolution ---")

    r = tr.convolution_demo_signals(n=300)
    t = np.array(r.result["t"])
    a = np.array(r.result["signal_a"])
    b = np.array(r.result["signal_b"])
    t_conv = np.array(r.result["t_conv"])
    conv = np.array(r.result["convolution"])

    print(f"  Signal A: square pulse [1, 3]")
    print(f"  Signal B: exp(-t)")
    print(f"  Convolution length: {len(conv)}")

    # Also test manual convolution
    r2 = tr.convolve([1, 2, 3], [4, 5, 6], mode="full")
    print(f"  [1,2,3] * [4,5,6] = {r2.result}")

    return t, a, b, t_conv, conv


def demo_filter():
    """Demonstrate filter design and application."""
    print("\n--- 5. Filter Design ---")

    # Design low-pass filter
    r_lp = tr.design_filter("lowpass", order=4, cutoff=10, fs=100)
    print(f"  Low-pass Butterworth (order=4, fc=10Hz, fs=100Hz)")
    print(f"  b = {[f'{x:.4f}' for x in r_lp.result['b'][:4]]}...")
    print(f"  a = {[f'{x:.4f}' for x in r_lp.result['a'][:4]]}...")

    # Generate noisy signal and filter it
    dt = 0.01
    t = np.arange(0, 2, dt)
    clean = np.sin(2 * np.pi * 3 * t)  # 3 Hz signal
    noise = 0.5 * np.sin(2 * np.pi * 40 * t)  # 40 Hz noise
    noisy = clean + noise

    r_filt = tr.apply_filter(noisy, r_lp.result["b"], r_lp.result["a"])
    filtered = np.array(r_filt.result)

    # FFT of before/after
    r_fft_noisy = tr.fourier_transform(noisy, dt=dt)
    r_fft_clean = tr.fourier_transform(filtered, dt=dt)

    print(f"  Applied low-pass filter: removed 40 Hz noise")

    return t, clean, noisy, filtered, r_fft_noisy, r_fft_clean, r_lp


# ---- Helpers for signal generation ----

def scipy_signal_square(t, freq=2.0):
    """Generate square wave."""
    return np.where(np.sin(2 * np.pi * freq * t) >= 0, 1.0, -1.0)


def scipy_signal_chirp(t, f0=1.0, f1=50.0):
    """Generate linear chirp."""
    return np.sin(2 * np.pi * (f0 + (f1 - f0) * t / t[-1]) * t)


# ---- PLOTS ----

def main():
    print("=" * 60)
    print("TRANSFORMS — Laplace, Fourier, Bode, Convolution")
    print("=" * 60)

    # Run all demos
    laplace_results = demo_laplace()
    t_fft, sig1, freqs1, mag1, square, freqs2, mag2, chirp, spec_r = demo_fourier()
    bode_results = demo_bode()
    t_conv, a_conv, b_conv, t_c, conv = demo_convolution()
    t_filt, clean, noisy, filtered, rfft_n, rfft_c, r_lp = demo_filter()

    # ---- FIGURE 1: Main ----
    fig = plt.figure(figsize=(20, 18))

    # 1. Laplace transform table
    ax1 = fig.add_subplot(3, 4, 1)
    ax1.axis("off")
    table_text = "Laplace Transform Pairs:\n" + "━" * 30 + "\n"
    for name, F_s in laplace_results[:7]:
        short_f = F_s[:40] + ("..." if len(F_s) > 40 else "")
        table_text += f"f(t) = {name}\nF(s) = {short_f}\n\n"
    ax1.text(0.05, 0.95, table_text, transform=ax1.transAxes,
             fontsize=7, verticalalignment="top", fontfamily="monospace")

    # 2. Signal 1: time domain
    ax2 = fig.add_subplot(3, 4, 2)
    ax2.plot(t_fft[:300], sig1[:300], linewidth=0.8, color="#2196F3")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Amplitude")
    ax2.set_title("Signal: 5+15+30 Hz Sinusoids")
    ax2.grid(True, alpha=0.3)

    # 3. Signal 1: FFT magnitude
    ax3 = fig.add_subplot(3, 4, 3)
    mask = freqs1 < 50
    ax3.stem(freqs1[mask], mag1[mask], linefmt="#4CAF50", markerfmt="o", basefmt=" ")
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Magnitude")
    ax3.set_title("FFT: Detected Frequencies")
    ax3.grid(True, alpha=0.3)

    # 4. Square wave
    ax4 = fig.add_subplot(3, 4, 4)
    ax4.plot(t_fft[:200], square[:200], linewidth=0.8, color="#FF9800")
    ax4.set_xlabel("Time (s)")
    ax4.set_ylabel("Amplitude")
    ax4.set_title("Square Wave (2 Hz)")
    ax4.grid(True, alpha=0.3)

    # 5. Square wave FFT
    ax5 = fig.add_subplot(3, 4, 5)
    mask2 = freqs2 < 30
    ax5.stem(freqs2[mask2], mag2[mask2], linefmt="#FF9800", markerfmt="o", basefmt=" ")
    ax5.set_xlabel("Frequency (Hz)")
    ax5.set_ylabel("Magnitude")
    ax5.set_title("FFT: Square Wave Harmonics")
    ax5.grid(True, alpha=0.3)

    # 6. Spectrogram
    ax6 = fig.add_subplot(3, 4, 6)
    Sxx = np.array(spec_r.result["Sxx"])
    times_spec = np.array(spec_r.result["times"])
    freqs_spec = np.array(spec_r.result["frequencies"])
    im6 = ax6.pcolormesh(times_spec, freqs_spec, 10 * np.log10(Sxx + 1e-10),
                         shading="gouraud", cmap="viridis")
    ax6.set_xlabel("Time (s)")
    ax6.set_ylabel("Frequency (Hz)")
    ax6.set_title("Spectrogram: Chirp 1→50 Hz")
    plt.colorbar(im6, ax=ax6, label="dB", shrink=0.8)

    # 7. Bode magnitude
    ax7 = fig.add_subplot(3, 4, 7)
    # Find the first bode result (low-pass 1st order)
    for name, desc, r in bode_results:
        if "step" not in name and "Low-pass 1st" in name:
            freqs_b = np.array(r.result["frequencies_hz"])
            mag_b = np.array(r.result["magnitude_dB"])
            ax7.semilogx(freqs_b, mag_b, linewidth=2, label=desc)
    ax7.set_xlabel("Frequency (Hz)")
    ax7.set_ylabel("Magnitude (dB)")
    ax7.set_title("Bode: 1/(s+1)")
    ax7.grid(True, alpha=0.3)
    ax7.axhline(y=-3, color="red", linestyle="--", alpha=0.5, label="-3 dB")
    ax7.legend(fontsize=7)

    # 8. Bode phase
    ax8 = fig.add_subplot(3, 4, 8)
    for name, desc, r in bode_results:
        if "step" not in name and "Low-pass 1st" in name:
            phase_b = np.array(r.result["phase_deg"])
            ax8.semilogx(freqs_b, phase_b, linewidth=2, label=desc)
    ax8.set_xlabel("Frequency (Hz)")
    ax8.set_ylabel("Phase (deg)")
    ax8.set_title("Bode Phase: 1/(s+1)")
    ax8.grid(True, alpha=0.3)
    ax8.legend(fontsize=7)

    # 9. Step responses
    ax9 = fig.add_subplot(3, 4, 9)
    colors_sys = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63"]
    idx = 0
    for name, desc, r in bode_results:
        if "step" in name:
            t_step = np.array(r.result["time"])
            y_step = np.array(r.result["response"])
            ax9.plot(t_step, y_step, linewidth=1.5, color=colors_sys[idx % 4],
                     label=name.replace(" (step)", ""))
            idx += 1
    ax9.set_xlabel("Time (s)")
    ax9.set_ylabel("Response")
    ax9.set_title("Step Responses")
    ax9.legend(fontsize=7)
    ax9.grid(True, alpha=0.3)

    # 10. Convolution: signals
    ax10 = fig.add_subplot(3, 4, 10)
    ax10.plot(t_conv, a_conv, linewidth=1.5, label="A: square pulse", color="#2196F3")
    ax10.plot(t_conv, b_conv, linewidth=1.5, label="B: exp(-t)", color="#FF9800")
    ax10.set_xlabel("t")
    ax10.set_ylabel("Amplitude")
    ax10.set_title("Convolution: Input Signals")
    ax10.legend(fontsize=7)
    ax10.grid(True, alpha=0.3)

    # 11. Convolution result
    ax11 = fig.add_subplot(3, 4, 11)
    ax11.plot(t_c, conv, linewidth=2, color="#E91E63")
    ax11.set_xlabel("t")
    ax11.set_ylabel("(A * B)(t)")
    ax11.set_title("Convolution: A * B")
    ax11.grid(True, alpha=0.3)

    # 12. Filter demo
    ax12 = fig.add_subplot(3, 4, 12)
    ax12.plot(t_filt[:300], noisy[:300], linewidth=0.5, alpha=0.5, label="Noisy", color="red")
    ax12.plot(t_filt[:300], filtered[:300], linewidth=1.5, label="Filtered", color="#2196F3")
    ax12.plot(t_filt[:300], clean[:300], linewidth=1, linestyle="--", label="Clean (3 Hz)", color="green")
    ax12.set_xlabel("Time (s)")
    ax12.set_ylabel("Amplitude")
    ax12.set_title("Low-pass Filter: 3 Hz + 40 Hz noise")
    ax12.legend(fontsize=7)
    ax12.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "transforms_demo.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")

    # ---- FIGURE 2: Bode & Filter Analysis ----
    fig2, axes2 = plt.subplots(2, 3, figsize=(18, 10))

    # Bode magnitude for all systems
    ax = axes2[0, 0]
    colors_sys2 = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63"]
    idx = 0
    for name, desc, r in bode_results:
        if "step" not in name:
            freqs_b = np.array(r.result["frequencies_hz"])
            mag_b = np.array(r.result["magnitude_dB"])
            ax.semilogx(freqs_b, mag_b, linewidth=2, color=colors_sys2[idx % 4], label=name)
            idx += 1
    ax.axhline(y=-3, color="red", linestyle="--", alpha=0.3, label="-3 dB")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title("Bode Magnitude: All Systems")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Bode phase for all systems
    ax = axes2[0, 1]
    idx = 0
    for name, desc, r in bode_results:
        if "step" not in name:
            freqs_b = np.array(r.result["frequencies_hz"])
            phase_b = np.array(r.result["phase_deg"])
            ax.semilogx(freqs_b, phase_b, linewidth=2, color=colors_sys2[idx % 4], label=name)
            idx += 1
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Phase (deg)")
    ax.set_title("Bode Phase: All Systems")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Pole-zero map
    ax = axes2[0, 2]
    systems_pz = [
        ([1], [1, 1], "LP 1st"),
        ([1], [1, 1.4, 1], "LP 2nd"),
        ([1, 0], [1, 1], "HP"),
        ([1, 0], [1, 1, 1], "BP"),
    ]
    markers = ["o", "s", "^", "D"]
    for (num, den, label), marker in zip(systems_pz, markers):
        r_tf = tr.transfer_function(num, den)
        zeros = np.array(r_tf.result["zeros"])
        poles = np.array(r_tf.result["poles"])
        ax.scatter(poles.real, poles.imag, marker=marker, s=80, facecolors="none",
                   edgecolors=colors_sys2[systems_pz.index((num, den, label)) % 4],
                   linewidths=2, label=f"{label} poles")
        if len(zeros) > 0:
            ax.scatter(zeros.real, zeros.imag, marker=marker, s=80,
                       color=colors_sys2[systems_pz.index((num, den, label)) % 4],
                       label=f"{label} zeros")
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.axvline(x=0, color="black", linewidth=0.5)
    ax.set_xlabel("Real")
    ax.set_ylabel("Imag")
    ax.set_title("Pole-Zero Map")
    ax.legend(fontsize=6)
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal")

    # Filter: FFT before
    ax = axes2[1, 0]
    f_n = np.array(rfft_n.result["frequencies"])
    m_n = np.array(rfft_n.result["magnitude"])
    mask_n = f_n < 50
    ax.stem(f_n[mask_n], m_n[mask_n], linefmt="red", markerfmt="o", basefmt=" ")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude")
    ax.set_title("FFT: Noisy Signal (3 Hz + 40 Hz)")
    ax.grid(True, alpha=0.3)

    # Filter: FFT after
    ax = axes2[1, 1]
    f_c = np.array(rfft_c.result["frequencies"])
    m_c = np.array(rfft_c.result["magnitude"])
    mask_c = f_c < 50
    ax.stem(f_c[mask_c], m_c[mask_c], linefmt="#2196F3", markerfmt="o", basefmt=" ")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude")
    ax.set_title("FFT: Filtered Signal (40 Hz removed)")
    ax.grid(True, alpha=0.3)

    # Filter frequency response
    ax = axes2[1, 2]
    r_filt_bode = tr.bode(r_lp.result["b"], r_lp.result["a"],
                          freq_range=(0.1, 50), n_freqs=300)
    f_filt = np.array(r_filt_bode.result["frequencies_hz"])
    m_filt = np.array(r_filt_bode.result["magnitude_dB"])
    ax.semilogx(f_filt, m_filt, linewidth=2, color="#2196F3")
    ax.axvline(x=10, color="red", linestyle="--", alpha=0.5, label="fc=10 Hz")
    ax.axhline(y=-3, color="green", linestyle="--", alpha=0.5, label="-3 dB")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title("Low-pass Filter Response (order=4)")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path2 = OUTPUT_DIR / "transforms_bode_filter.png"
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path2}")

    print(f"\n✅ All transforms charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
