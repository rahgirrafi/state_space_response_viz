"""Play a RobotTrajectory npz on its URDF in RViz.

    ros2 launch state_space_response_viz view_response.launch.py \
        trajectory:=/path/to/trajectory.npz \
        urdf:=/path/to/robot.urdf [fixed_frame:=base_link] [speed:=1.0]
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    rviz_config = PathJoinSubstitution(
        [FindPackageShare('state_space_response_viz'), 'rviz', 'response.rviz'])

    args = [
        DeclareLaunchArgument('trajectory',
                              description='RobotTrajectory .npz to play'),
        DeclareLaunchArgument('urdf', description='URDF (or xacro) file'),
        DeclareLaunchArgument('fixed_frame', default_value='base_link',
                              description='RViz fixed frame (URDF root link)'),
        DeclareLaunchArgument('speed', default_value='1.0'),
        DeclareLaunchArgument('loop', default_value='false'),
        DeclareLaunchArgument('publish_rate', default_value='60.0'),
        DeclareLaunchArgument('rviz', default_value='true'),
    ]

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': ParameterValue(
            # xacro passes plain URDF through untouched, so this handles both.
            Command(['xacro ', LaunchConfiguration('urdf')]), value_type=str)}],
    )

    player = Node(
        package='state_space_response_viz',
        executable='response_player',
        parameters=[{
            'trajectory': LaunchConfiguration('trajectory'),
            'speed': ParameterValue(LaunchConfiguration('speed'),
                                    value_type=float),
            'loop': ParameterValue(LaunchConfiguration('loop'),
                                   value_type=bool),
            'publish_rate': ParameterValue(LaunchConfiguration('publish_rate'),
                                           value_type=float),
        }],
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config,
                   '-f', LaunchConfiguration('fixed_frame')],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return LaunchDescription(args + [robot_state_publisher, player, rviz])
