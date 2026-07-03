"""response_player smoke tests: real rclpy node, spun briefly in-process."""

import time

import numpy as np
import pytest

rclpy = pytest.importorskip('rclpy')


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


def spin_for(node, seconds, extra=()):
    from rclpy.executors import SingleThreadedExecutor
    ex = SingleThreadedExecutor()
    ex.add_node(node)
    for n in extra:
        ex.add_node(n)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ex.spin_once(timeout_sec=0.05)
    ex.shutdown()


def make_player(traj_file, **params):
    from rclpy.parameter import Parameter
    from state_space_response_viz.player_node import ResponsePlayer
    overrides = [Parameter('trajectory', value=traj_file),
                 Parameter('publish_rate', value=200.0)]
    overrides += [Parameter(k, value=v) for k, v in params.items()]
    return ResponsePlayer(parameter_overrides=overrides)


def test_missing_trajectory_param_raises(ros):
    from state_space_response_viz.player_node import ResponsePlayer
    with pytest.raises(ValueError, match='trajectory'):
        node = ResponsePlayer()
        node.destroy_node()


def test_publishes_joint_states_and_time(ros, traj_file):
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Float64

    player = make_player(traj_file)
    listener = rclpy.create_node('listener')
    joint_msgs, time_msgs = [], []
    listener.create_subscription(JointState, 'joint_states',
                                 joint_msgs.append, 10)
    listener.create_subscription(Float64, 'response_viz/time',
                                 time_msgs.append, 10)
    try:
        spin_for(player, 0.5, extra=[listener])
    finally:
        player.destroy_node()
        listener.destroy_node()

    assert joint_msgs, 'no JointState received'
    msg = joint_msgs[-1]
    assert list(msg.name) == ['j1', 'j2']
    # Autoplay: the cursor moved, and time messages advanced monotonically
    # up to loop/end behavior (2 s trajectory, 0.5 s spin -> no wrap).
    assert time_msgs and time_msgs[-1].data > 0.0
    ts = [m.data for m in time_msgs]
    assert all(b >= a for a, b in zip(ts, ts[1:]))
    # Position matches the sampled sine at the reported time (loosely:
    # message and time are from adjacent ticks).
    assert msg.position[0] == pytest.approx(np.sin(ts[-1]), abs=0.05)


def test_seek_parameter_moves_cursor_when_paused(ros, traj_file):
    from rclpy.parameter import Parameter
    from sensor_msgs.msg import JointState

    player = make_player(traj_file, autoplay=False)
    player.set_parameters([Parameter('seek', value=1.5)])
    listener = rclpy.create_node('listener2')
    joint_msgs = []
    listener.create_subscription(JointState, 'joint_states',
                                 joint_msgs.append, 10)
    try:
        spin_for(player, 0.3, extra=[listener])
    finally:
        player.destroy_node()
        listener.destroy_node()

    assert joint_msgs
    # Paused at t=1.5: every frame renders q1 = sin(1.5), q2 = 0.75.
    for msg in joint_msgs[-3:]:
        assert msg.position[0] == pytest.approx(np.sin(1.5), abs=1e-6)
        assert msg.position[1] == pytest.approx(0.75, abs=1e-6)


def test_invalid_speed_parameter_rejected(ros, traj_file):
    from rclpy.parameter import Parameter

    player = make_player(traj_file, autoplay=False)
    try:
        result = player.set_parameters([Parameter('speed', value=0.0)])
        assert not result[0].successful
        assert 'speed' in result[0].reason
    finally:
        player.destroy_node()


def test_events_published_when_crossed(ros, traj_file):
    import json
    from std_msgs.msg import String

    player = make_player(traj_file, speed=8.0)   # crosses t=1.0 within spin
    listener = rclpy.create_node('listener3')
    events = []
    listener.create_subscription(String, 'response_viz/events',
                                 events.append, 10)
    try:
        spin_for(player, 0.5, extra=[listener])
    finally:
        player.destroy_node()
        listener.destroy_node()

    assert events, 'event at t=1.0 not published'
    payload = json.loads(events[0].data)
    assert payload['type'] == 'user' and payload['t'] == pytest.approx(1.0)
