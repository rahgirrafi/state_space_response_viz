"""TrajectoryRenderer: put a sampled RobotFrame on a screen.

The playback engine operates on frames and delegates to whichever
renderers are active — how a frame becomes pixels (JointState + TF for
RViz, setJointValue for the web viewer, an encoder for video export) is an
implementation detail hidden behind ``render(frame)``. Renderers hold
transport handles created in ``setup``; they are stateless between frames.
"""

from typing import Optional

from state_space_control.trajectory import RobotFrame, RobotTrajectory


class TrajectoryRenderer:
    """Interface: ``setup`` once before playback, ``render`` per frame."""

    def setup(self, traj: RobotTrajectory) -> None:
        pass

    def render(self, frame: RobotFrame) -> None:
        raise NotImplementedError


class RVizRenderer(TrajectoryRenderer):
    """Renders frames into RViz by publishing sensor_msgs/JointState (and a
    world→base TF when the trajectory carries a base pose). Those transport
    details stay invisible above this class.

    Mimic joints are intentionally absent from trajectories —
    robot_state_publisher derives them from the URDF.
    """

    def __init__(self, node, *, joint_states_topic: str = 'joint_states',
                 base_frame: str = 'base_link', world_frame: str = 'world'):
        self._node = node
        self._topic = joint_states_topic
        self._base_frame = base_frame
        self._world_frame = world_frame
        self._pub = None
        self._tf = None
        self._names = []

    def setup(self, traj: RobotTrajectory) -> None:
        from sensor_msgs.msg import JointState
        self._names = list(traj.joint_names)
        self._pub = self._node.create_publisher(JointState, self._topic, 10)
        if traj.base_pose is not None:
            from tf2_ros import TransformBroadcaster
            self._tf = TransformBroadcaster(self._node)

    def render(self, frame: RobotFrame) -> None:
        from sensor_msgs.msg import JointState
        msg = JointState()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        # Every joint in the trajectory, actuated or not: omitting the
        # unactuated ones would leave their TF stale in RViz.
        msg.name = self._names
        msg.position = [frame.joint_positions[n] for n in self._names]
        msg.velocity = [frame.joint_velocities[n] for n in self._names]
        self._pub.publish(msg)
        if self._tf is not None and frame.base_pose is not None:
            self._tf.sendTransform(self._base_transform(frame, msg.header.stamp))

    def _base_transform(self, frame: RobotFrame, stamp):
        from geometry_msgs.msg import TransformStamped
        tfm = TransformStamped()
        tfm.header.stamp = stamp
        tfm.header.frame_id = self._world_frame
        tfm.child_frame_id = self._base_frame
        x, y, z, qx, qy, qz, qw = (float(v) for v in frame.base_pose)
        tfm.transform.translation.x = x
        tfm.transform.translation.y = y
        tfm.transform.translation.z = z
        tfm.transform.rotation.x = qx
        tfm.transform.rotation.y = qy
        tfm.transform.rotation.z = qz
        tfm.transform.rotation.w = qw
        return tfm
