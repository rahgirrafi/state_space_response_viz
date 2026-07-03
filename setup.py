import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'state_space_response_viz'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=False,
    maintainer='rahgirrafi',
    maintainer_email='rahgirrafi@gmail.com',
    description='RViz playback for RobotTrajectory files: animate a URDF '
                'from simulated or recorded closed-loop responses.',
    license='BSD-3-Clause',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'response_player = state_space_response_viz.player_node:main',
        ],
    },
)
