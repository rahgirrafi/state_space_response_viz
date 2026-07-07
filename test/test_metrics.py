"""Live-window performance metrics."""

import numpy as np

from state_space_response_viz import metrics


def test_rms_error():
    assert metrics.rms_error([3.0, 4.0]) == (12.5) ** 0.5   # sqrt((9+16)/2)
    assert metrics.rms_error([]) == 0.0


def test_settled_within_true_when_tail_bounded():
    t = list(np.linspace(0, 4, 41))
    e = [1.0 if ti < 1.0 else 0.005 for ti in t]   # big early, tiny later
    assert metrics.settled_within(t, e, band=0.02) is True


def test_settled_within_false_when_tail_violates():
    t = list(np.linspace(0, 4, 41))
    e = [0.1 for _ in t]
    assert metrics.settled_within(t, e, band=0.02) is False


def test_settling_time_abs_reports_time_since_band_entry():
    t = list(np.linspace(0, 4, 41))          # dt = 0.1
    e = [0.5 if ti <= 2.0 else 0.001 for ti in t]
    st = metrics.settling_time_abs(t, e, band=0.02)
    # It settled just after t=2.0, so ~2 s ago (window ends at 4.0).
    assert st is not None
    assert 1.7 < st < 2.05


def test_settling_time_abs_none_when_always_outside():
    t = [0.0, 1.0, 2.0]
    assert metrics.settling_time_abs(t, [1.0, 1.0, 1.0], band=0.02) is None


def test_rise_time_on_step():
    t = np.linspace(0, 1, 101)
    y = 1.0 - np.exp(-t / 0.1)                # first-order rise to 1.0
    rt = metrics.rise_time(t, y, 0.0, 1.0)
    assert rt is not None
    assert 0.15 < rt < 0.30                   # ~2.2*tau for 10-90%


def test_rise_time_none_without_step():
    t = np.linspace(0, 1, 11)
    assert metrics.rise_time(t, np.zeros_like(t), 0.0, 0.0) is None


def test_channel_metrics_shape():
    t = list(np.linspace(0, 2, 21))
    ch = [[0.01] * 21, [0.5] * 21]
    out = metrics.channel_metrics(t, ch, band=0.02)
    assert len(out) == 2
    assert out[0]['settled'] is True
    assert out[1]['settled'] is False
    assert set(out[0]) == {'rms', 'settled', 'settling_time'}
