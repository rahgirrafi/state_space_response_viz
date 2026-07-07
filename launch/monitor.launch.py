"""Start the live controller monitor dashboard.

    ros2 launch state_space_response_viz monitor.launch.py \
        controller:=/lqr_controller [port:=8080] [open:=true]

Enable the controller's diagnostics feed for the full set of panels, e.g. set
``publish_diagnostics: true`` in the controller_manager YAML (or pass it when
spawning). Then browse to http://<host>:<port>.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    args = [
        DeclareLaunchArgument('controller', default_value='/lqr_controller',
                              description='Controller namespace (its '
                                          '~/diagnostics feed is watched)'),
        DeclareLaunchArgument('host', default_value='127.0.0.1'),
        DeclareLaunchArgument('port', default_value='8080'),
        DeclareLaunchArgument('window_seconds', default_value='30.0'),
        DeclareLaunchArgument('stream_rate', default_value='25.0'),
        DeclareLaunchArgument('open', default_value='false',
                              description='Open the dashboard in a browser'),
    ]

    monitor = Node(
        package='state_space_response_viz',
        executable='response_monitor',
        output='screen',
        parameters=[{
            'controller': LaunchConfiguration('controller'),
            'host': LaunchConfiguration('host'),
            'port': ParameterValue(LaunchConfiguration('port'), value_type=int),
            'window_seconds': ParameterValue(
                LaunchConfiguration('window_seconds'), value_type=float),
            'stream_rate': ParameterValue(
                LaunchConfiguration('stream_rate'), value_type=float),
        }],
    )

    open_browser = TimerAction(
        period=1.5,
        actions=[ExecuteProcess(
            cmd=['xdg-open', ['http://', LaunchConfiguration('host'), ':',
                              LaunchConfiguration('port')]],
            shell=False)],
        condition=IfCondition(LaunchConfiguration('open')),
    )

    return LaunchDescription(args + [monitor, open_browser])
