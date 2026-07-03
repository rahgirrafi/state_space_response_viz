"""Hand-built trajectories: the viz package is source-agnostic, so no test
here may import the simulator or any URDF tooling."""

import numpy as np
import pytest

from state_space_control.trajectory import RobotTrajectory, TrajectoryEvent


@pytest.fixture
def traj():
    t = np.linspace(0.0, 2.0, 21)
    return RobotTrajectory(
        t=t,
        q=np.column_stack([np.sin(t), 0.5 * t]),
        qd=np.column_stack([np.cos(t), np.full_like(t, 0.5)]),
        joint_names=['j1', 'j2'],
        actuated_joint_names=['j1'],
        u=np.cos(t)[:, None],
        events=[TrajectoryEvent(t=1.0, type='user', message='midpoint')],
        meta={'source': 'hand-built'},
    )


@pytest.fixture
def traj_file(traj, tmp_path):
    path = str(tmp_path / 'traj.npz')
    traj.save_npz(path)
    return path
