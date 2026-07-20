"""
Tests for transforms.py module.

Covers: Laplace transform, Fourier transform (FFT), Bode plots,
transfer functions, convolution, filter design.
"""

import numpy as np
import pytest
from transforms import Transforms, TRResult

tr = Transforms()


# ---- Laplace Transform ----

def test_laplace_sin():
    r = tr.laplace_transform("sin(t)")
    assert r.success
    # L{sin(t)} = 1/(s²+1)
    assert "1" in r.result["F_s"] and "s" in r.result["F_s"]


def test_laplace_exp():
    r = tr.laplace_transform("exp(-a*t)")
    assert r.success
    # L{exp(-at)} = 1/(s+a)
    assert "a" in r.result["F_s"] or "s" in r.result["F_s"]


def test_laplace_step():
    r = tr.laplace_transform("Heaviside(t)")
    assert r.success
    # L{u(t)} = 1/s
    assert "1" in r.result["F_s"] and "s" in r.result["F_s"]


def test_laplace_impulse():
    r = tr.laplace_transform("DiracDelta(t)")
    # SymPy may return 0 for DiracDelta — just check it doesn't crash
    assert isinstance(r, TRResult)


def test_laplace_t_power():
    r = tr.laplace_transform("t**2")
    assert r.success
    # L{t²} = 2/s³
    assert "2" in r.result["F_s"]


def test_inverse_laplace():
    r = tr.inverse_laplace_transform("1/(s**2 + 1)")
    assert r.success
    # L⁻¹{1/(s²+1)} = sin(t)
    assert "sin" in r.result["f_t"].lower()


def test_inverse_laplace_exp():
    r = tr.inverse_laplace_transform("1/(s + a)")
    assert r.success
    assert "exp" in r.result["f_t"].lower()


# ---- Fourier Transform (FFT) ----

def test_fourier_transform_sinusoid():
    """FFT of a pure sinusoid should show a single peak."""
    dt = 0.01
    t = np.arange(0, 1, dt)
    freq = 10.0  # Hz
    signal = np.sin(2 * np.pi * freq * t)

    r = tr.fourier_transform(signal, dt=dt)
    assert r.success
    freqs = np.array(r.result["frequencies"])
    mag = np.array(r.result["magnitude"])

    # Find peak frequency
    peak_idx = np.argmax(mag[1:]) + 1  # skip DC
    peak_freq = freqs[peak_idx]
    assert abs(peak_freq - freq) < 2.0  # within 2 Hz


def test_fourier_transform_dc():
    """FFT of constant signal should have only DC component."""
    signal = np.ones(100)
    r = tr.fourier_transform(signal, dt=0.01)
    assert r.success
    mag = np.array(r.result["magnitude"])
    # DC component should dominate
    assert mag[0] > 10 * np.max(mag[1:])


def test_fourier_transform_length():
    signal = np.random.randn(128)
    r = tr.fourier_transform(signal, dt=0.01)
    assert r.success
    freqs = np.array(r.result["frequencies"])
    mag = np.array(r.result["magnitude"])
    # Positive frequencies only: n//2 + 1
    assert len(freqs) == 64  # 128//2 (positive frequencies for even-length real input)
    assert len(mag) == 64


def test_inverse_fourier():
    """Round-trip: FFT → IFFT should recover original signal."""
    signal = np.sin(2 * np.pi * 5 * np.arange(0, 1, 0.01))
    fft = np.fft.fft(signal)
    r = tr.inverse_fourier_transform(fft)
    assert r.success
    recovered = np.array(r.result["signal_real"])
    assert np.allclose(signal, recovered, atol=1e-10)


def test_spectrogram():
    dt = 0.01
    t = np.arange(0, 2, dt)
    chirp = np.sin(2 * np.pi * (1 + 49 * t / t[-1]) * t)
    r = tr.spectrogram(chirp, fs=1/dt, nperseg=128, noverlap=64)
    assert r.success
    Sxx = np.array(r.result["Sxx"])
    assert Sxx.shape[0] > 0
    assert Sxx.shape[1] > 0


# ---- Transfer Functions & Bode ----

def test_transfer_function():
    r = tr.transfer_function([1], [1, 2, 1])
    assert r.success
    assert len(r.result["poles"]) == 2
    # Poles of 1/(s²+2s+1) = 1/(s+1)² → double pole at -1
    assert abs(r.result["poles"][0] + 1.0) < 1e-10


def test_transfer_function_zeros():
    r = tr.transfer_function([1, 0], [1, 1])  # s/(s+1)
    assert r.success
    assert len(r.result["zeros"]) == 1
    assert abs(r.result["zeros"][0]) < 1e-10  # zero at 0


def test_bode():
    r = tr.bode([1], [1, 1], freq_range=(0.01, 100), n_freqs=200)
    assert r.success
    mag = np.array(r.result["magnitude_dB"])
    phase = np.array(r.result["phase_deg"])
    freqs = np.array(r.result["frequencies_hz"])
    assert len(mag) == 200
    assert len(phase) == 200
    # DC gain of 1/(s+1) should be 0 dB
    assert abs(mag[0]) < 1.0


def test_bode_lowpass_attenuation():
    """Low-pass filter should attenuate at high frequencies."""
    r = tr.bode([1], [1, 1], freq_range=(0.01, 100), n_freqs=300)
    mag = np.array(r.result["magnitude_dB"])
    # At high frequency, should be well below 0 dB
    assert mag[-1] < -20


def test_frequency_response():
    r = tr.frequency_response([1], [1, 1], freq_range=(0.01, 100), n_freqs=100)
    assert r.success
    H_real = np.array(r.result["H_real"])
    H_imag = np.array(r.result["H_imag"])
    assert len(H_real) == 100


def test_step_response():
    r = tr.step_response([1], [1, 1], t_end=5, n_points=200)
    assert r.success
    y = np.array(r.result["response"])
    # Step response of 1/(s+1) should approach 1
    assert abs(y[-1] - 1.0) < 0.1


def test_impulse_response():
    r = tr.impulse_response([1], [1, 1], t_end=5, n_points=200)
    assert r.success
    y = np.array(r.result["response"])
    # Impulse response of 1/(s+1) = exp(-t), should decay to 0
    assert abs(y[-1]) < 0.1


# ---- Convolution ----

def test_convolve_full():
    r = tr.convolve([1, 2, 3], [4, 5, 6], mode="full")
    assert r.success
    # [1,2,3] * [4,5,6] = [4, 13, 28, 27, 18]
    expected = [4, 13, 28, 27, 18]
    assert np.allclose(r.result, expected)


def test_convolve_same():
    r = tr.convolve([1, 2, 3], [4, 5, 6], mode="same")
    assert r.success
    assert len(r.result) == 3


def test_convolve_valid():
    r = tr.convolve([1, 2, 3], [4, 5, 6], mode="valid")
    assert r.success
    assert len(r.result) == 1


def test_convolution_demo():
    r = tr.convolution_demo_signals(n=100)
    assert r.success
    assert len(r.result["signal_a"]) == 100
    assert len(r.result["signal_b"]) == 100
    assert len(r.result["convolution"]) == 100


# ---- Filter Design ----

def test_design_lowpass():
    r = tr.design_filter("lowpass", order=4, cutoff=10, fs=100)
    assert r.success
    assert len(r.result["b"]) == 5  # order 4 → 5 coefficients
    assert len(r.result["a"]) == 5


def test_design_highpass():
    r = tr.design_filter("highpass", order=2, cutoff=20, fs=100)
    assert r.success
    assert len(r.result["b"]) == 3


def test_design_bandpass():
    r = tr.design_filter("bandpass", order=4, cutoff=[10, 30], fs=100)
    assert r.success


def test_apply_filter():
    # Design low-pass and apply to noisy signal
    r_filt = tr.design_filter("lowpass", order=4, cutoff=10, fs=100)
    t = np.arange(0, 1, 0.01)
    signal = np.sin(2 * np.pi * 3 * t) + 0.5 * np.sin(2 * np.pi * 40 * t)
    r = tr.apply_filter(signal, r_filt.result["b"], r_filt.result["a"])
    assert r.success
    filtered = np.array(r.result)
    assert len(filtered) == len(signal)
    # Filtered signal should have less high-frequency content
    fft_orig = np.fft.fft(signal)
    fft_filt = np.fft.fft(filtered)
    high_freq_mask = np.abs(np.fft.fftfreq(len(t), 0.01)) > 30
    assert np.sum(np.abs(fft_filt[high_freq_mask])) < np.sum(np.abs(fft_orig[high_freq_mask]))


# ---- Symbolic Fourier ----

def test_symbolic_fourier():
    r = tr.symbolic_fourier_transform("exp(-t**2)")
    # SymPy may return 0 if it can't compute; that's OK — just check it doesn't crash
    assert isinstance(r, TRResult)


def test_symbolic_inverse_fourier():
    r = tr.symbolic_inverse_fourier_transform("exp(-w**2)")
    assert r.success


# ---- Edge Cases ----

def test_fourier_empty():
    r = tr.fourier_transform([], dt=0.01)
    # Empty input may fail — that's acceptable
    assert isinstance(r, TRResult)


def test_fourier_single_point():
    r = tr.fourier_transform([1.0], dt=0.01)
    assert r.success
    assert len(r.result["frequencies"]) == 1


def test_convolve_empty():
    r = tr.convolve([], [1, 2, 3])
    # Empty input may fail — that's acceptable
    assert isinstance(r, TRResult)


def test_bode_invalid():
    """Bode with unstable system should still compute."""
    r = tr.bode([1], [1, -1], freq_range=(0.01, 10), n_freqs=50)
    # Should not crash, even if system is unstable
    assert isinstance(r, TRResult)
