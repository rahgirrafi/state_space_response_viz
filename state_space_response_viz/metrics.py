"""Live performance metrics computed over a sliding window.

The dashboard's tracking error should decay to zero (regulate-to-equilibrium)
or to a setpoint step. ``state_space_control.analysis.settling_time`` measures
settling relative to a signal's *final* value, which is the right tool for a
finished step response but not for a live regulator sitting near zero — so the
live indicators here use an **absolute** band. ``settling_time`` is reused for
the rise-time helper, where a genuine nonzero step target exists.

All functions take plain Python lists / numpy arrays and are import-light so
they can be unit-tested without ROS.
"""

from typing import List, Optional, Sequence

import numpy as np


def rms_error(err: Sequence[float]) -> float:
    """Root-mean-square of a tracking-error series over the window."""
    a = np.asarray(err, dtype=float)
    if a.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(a * a)))


def settled_within(
    t: Sequence[float], err: Sequence[float], band: float, hold_frac: float = 0.25
) -> bool:
    """True if |err| stayed within ``band`` over the final ``hold_frac`` of t."""
    t = np.asarray(t, dtype=float)
    e = np.asarray(err, dtype=float)
    if t.size < 2:
        return False
    t0 = t[-1] - hold_frac * (t[-1] - t[0])
    tail = e[t >= t0]
    return bool(tail.size > 0 and np.all(np.abs(tail) <= band))


def settling_time_abs(
    t: Sequence[float], err: Sequence[float], band: float
) -> Optional[float]:
    """Seconds since |err| last left ``band``; None if still outside it.

    Answers "how long has it been settled?" for the live indicator.
    """
    t = np.asarray(t, dtype=float)
    e = np.asarray(err, dtype=float)
    if t.size == 0:
        return None
    outside = np.abs(e) > band
    if outside.all():
        return None
    if not outside.any():
        return float(t[-1] - t[0])
    last_bad = int(np.max(np.nonzero(outside)))
    if last_bad + 1 >= t.size:
        return None
    return float(t[-1] - t[last_bad + 1])


def rise_time(
    t: Sequence[float], y: Sequence[float], y0: float, yf: float,
    lo: float = 0.1, hi: float = 0.9,
) -> Optional[float]:
    """10%-90% rise time for a step from ``y0`` to ``yf`` (None if N/A)."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    span = yf - y0
    if t.size < 2 or abs(span) < 1e-9:
        return None
    y_lo, y_hi = y0 + lo * span, y0 + hi * span
    frac = (y - y0) / span

    def _cross(level_frac: float) -> Optional[float]:
        idx = np.nonzero(frac >= level_frac)[0]
        return float(t[idx[0]]) if idx.size else None

    t_lo, t_hi = _cross(lo), _cross(hi)
    if t_lo is None or t_hi is None or t_hi < t_lo:
        return None
    return t_hi - t_lo


def detect_step(ref: Sequence[float], eps: float = 1e-6) -> bool:
    """True if the reference channel changed meaningfully across the window."""
    a = np.asarray(ref, dtype=float)
    return bool(a.size >= 2 and (a.max() - a.min()) > eps)


def channel_metrics(
    t: Sequence[float], err_channels: List[Sequence[float]], band: float
) -> List[dict]:
    """Per-error-channel {rms, settled, settling_time} over the window."""
    out = []
    for e in err_channels:
        out.append({
            'rms': rms_error(e),
            'settled': settled_within(t, e, band),
            'settling_time': settling_time_abs(t, e, band),
        })
    return out
