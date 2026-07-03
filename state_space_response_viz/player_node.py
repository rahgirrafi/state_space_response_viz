"""response_player: RobotTrajectory playback node.

Pure composition — PlaybackClock (what time is it?) × FrameSampler (what
does the robot look like then?) × TrajectoryRenderer (put it on screen).
The node itself only wires transport control to the clock:

    ros2 run state_space_response_viz response_player \
        --ros-args -p trajectory:=/path/to/trajectory.npz

    ros2 service call /response_player/pause std_srvs/srv/Trigger
    ros2 param set /response_player speed 0.5
    ros2 param set /response_player seek 1.25
"""

import json
import time

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from std_msgs.msg import Float64, String
from std_srvs.srv import Trigger

from state_space_control.trajectory import FrameSampler, RobotTrajectory

from .playback import PLAYING, PlaybackClock
from .renderers import RVizRenderer


class ResponsePlayer(Node):
    def __init__(self, **node_kwargs):
        super().__init__('response_player', **node_kwargs)
        self.declare_parameter('trajectory', '')
        self.declare_parameter('publish_rate', 60.0)
        self.declare_parameter('speed', 1.0)
        self.declare_parameter('seek', -1.0)
        self.declare_parameter('loop', False)
        self.declare_parameter('autoplay', True)
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('world_frame', 'world')

        path = self.get_parameter('trajectory').value
        if not path:
            raise ValueError(
                'the "trajectory" parameter is required: '
                '--ros-args -p trajectory:=/path/to/trajectory.npz')
        self.traj = RobotTrajectory.from_npz(path)   # validates on load
        self.sampler = FrameSampler(self.traj)
        self.clock = PlaybackClock(
            self.traj.duration,
            t0=float(self.traj.t[0]),
            speed=float(self.get_parameter('speed').value),
            loop=bool(self.get_parameter('loop').value),
        )
        self.renderers = [RVizRenderer(
            self,
            base_frame=self.get_parameter('base_frame').value,
            world_frame=self.get_parameter('world_frame').value,
        )]
        for r in self.renderers:
            r.setup(self.traj)

        self._time_pub = self.create_publisher(Float64, 'response_viz/time', 10)
        self._status_pub = self.create_publisher(
            String, 'response_viz/status', 10)
        self._event_pub = self.create_publisher(
            String, 'response_viz/events', 10)
        self._events = sorted(self.traj.events, key=lambda e: e.t)
        self._last_t = float(self.traj.t[0])

        self.create_service(Trigger, '~/play', self._srv_play)
        self.create_service(Trigger, '~/pause', self._srv_pause)
        self.create_service(Trigger, '~/reset', self._srv_reset)
        self.add_on_set_parameters_callback(self._on_params)

        rate = float(self.get_parameter('publish_rate').value)
        self.create_timer(1.0 / rate, self._tick)
        self.create_timer(0.5, self._publish_status)

        if bool(self.get_parameter('autoplay').value):
            self.clock.play(time.monotonic())
        self.get_logger().info(
            f'loaded {path}: {len(self.traj.t)} samples, '
            f'{self.traj.duration:.3f} s, joints {self.traj.joint_names}, '
            f'source {self.traj.meta.get("source", "unknown")!r}')

    # -- playback -----------------------------------------------------------

    def _tick(self):
        t = self.clock.now(time.monotonic())
        frame = self.sampler.frame_at(t)
        for r in self.renderers:
            r.render(frame)
        self._time_pub.publish(Float64(data=float(t)))
        self._publish_crossed_events(t)

    def _publish_crossed_events(self, t):
        if t < self._last_t:      # wrapped (loop) or sought backwards
            self._last_t = t
            return
        for ev in self._events:
            if self._last_t < ev.t <= t:
                self._event_pub.publish(String(data=json.dumps(ev.to_dict())))
        self._last_t = t

    def _publish_status(self):
        self._status_pub.publish(String(data=json.dumps({
            'state': self.clock.state,
            'speed': self.clock.speed,
            't': self.clock.now(time.monotonic()),
            'duration': self.traj.duration,
            'trajectory': self.get_parameter('trajectory').value,
        })))

    # -- transport ----------------------------------------------------------

    def _srv_play(self, _req, res):
        self.clock.play(time.monotonic())
        res.success, res.message = True, 'playing'
        return res

    def _srv_pause(self, _req, res):
        self.clock.pause(time.monotonic())
        res.success, res.message = True, f'paused at {self._last_t:.3f}s'
        return res

    def _srv_reset(self, _req, res):
        self.clock.reset()
        self._last_t = float(self.traj.t[0])
        res.success, res.message = True, 'reset'
        return res

    def _on_params(self, params):
        for p in params:
            if p.name == 'speed':
                try:
                    self.clock.set_speed(float(p.value), time.monotonic())
                except ValueError as exc:
                    return SetParametersResult(successful=False,
                                               reason=str(exc))
            elif p.name == 'seek':
                if float(p.value) >= 0.0:
                    self.clock.seek(float(p.value), time.monotonic())
                    self._last_t = self.clock.now(time.monotonic())
            elif p.name == 'loop':
                self.clock.loop = bool(p.value)
        return SetParametersResult(successful=True)


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ResponsePlayer()
    except (ValueError, FileNotFoundError) as exc:
        print(f'response_player: {exc}')
        rclpy.shutdown()
        return 1
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
