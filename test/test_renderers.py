"""RVizRenderer against a fake node: correct JointState per frame."""

import numpy as np
import pytest

rclpy = pytest.importorskip('rclpy')

from state_space_control.trajectory import FrameSampler  # noqa: E402
from state_space_response_viz.renderers import RVizRenderer  # noqa: E402


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)


class FakeClock:
    def now(self):
        import rclpy.time
        return rclpy.time.Time()


class FakeNode:
    """Just enough of rclpy.node.Node for the renderer."""

    def __init__(self):
        self.publishers = {}

    def create_publisher(self, _type, topic, _qos):
        self.publishers[topic] = FakePublisher()
        return self.publishers[topic]

    def get_clock(self):
        return FakeClock()


def test_renders_all_joints_including_unactuated(traj):
    node = FakeNode()
    renderer = RVizRenderer(node)
    renderer.setup(traj)
    frame = FrameSampler(traj).frame_at(1.0)
    renderer.render(frame)

    msg = node.publishers['joint_states'].messages[-1]
    assert list(msg.name) == ['j1', 'j2']          # unactuated j2 included
    assert msg.position[0] == pytest.approx(np.sin(1.0))
    assert msg.position[1] == pytest.approx(0.5)
    assert msg.velocity[0] == pytest.approx(np.cos(1.0))


def test_fixed_base_creates_no_tf_broadcaster(traj):
    node = FakeNode()
    renderer = RVizRenderer(node)
    renderer.setup(traj)                            # base_pose is None
    assert renderer._tf is None
    renderer.render(FrameSampler(traj).frame_at(0.5))   # must not raise
