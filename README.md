# state_space_response_viz

Source-agnostic playback of **RobotTrajectory** files into RViz: animate a
URDF from a simulated (or recorded) motion, with play/pause/seek/speed
transport control.

```
ros2 launch state_space_response_viz view_response.launch.py \
    trajectory:=/path/to/trajectory.npz \
    urdf:=/path/to/robot.urdf [fixed_frame:=base_link] [speed:=1.0] [loop:=true]
```

Transport at runtime:

```
ros2 service call /response_player/pause std_srvs/srv/Trigger
ros2 service call /response_player/play  std_srvs/srv/Trigger
ros2 service call /response_player/reset std_srvs/srv/Trigger
ros2 param set /response_player speed 0.5      # 0.25x .. 2x (any 0.01..10)
ros2 param set /response_player seek 1.25      # jump to t = 1.25 s
```

## The canonical trajectory format

`RobotTrajectory` (`state_space_control.trajectory`, npz schema
`robot_trajectory/1`) is the framework's **interchange format**, not an
export by-product: producers (the Setup Assistant's linear closed-loop
simulation today; nonlinear simulators, MuJoCo, rosbag importers, real-robot
logs later) write it, consumers (this package, the web wizard's Response
step, benchmark playback, report/video export later) read it, and neither
side knows about the other. This node requires only a *valid trajectory* —
its tests run against hand-built files, never against a simulation.

Contents: time `t`, **absolute** joint positions `q` and velocities `qd`
(producers apply the operating-point offset; consumers never see deviation
coordinates), optional inputs `u` (stored as u − u_eq), optional
`base_pose (N,7)`/`base_twist (N,6)` for mobile/floating-base robots
(`base_pose` absent *means* fixed base — no identity transform is invented),
time-stamped **events** (limit violations, linear-validity excursions,
instability, settling, user annotations — unknown types are ignored), and
self-describing **meta** (source, robot + URDF sha256, operating point,
controller type/params, excitation, solver settings, package versions,
timestamp) so a trajectory is reproducible from the file alone.

Mimic joints are intentionally absent from trajectories;
`robot_state_publisher` (and the wizard's three.js viewer) derive them from
the URDF.

## Architecture: clock × sampler × renderer

- **PlaybackClock** (`playback.py`) — what simulation time is it?
  Play/pause/seek/speed with anchor rebasing (speed changes never jump);
  pose is a function of monotonic wall time, never an index++ per tick, so
  timer jitter and dropped frames cannot desynchronize playback.
- **FrameSampler** (`state_space_control.trajectory`) — what does the robot
  look like at time t? Owns interpolation (linear; hold available; slerp for
  base quaternions). A future 30 fps video exporter reuses exactly this.
- **TrajectoryRenderer** (`renderers.py`) — put the sampled frame on a
  screen. `RVizRenderer` publishes `sensor_msgs/JointState` for **every**
  joint in the trajectory (omitting unactuated joints would leave their TF
  stale) plus a world→base TF when a base pose is present; those transport
  details stay hidden behind `setup(traj)`/`render(frame)`. To render
  elsewhere (Foxglove, video, …), implement those two methods and add the
  instance to the player's renderer list.

## Topics / services / parameters

| Name | Type | Notes |
|---|---|---|
| `/joint_states` | sensor_msgs/JointState | published at `publish_rate` (60 Hz default) |
| `/response_viz/time` | std_msgs/Float64 | current sim time (external sync cursor) |
| `/response_viz/status` | std_msgs/String (JSON) | `{state, speed, t, duration, trajectory}` at 2 Hz |
| `/response_viz/events` | std_msgs/String (JSON) | each TrajectoryEvent as the cursor crosses it |
| `~/play` `~/pause` `~/reset` | std_srvs/Trigger | transport |
| `trajectory, publish_rate, speed, seek, loop, autoplay, base_frame, world_frame` | parameters | `speed`/`seek`/`loop` dynamic |

No custom interfaces — the package stays pure ament_python.

## Future work

Side-by-side controller comparison (two players under namespaces with
`frame_prefix`-ed robot_state_publishers, slaved to one `/response_viz/time`),
reference-tracking excitations, force/torque arrow rendering, video export,
rosbag→RobotTrajectory importer. All fit the existing format and interfaces;
none require redesign.

## Tests

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/state_space_response_viz/test/
```
