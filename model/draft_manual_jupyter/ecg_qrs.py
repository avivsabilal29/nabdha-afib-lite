"""
ECG QRS/R-peak detection pipeline.

Implements the maths from TASK_BRIEF (note 31, _Memahami AFIB-LITE_):

  Stage 1  Bandpass 5-15 Hz              -> removes baseline wander + mains hum
  Stage 2  5-point derivative            -> coefficients [2, 1, 0, -1, -2] / 8
  Stage 3  Squaring                      -> emphasises QRS slope
  Stage 4  Moving-window integrator 150 ms -> envelope of QRS energy
  Stage 5  Adaptive peak detection       -> Pan-Tompkins SPKI/NPKI/T1/T2

All functions are pure: state lives in the caller, no printing inside a stage.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt, convolve, find_peaks


# --------------------------------------------------------------------------- #
# Stage 1 - Bandpass filter (5-15 Hz)
# --------------------------------------------------------------------------- #
def bandpass_filter(x: np.ndarray,
                    fs: float = 250.0,
                    low: float = 5.0,
                    high: float = 15.0,
                    order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth bandpass.

    Note 31, stage 1. Cuts baseline wander (<5 Hz) and mains hum (>15 Hz)
    while keeping the QRS complex intact.

    Parameters
    ----------
    x : float ndarray, ECG samples (any unit)
    fs : Hz, sample rate
    low, high : Hz, passband edges
    order : Butterworth filter order

    Returns
    -------
    y : float ndarray, same shape as x, zero-phase filtered
    """
    nyq = 0.5 * fs
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, x)


# --------------------------------------------------------------------------- #
# Stage 2 - 5-point derivative
# --------------------------------------------------------------------------- #
def derivative(x: np.ndarray,
               coeffs: np.ndarray | None = None) -> np.ndarray:
    """5-point derivative, coefficients 2, 1, 0, -1, -2 divided by 8.

    Note 31, stage 2. Uses 'same' convolution so the group delay is
    (len(coeffs) - 1) / 2 = 2 samples, as recorded in the brief.

    Parameters
    ----------
    x : float ndarray, filtered ECG
    coeffs : derivative coefficients, default [2, 1, 0, -1, -2] / 8

    Returns
    -------
    y : float ndarray, same length as x
    """
    if coeffs is None:
        coeffs = np.array([2.0, 1.0, 0.0, -1.0, -2.0]) / 8.0
    return np.convolve(x, coeffs, mode="same")


# --------------------------------------------------------------------------- #
# Stage 3 - Squaring
# --------------------------------------------------------------------------- #
def squarer(x: np.ndarray) -> np.ndarray:
    """Sample-by-sample squaring.

    Note 31, stage 3. Output is strictly non-negative; emphasises steep QRS
    slopes and suppresses small T-wave energy.
    """
    return np.asarray(x, dtype=float) ** 2


# --------------------------------------------------------------------------- #
# Stage 4 - Moving-window integrator (150 ms)
# --------------------------------------------------------------------------- #
def moving_window_integrator(x: np.ndarray,
                             fs: float = 250.0,
                             window_sec: float = 0.150) -> np.ndarray:
    """Running average over a 150 ms window.

    Note 31, stage 4. At 250 Hz a 150 ms window is 37.5 samples. The brief
    says to alternate 37 and 38 samples so the average window is exactly
    150 ms; we use round(0.150 * fs) for the first cut and document the
    trade-off here.

    Parameters
    ----------
    x : float ndarray, squared derivative
    fs : Hz
    window_sec : seconds, default 0.150

    Returns
    -------
    y : float ndarray, same length as x (centred convolution)
    """
    n = max(1, int(round(window_sec * fs)))
    kernel = np.ones(n, dtype=float) / n
    return convolve(x, kernel, mode="same", method="direct")


# --------------------------------------------------------------------------- #
# Stage 5 - Adaptive-threshold R-peak detection (Pan-Tompkins)
# --------------------------------------------------------------------------- #
def detect_r_peaks(envelope: np.ndarray,
                  fs: float = 250.0,
                  refractory_sec: float = 0.200,
                  search_back_factor: float = 1.66,
                  spki_alpha: float = 0.125,
                  npki_alpha: float = 0.125,
                  t1_factor: float = 0.25,
                  t2_factor: float = 0.50) -> np.ndarray:
    """Detect R-peak sample indices on the QRS envelope.

    Note 31, stage 5. Implements Pan-Tompkins adaptive thresholds:

        SPKI = alpha * peak + (1 - alpha) * SPKI   # signal running average
        NPKI = alpha * peak + (1 - alpha) * NPKI   # noise running average
        T1   = NPKI + 0.25 * (SPKI - NPKI)          # primary threshold
        T2   = 0.5 * T1                             # secondary (search-back)

    Plus a 200 ms refractory and a search-back at 1.66 x mean RR when
    a beat is missed.

    Parameters
    ----------
    envelope : float ndarray, output of moving_window_integrator
    fs, refractory_sec, search_back_factor : see brief
    spki_alpha, npki_alpha : EMA factors for SPKI / NPKI
    t1_factor, t2_factor : threshold factors

    Returns
    -------
    peaks : int ndarray, ascending sample indices of R-peaks
    """
    n = len(envelope)
    refractory = max(1, int(refractory_sec * fs))

    # Step 1 - candidate local maxima of the envelope.
    # `distance=refractory` enforces the refractory period between candidates,
    # so we never get two R-peaks closer than 200 ms apart.
    candidates, _ = find_peaks(envelope, distance=refractory)
    if candidates.size == 0:
        return np.array([], dtype=int)

    # Seed SPKI / NPKI from the envelope statistics of the first ~5 s.
    seed_n = min(n, int(5.0 * fs))
    seed = envelope[:seed_n]
    spki = float(np.max(seed))
    npki = float(np.mean(seed)) + 1e-9
    t1 = npki + t1_factor * (spki - npki)
    t2 = t2_factor * t1

    # Step 2 - Pan-Tompkins adaptive thresholding on each candidate.
    peaks: list[int] = []
    rr_recent: list[int] = []
    last_accepted = -1

    for cand_idx in candidates:
        cand_val = float(envelope[cand_idx])

        if cand_val > t1:
            # Signal peak -> accept.
            peaks.append(int(cand_idx))
            spki = spki_alpha * cand_val + (1 - spki_alpha) * spki
            if last_accepted >= 0:
                rr_recent.append(int(cand_idx) - last_accepted)
            last_accepted = int(cand_idx)
        elif cand_val > t2:
            # Noise peak -> raise NPKI but don't record.
            npki = npki_alpha * cand_val + (1 - npki_alpha) * npki
        # else: below T2, ignore.

        # Recompute thresholds.
        t1 = npki + t1_factor * (spki - npki)
        t2 = t2_factor * t1

    # Step 3 - search-back for missed beats.
    # If the gap between two accepted peaks exceeds 1.66 x mean RR, look
    # back into the gap for the largest envelope value above T2 and
    # accept it as a signal peak.
    if len(peaks) >= 2 and rr_recent:
        mean_rr = int(np.mean(rr_recent))
        sb_limit = int(search_back_factor * mean_rr)
        extra: list[int] = []
        for i in range(1, len(peaks)):
            gap = peaks[i] - peaks[i - 1]
            if gap > sb_limit:
                lo = peaks[i - 1] + refractory
                hi = min(peaks[i], peaks[i - 1] + sb_limit)
                if hi <= lo:
                    continue
                seg = envelope[lo:hi]
                sb_val = float(np.max(seg))
                # Use the current T2 of the previous beat for the search-back.
                if sb_val > t2:
                    sb_idx = lo + int(np.argmax(seg))
                    extra.append(sb_idx)
        if extra:
            peaks = sorted(set(peaks) | set(extra))

    return np.array(peaks, dtype=int)


# --------------------------------------------------------------------------- #
# Convenience - run stages 1-4 end to end
# --------------------------------------------------------------------------- #
def qrs_envelope(ecg: np.ndarray, fs: float = 250.0) -> tuple[np.ndarray, ...]:
    """Run stages 1-4 and return every intermediate signal.

    Useful for plots and golden-vector export.
    """
    x1 = bandpass_filter(ecg, fs=fs)
    x2 = derivative(x1)
    x3 = squarer(x2)
    x4 = moving_window_integrator(x3, fs=fs)
    return x1, x2, x3, x4


def rr_intervals_samples(peaks: np.ndarray) -> np.ndarray:
    """Stage 6 - RR series in sample counts (not seconds)."""
    return np.diff(peaks).astype(int)
