"""response_monitor: a live web dashboard of a running controller.

Subscribes to a Kontrol'Em controller's ``~/diagnostics`` feed (enable it with
``publish_diagnostics:=true`` on the controller) and to ``/joint_states``, keeps
a sliding window of samples, and serves a same-origin Flask + SSE dashboard so a
control engineer can watch reference/output/error/effort/observer/timing live
while a simulation runs.

    ros2 run state_space_response_viz response_monitor \
        --ros-args -p controller:=/lqr_controller

Then open http://127.0.0.1:8080. Without the diagnostics feed the node still
shows the passively observable signals (measured joint positions/velocities and,
if published, the ``~/reference`` setpoint); the effort/observer/timing panels
grey out until ``publish_diagnostics`` is on.
"""

import json
import threading
from typing import Dict, List, Optional

import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray, String

from . import diagnostics, metrics
from .monitor_state import MonitorState


class ResponseMonitor(Node):
    def __init__(self, **node_kwargs):
        super().__init__('response_monitor', **node_kwargs)
        self.declare_parameter('controller', '/lqr_controller')
        self.declare_parameter('diagnostics_topic', '')
        self.declare_parameter('reference_topic', '')
        self.declare_parameter('joint_states_topic', '/joint_states')
        self.declare_parameter('window_seconds', 30.0)
        self.declare_parameter('host', '127.0.0.1')
        self.declare_parameter('port', 8080)
        self.declare_parameter('stream_rate', 25.0)
        self.declare_parameter('band', 0.02)

        controller = self.get_parameter('controller').value.rstrip('/')
        diag_topic = self.get_parameter('diagnostics_topic').value \
            or f'{controller}/diagnostics'
        ref_topic = self.get_parameter('reference_topic').value \
            or f'{controller}/reference'
        js_topic = self.get_parameter('joint_states_topic').value
        self._band = float(self.get_parameter('band').value)

        self.state = MonitorState(
            self.get_parameter('window_seconds').value, controller)

        self._last_ref: Optional[List[float]] = None
        self._diag_seen = False

        self.create_subscription(
            Float64MultiArray, diag_topic, self._on_diagnostics, 10)
        self.create_subscription(
            Float64MultiArray, ref_topic, self._on_reference, 10)
        self.create_subscription(
            JointState, js_topic, self._on_joint_states, 10)
        # Latched channel-label metadata (published once, transient-local).
        info_qos = QoSProfile(
            depth=1, history=QoSHistoryPolicy.KEEP_LAST,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            String, f'{controller}/diagnostics_info', self._on_info, info_qos)
        self.create_timer(0.2, self._recompute_metrics)

        host = self.get_parameter('host').value
        port = int(self.get_parameter('port').value)
        rate = float(self.get_parameter('stream_rate').value)
        self._start_server(host, port, rate)
        self.get_logger().info(
            f'response_monitor: watching {diag_topic!r}; dashboard at '
            f'http://{host}:{port}  (enable publish_diagnostics on the '
            f'controller for the full feed)')

    # -- ROS callbacks ------------------------------------------------------
    def _on_info(self, msg: String):
        """Latched channel-label metadata from the controller (authoritative
        joint order); builds display labels so the dashboard need not guess."""
        try:
            info = json.loads(msg.data)
        except (ValueError, TypeError):
            return
        joints = info.get('joints', [])
        labels = {
            'error': info.get('error', []),
            'command': info.get('command', []),
            'position': [f'{j}' for j in joints],
            'velocity': [f'{j}' for j in joints],
        }
        self.state.update_meta(labels=labels, joint_names=joints)

    def _on_diagnostics(self, msg: Float64MultiArray):
        try:
            frame = diagnostics.parse(msg)
        except ValueError:
            return
        if not self._diag_seen:
            self._diag_seen = True
            self.state.update_meta(
                has_diag=True,
                sections=diagnostics.section_sizes(msg.layout))
        self.state.update_meta(safe_action=frame['safe_action'])
        self.state.push_frame(frame)

    def _on_reference(self, msg: Float64MultiArray):
        self._last_ref = [float(v) for v in msg.data]

    def _on_joint_states(self, msg: JointState):
        if msg.name:
            self.state.update_meta(joint_names=list(msg.name))
        if self._diag_seen:
            return   # diagnostics carries a richer, controller-synced frame
        n = len(msg.position)
        x = list(msg.position) + (list(msg.velocity) if msg.velocity else [0.0] * n)
        self.state.push_frame({
            't': self.get_clock().now().nanoseconds * 1e-9,
            'x': x, 'ref': self._last_ref or [], 'err': [], 'u': [],
            'xhat': [], 'period_s': 0.0, 'update_us': 0.0, 'rate_hz': 0.0,
            'deadline_miss': False, 'valid': True, 'safe_action': 'hold_u_eq',
        })

    # -- periodic metrics ---------------------------------------------------
    def _recompute_metrics(self):
        t, frames = self.state.window_arrays()
        if len(frames) < 2:
            return
        out: Dict = {'window_seconds': self.state.window_seconds}

        err_rows = [f['err'] for f in frames if f['err']]
        if err_rows:
            width = min(len(r) for r in err_rows)
            channels = [[r[i] for r in err_rows] for i in range(width)]
            out['error'] = metrics.channel_metrics(t, channels, self._band)
            allerr = np.concatenate([np.asarray(c) for c in channels]) \
                if channels else np.array([])
            out['rms_error'] = metrics.rms_error(allerr)

        rates = [f['rate_hz'] for f in frames if f['rate_hz'] > 0]
        ups = [f['update_us'] for f in frames if f['update_us'] > 0]
        misses = sum(1 for f in frames if f['deadline_miss'])
        if rates:
            out['timing'] = {
                'rate_hz': float(np.median(rates)),
                'update_us_mean': float(np.mean(ups)) if ups else 0.0,
                'update_us_max': float(np.max(ups)) if ups else 0.0,
                'deadline_misses': int(misses),
                'samples': len(frames),
            }
        self.state.set_metrics(out)

    # -- server -------------------------------------------------------------
    def _start_server(self, host: str, port: int, rate: float):
        from .monitor_server import create_app
        app = create_app(self.state, stream_rate=rate)
        thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, threaded=True,
                                   use_reloader=False, debug=False),
            daemon=True)
        thread.start()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ResponseMonitor()
    except Exception as exc:   # noqa: BLE001 - surface startup errors cleanly
        print(f'response_monitor: {exc}')
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
