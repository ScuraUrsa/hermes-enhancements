"""
Transforms Module — Laplace, Fourier, Bode, Convolution.

All computations use NumPy/SciPy/SymPy — LLM NEVER does math.
Provides symbolic Laplace transforms (SymPy), numerical FFT (NumPy),
transfer function analysis, Bode plots, and convolution.

Usage:
    from transforms import Transforms
    tr = Transforms()
    result = tr.laplace_transform("sin(t)", "t", "s")
    fft_result = tr.fourier_transform(data, dt=0.01)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import scipy.signal
import sympy as sp


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class TRResult:
    """Structured result from transform operations."""
    success: bool
    result: Any = None
    error: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Transforms Engine
# ---------------------------------------------------------------------------

class Transforms:
    """Symbolic and numerical transforms."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Laplace Transform (Symbolic) ----

    @staticmethod
    def laplace_transform(
        expr: str, t_var: str = "t", s_var: str = "s",
    ) -> TRResult:
        """Compute symbolic Laplace transform: L{f(t)} = F(s).

        Uses SymPy's laplace_transform.

        Args:
            expr: expression in t (e.g., 'sin(t)', 'exp(-a*t)', 't**2')
            t_var: time variable
            s_var: Laplace variable

        Returns:
            F(s), region of convergence, steps
        """
        try:
            t = sp.symbols(t_var, positive=True)
            s = sp.symbols(s_var)
            # Use the same t symbol in the expression
            local_dict = {t_var: t}
            f = sp.sympify(expr, locals=local_dict)

            F_result = sp.laplace_transform(f, t, s, noconds=False)
            # Handle different SymPy versions (returns 2 or 3 values)
            if len(F_result) == 3:
                F, a, cond = F_result
                convergence_condition = f"Re(s) > {a}"
            else:
                F, convergence_condition = F_result

            return TRResult(
                success=True,
                result={
                    "F_s": str(F),
                    "latex": sp.latex(F),
                    "convergence": str(convergence_condition),
                },
                metadata={"expr": expr, "t_var": t_var, "s_var": s_var},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def inverse_laplace_transform(
        expr: str, s_var: str = "s", t_var: str = "t",
    ) -> TRResult:
        """Compute symbolic inverse Laplace transform: L⁻¹{F(s)} = f(t).

        Args:
            expr: expression in s (e.g., '1/(s**2 + 1)', '1/s**2')
            s_var: Laplace variable
            t_var: time variable

        Returns:
            f(t)
        """
        try:
            s = sp.symbols(s_var)
            t = sp.symbols(t_var, positive=True)
            local_dict = {s_var: s}
            F = sp.sympify(expr, locals=local_dict)

            f = sp.inverse_laplace_transform(F, s, t)

            return TRResult(
                success=True,
                result={
                    "f_t": str(f),
                    "latex": sp.latex(f),
                },
                metadata={"expr": expr, "s_var": s_var, "t_var": t_var},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    # ---- Fourier Transform (Numerical) ----

    @staticmethod
    def fourier_transform(
        data: list[float] | np.ndarray,
        dt: float = 1.0,
    ) -> TRResult:
        """Compute FFT of time-domain data.

        Args:
            data: time-domain signal
            dt: sampling interval

        Returns:
            frequencies, magnitude, phase, power spectrum
        """
        try:
            arr = np.asarray(data, dtype=float)
            n = len(arr)
            fft = np.fft.fft(arr)
            freqs = np.fft.fftfreq(n, dt)

            # Only positive frequencies
            pos_mask = freqs >= 0
            magnitude = np.abs(fft)[pos_mask]
            phase = np.angle(fft)[pos_mask]
            power = magnitude ** 2

            return TRResult(
                success=True,
                result={
                    "frequencies": freqs[pos_mask].tolist(),
                    "magnitude": magnitude.tolist(),
                    "phase": phase.tolist(),
                    "power": power.tolist(),
                },
                metadata={"n": n, "dt": dt, "nyquist": 0.5 / dt},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def inverse_fourier_transform(
        fft_data: list[complex] | np.ndarray,
    ) -> TRResult:
        """Compute inverse FFT to recover time-domain signal.

        Args:
            fft_data: complex FFT coefficients

        Returns:
            reconstructed time-domain signal (real part)
        """
        try:
            arr = np.asarray(fft_data, dtype=complex)
            signal = np.fft.ifft(arr)
            return TRResult(
                success=True,
                result={
                    "signal_real": signal.real.tolist(),
                    "signal_imag": signal.imag.tolist(),
                },
                metadata={"n": len(arr)},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def spectrogram(
        data: list[float] | np.ndarray,
        fs: float = 1.0,
        nperseg: int = 256,
        noverlap: int = 128,
    ) -> TRResult:
        """Compute spectrogram (STFT) of a signal.

        Args:
            data: time-domain signal
            fs: sampling frequency
            nperseg: samples per segment
            noverlap: overlap between segments

        Returns:
            frequencies, times, Sxx (spectrogram matrix)
        """
        try:
            arr = np.asarray(data, dtype=float)
            freqs, times, Sxx = scipy.signal.spectrogram(
                arr, fs=fs, nperseg=nperseg, noverlap=noverlap,
            )
            return TRResult(
                success=True,
                result={
                    "frequencies": freqs.tolist(),
                    "times": times.tolist(),
                    "Sxx": Sxx.tolist(),
                },
                metadata={"fs": fs, "nperseg": nperseg, "noverlap": noverlap},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    # ---- Transfer Functions & Bode Plots ----

    @staticmethod
    def transfer_function(
        num: list[float],
        den: list[float],
    ) -> TRResult:
        """Create a transfer function H(s) = num(s) / den(s).

        Uses scipy.signal.TransferFunction.

        Args:
            num: numerator coefficients (highest power first)
            den: denominator coefficients (highest power first)

        Returns:
            TransferFunction object data: poles, zeros, gain
        """
        try:
            sys = scipy.signal.TransferFunction(num, den)
            zeros = np.roots(num)
            poles = np.roots(den)
            gain = num[0] / den[0] if den[0] != 0 else float("inf")

            return TRResult(
                success=True,
                result={
                    "num": num,
                    "den": den,
                    "zeros": zeros.tolist(),
                    "poles": poles.tolist(),
                    "gain": float(gain),
                },
                metadata={"order": len(den) - 1},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def bode(
        num: list[float],
        den: list[float],
        freq_range: tuple[float, float] = (0.01, 100.0),
        n_freqs: int = 500,
    ) -> TRResult:
        """Compute Bode plot data: magnitude (dB) and phase (degrees) vs frequency.

        Args:
            num: numerator coefficients
            den: denominator coefficients
            freq_range: (f_min, f_max) in Hz
            n_freqs: number of frequency points

        Returns:
            frequencies, magnitude_dB, phase_deg
        """
        try:
            sys = scipy.signal.TransferFunction(num, den)
            w = np.logspace(
                np.log10(2 * np.pi * freq_range[0]),
                np.log10(2 * np.pi * freq_range[1]),
                n_freqs,
            )
            w, mag, phase = scipy.signal.bode(sys, w=w)

            return TRResult(
                success=True,
                result={
                    "frequencies_hz": (w / (2 * np.pi)).tolist(),
                    "magnitude_dB": mag.tolist(),
                    "phase_deg": phase.tolist(),
                },
                metadata={"freq_range": freq_range, "n_freqs": n_freqs},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def frequency_response(
        num: list[float],
        den: list[float],
        freq_range: tuple[float, float] = (0.01, 100.0),
        n_freqs: int = 500,
    ) -> TRResult:
        """Compute frequency response (complex) of a transfer function.

        Returns magnitude, phase, and complex response.
        """
        try:
            sys = scipy.signal.TransferFunction(num, den)
            w = np.logspace(
                np.log10(2 * np.pi * freq_range[0]),
                np.log10(2 * np.pi * freq_range[1]),
                n_freqs,
            )
            w, H = scipy.signal.freqresp(sys, w=w)

            return TRResult(
                success=True,
                result={
                    "frequencies_hz": (w / (2 * np.pi)).tolist(),
                    "magnitude": np.abs(H).tolist(),
                    "phase_rad": np.angle(H).tolist(),
                    "H_real": H.real.tolist(),
                    "H_imag": H.imag.tolist(),
                },
                metadata={"freq_range": freq_range, "n_freqs": n_freqs},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def step_response(
        num: list[float],
        den: list[float],
        t_end: float = 10.0,
        n_points: int = 500,
    ) -> TRResult:
        """Compute step response of a transfer function.

        Args:
            num: numerator coefficients
            den: denominator coefficients
            t_end: simulation end time
            n_points: number of time points

        Returns:
            time, response
        """
        try:
            sys = scipy.signal.TransferFunction(num, den)
            t = np.linspace(0, t_end, n_points)
            _, y = scipy.signal.step(sys, T=t)

            return TRResult(
                success=True,
                result={
                    "time": t.tolist(),
                    "response": y.tolist(),
                },
                metadata={"t_end": t_end, "n_points": n_points},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def impulse_response(
        num: list[float],
        den: list[float],
        t_end: float = 10.0,
        n_points: int = 500,
    ) -> TRResult:
        """Compute impulse response of a transfer function."""
        try:
            sys = scipy.signal.TransferFunction(num, den)
            t = np.linspace(0, t_end, n_points)
            _, y = scipy.signal.impulse(sys, T=t)

            return TRResult(
                success=True,
                result={
                    "time": t.tolist(),
                    "response": y.tolist(),
                },
                metadata={"t_end": t_end, "n_points": n_points},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    # ---- Convolution ----

    @staticmethod
    def convolve(
        a: list[float] | np.ndarray,
        b: list[float] | np.ndarray,
        mode: str = "full",
    ) -> TRResult:
        """Compute discrete convolution of two sequences.

        Args:
            a: first sequence
            b: second sequence
            mode: 'full', 'same', or 'valid'

        Returns:
            convolved sequence
        """
        try:
            a_arr = np.asarray(a, dtype=float)
            b_arr = np.asarray(b, dtype=float)
            result = np.convolve(a_arr, b_arr, mode=mode)

            return TRResult(
                success=True,
                result=result.tolist(),
                metadata={"len_a": len(a_arr), "len_b": len(b_arr),
                          "mode": mode, "len_result": len(result)},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def convolution_demo_signals(
        n: int = 200,
    ) -> TRResult:
        """Generate demo signals for convolution visualization.

        Creates a square pulse and an exponential decay for convolution demo.

        Returns:
            t, signal_a, signal_b, convolution result
        """
        try:
            t = np.linspace(0, 10, n)
            dt = t[1] - t[0]

            # Signal A: square pulse
            a = np.zeros(n)
            a[(t >= 1) & (t <= 3)] = 1.0

            # Signal B: exponential decay
            b = np.exp(-t) * (t >= 0)

            # Convolution
            conv = np.convolve(a, b, mode="full")[:n] * dt
            t_conv = np.linspace(0, 20, 2 * n - 1)[:n]

            return TRResult(
                success=True,
                result={
                    "t": t.tolist(),
                    "signal_a": a.tolist(),
                    "signal_b": b.tolist(),
                    "t_conv": t_conv.tolist(),
                    "convolution": conv.tolist(),
                },
                metadata={"n": n, "dt": float(dt)},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    # ---- Filter Design ----

    @staticmethod
    def design_filter(
        filter_type: str = "lowpass",
        order: int = 4,
        cutoff: float = 10.0,
        fs: float = 100.0,
    ) -> TRResult:
        """Design a Butterworth filter.

        Args:
            filter_type: 'lowpass', 'highpass', 'bandpass', 'bandstop'
            order: filter order
            cutoff: cutoff frequency (Hz) — for bandpass/bandstop use [low, high]
            fs: sampling frequency (Hz)

        Returns:
            b, a coefficients (numerator, denominator)
        """
        try:
            nyq = fs / 2
            if isinstance(cutoff, (list, tuple)):
                Wn = [c / nyq for c in cutoff]
            else:
                Wn = cutoff / nyq

            b, a = scipy.signal.butter(order, Wn, btype=filter_type)

            return TRResult(
                success=True,
                result={"b": b.tolist(), "a": a.tolist()},
                metadata={"filter_type": filter_type, "order": order,
                          "cutoff": cutoff, "fs": fs},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def apply_filter(
        data: list[float] | np.ndarray,
        b: list[float],
        a: list[float],
    ) -> TRResult:
        """Apply a digital filter to data.

        Args:
            data: input signal
            b: numerator coefficients
            a: denominator coefficients

        Returns:
            filtered signal
        """
        try:
            arr = np.asarray(data, dtype=float)
            b_arr = np.asarray(b, dtype=float)
            a_arr = np.asarray(a, dtype=float)
            filtered = scipy.signal.lfilter(b_arr, a_arr, arr)

            return TRResult(
                success=True,
                result=filtered.tolist(),
                metadata={"n": len(arr)},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    # ---- Symbolic Fourier (SymPy) ----

    @staticmethod
    def symbolic_fourier_transform(
        expr: str, t_var: str = "t", w_var: str = "w",
    ) -> TRResult:
        """Compute symbolic Fourier transform using SymPy.

        Args:
            expr: expression in t
            t_var: time variable
            w_var: frequency variable

        Returns:
            F(ω)
        """
        try:
            t = sp.symbols(t_var, real=True)
            w = sp.symbols(w_var, real=True)
            local_dict = {t_var: t}
            f = sp.sympify(expr, locals=local_dict)

            F = sp.fourier_transform(f, t, w)

            return TRResult(
                success=True,
                result={
                    "F_w": str(F),
                    "latex": sp.latex(F),
                },
                metadata={"expr": expr, "t_var": t_var, "w_var": w_var},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))

    @staticmethod
    def symbolic_inverse_fourier_transform(
        expr: str, w_var: str = "w", t_var: str = "t",
    ) -> TRResult:
        """Compute symbolic inverse Fourier transform."""
        try:
            w = sp.symbols(w_var, real=True)
            t = sp.symbols(t_var, real=True)
            local_dict = {w_var: w}
            F = sp.sympify(expr, locals=local_dict)

            f = sp.inverse_fourier_transform(F, w, t)

            return TRResult(
                success=True,
                result={
                    "f_t": str(f),
                    "latex": sp.latex(f),
                },
                metadata={"expr": expr, "w_var": w_var, "t_var": t_var},
            )
        except Exception as e:
            return TRResult(success=False, error=str(e))
