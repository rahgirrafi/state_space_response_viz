"""MonitorState: the ROS-free buffer + SSE snapshot logic."""

from state_space_response_viz.monitor_state import MonitorState


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _frame(t):
    return {'t': t, 'x': [t], 'ref': [], 'err': [], 'u': [], 'xhat': [],
            'valid': True, 'safe_action': 'hold_u_eq'}


def test_push_and_snapshot_since_returns_new_frames():
    st = MonitorState(window_seconds=10.0, controller='/lqr_controller')
    st.push_frame(_frame(0.0))
    st.push_frame(_frame(0.1))
    snap = st.snapshot_since(0)
    assert len(snap['frames']) == 2
    assert snap['cursor'] == 2
    # A second call from the new cursor yields nothing until more arrive.
    assert st.snapshot_since(snap['cursor'])['frames'] == []
    st.push_frame(_frame(0.2))
    assert len(st.snapshot_since(snap['cursor'])['frames']) == 1


def test_snapshot_strips_internal_wall_field():
    st = MonitorState(window_seconds=10.0, controller='c')
    st.push_frame(_frame(0.0))
    assert '_wall' not in st.snapshot_since(0)['frames'][0]
    assert 'seq' in st.snapshot_since(0)['frames'][0]


def test_window_trims_by_wall_clock():
    clock = FakeClock()
    st = MonitorState(window_seconds=1.0, controller='c', clock=clock)
    for i in range(5):
        clock.t = i * 0.5           # 0.0, 0.5, 1.0, 1.5, 2.0
        st.push_frame(_frame(float(i)))
    _, frames = st.window_arrays()
    # Horizon at t=2.0 is 1.0; frames with wall < 1.0 (i=0,1) are dropped.
    assert [f['t'] for f in frames] == [2.0, 3.0, 4.0]


def test_meta_rev_bumps_only_on_change():
    st = MonitorState(window_seconds=10.0, controller='c')
    r0 = st.snapshot_since(0)['meta_rev']
    st.update_meta(has_diag=True)
    r1 = st.snapshot_since(0)['meta_rev']
    assert r1 == r0 + 1
    st.update_meta(has_diag=True)          # no change
    assert st.snapshot_since(0)['meta_rev'] == r1


def test_metrics_roundtrip():
    st = MonitorState(window_seconds=10.0, controller='c')
    st.set_metrics({'rms_error': 0.5})
    assert st.snapshot_since(0)['metrics'] == {'rms_error': 0.5}
