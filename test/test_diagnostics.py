"""diagnostics.parse: slice the flat Float64MultiArray by its named layout.

Uses lightweight fakes for the message so the test needs no ROS middleware.
"""

from types import SimpleNamespace

from state_space_response_viz import diagnostics


def _dim(label, size):
    return SimpleNamespace(label=label, size=size, stride=0)


def _msg(sections):
    """sections: list of (label, [values]); builds a fake Float64MultiArray."""
    data = []
    dims = []
    for label, values in sections:
        dims.append(_dim(label, len(values)))
        data.extend(values)
    return SimpleNamespace(layout=SimpleNamespace(dim=dims), data=data)


def test_parses_all_sections_by_label():
    msg = _msg([
        ('time', [12.5]),
        ('timing', [0.01, 42.0, 100.0, 0.0]),
        ('flags', [1.0, 0.0]),
        ('x', [0.1, 0.2, 0.3, 1.0, 2.0, 3.0]),
        ('ref', [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ('err', [0.1, 0.2, 0.3, 1.0, 2.0, 3.0]),
        ('u', [5.5]),
        ('xhat', []),
    ])
    f = diagnostics.parse(msg)
    assert f['t'] == 12.5
    assert f['period_s'] == 0.01
    assert f['update_us'] == 42.0
    assert f['rate_hz'] == 100.0
    assert f['deadline_miss'] is False
    assert f['valid'] is True
    assert f['safe_action'] == 'hold_u_eq'
    assert f['x'] == [0.1, 0.2, 0.3, 1.0, 2.0, 3.0]
    assert f['u'] == [5.5]
    assert f['xhat'] == []


def test_flags_decode_validity_and_safe_action():
    msg = _msg([
        ('time', [0.0]), ('timing', [0.0, 0.0, 0.0, 1.0]),
        ('flags', [0.0, 2.0]), ('x', [0.0, 0.0]),
        ('ref', []), ('err', []), ('u', []), ('xhat', []),
    ])
    f = diagnostics.parse(msg)
    assert f['valid'] is False
    assert f['deadline_miss'] is True
    assert f['safe_action'] == 'deactivate'


def test_missing_layout_is_rejected():
    import pytest
    bad = SimpleNamespace(layout=SimpleNamespace(dim=[]), data=[1.0, 2.0])
    with pytest.raises(ValueError):
        diagnostics.parse(bad)


def test_section_sizes():
    msg = _msg([('time', [0.0]), ('x', [1.0, 2.0, 3.0]), ('u', [4.0])])
    assert diagnostics.section_sizes(msg.layout) == {'time': 1, 'x': 3, 'u': 1}
