import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import OpaqueFunction
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable, EmitEvent, AppendEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node
from launch.events import Shutdown
from pathlib import Path

PACKAGE_NAME = "simbot_gz"

ARGUMENTS = [
    DeclareLaunchArgument('world', default_value='demo_world.sdf', description='Gazebo World file (with extension)'),
    DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use sim time if true'),
]

robot_model_list = [
    # '3w', 
    # '3w_v2',
    # '4w',
    # '5w',
    # '6w',
    'simbot_mecanum_waffle'
]

def launch_setup(context, *args, **kwargs):
    robot_model = os.environ.get("ROBOT_MODEL", "simbot_mecanum_waffle")

    if robot_model not in robot_model_list:
        error_msg = f"The robot model specified in environment variable ROBOT_MODEL is '{robot_model}', which is unknown.\nPlease choose from the following options:\n"

        for model in robot_model_list:
            error_msg += f"- {model}\n"
        
        print(error_msg)

        return LaunchDescription([
            EmitEvent(event=Shutdown(reason='Invalid robot model specified'))
        ])
    
    print("Robot model: ", robot_model)
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    # ld = LaunchDescription(ARGUMENTS)
    actions = []
    
    # Source Environment (Need it to be able find mesh files)
    pkg_path = get_package_share_directory(PACKAGE_NAME)
    actions.append(AppendEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=PathJoinSubstitution([pkg_path, 'worlds'])
    ))
    
    actions.append(AppendEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=PathJoinSubstitution([pkg_path, 'meshes'])
    ))
    
    # Add custom model path
    actions.append(AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        PathJoinSubstitution([pkg_path, 'models'])
    ))
    
    append_ign_path = AppendEnvironmentVariable(
        name='IGN_GAZEBO_RESOURCE_PATH',
        value='/ros2_ws/src/'
    )
    actions.append(append_ign_path)    
    
    append_gz_path = AppendEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value='/ros2_ws/src/'
    )
    actions.append(append_gz_path)

    # Create a robot_state_publisher node
    pkg_path = get_package_share_directory(PACKAGE_NAME)
    xacro_file = os.path.join(pkg_path,'urdf', robot_model, 'main.urdf.xacro')
    print(f"Loading {xacro_file}...")
    try:
        robot_description_config = Command(['xacro ', xacro_file])
    except():
        return LaunchDescription([
            EmitEvent(event=Shutdown(reason=f'Failed loading {xacro_file}'))
        ])
    
    print(f"Creating state publisher...")

    params = {'robot_description': robot_description_config, 'use_sim_time': use_sim_time, 'publish_frequency': 30.0}
    actions.append(Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[params]
    ))

    world_sdf_path = PathJoinSubstitution([pkg_path, 'worlds', LaunchConfiguration('world')])

    # launch gazebo
    print(f"Launching Gazebo with world {world_sdf_path}")
    gz_launch_path = PathJoinSubstitution([
        get_package_share_directory(PACKAGE_NAME), 'launch', 'gz.launch.py' # using local launch file with fixed debugger call
    ])
    # gz params explained: ruby /opt/ros/jazzy/opt/gz_tools_vendor/bin/gz sim --help
    debugger = LaunchConfiguration('debugger', default="false").perform(context)
    gdb_server = LaunchConfiguration("gdb_server", default="false").perform(context)
    gdb_server_port = LaunchConfiguration("gdb_server_port", default="3000").perform(context)
    
    actions.append(IncludeLaunchDescription(
        PythonLaunchDescriptionSource([gz_launch_path]),
        launch_arguments=[
            ('debugger', debugger),
            ('gdb_server', gdb_server),
            ('gdb_server_port', gdb_server_port),
            ('gz_args', [' -r', # run the simulation
                         ' -s', # server only (headless mode)
                         ' -v 4', # verbosity level (0-4)
                         ' --headless-rendering',
                         ' --render-engine ogre2',
                         ' --render-engine-api-backend vulkan'
                         ' --physics-engine gz-physics-dartsim-plugin ',
                         world_sdf_path])
        ]
    ))
    
    # Spawn the robot in Gazebo
    print(f"Spawning the robot...")
    actions.append(Node(package='ros_gz_sim', executable='create',
                        arguments=['-topic', 'robot_description',
                                   '-name', robot_model,
                                   '-z', '0.5'],
                        output='screen'))
    
    # gz bridge 
    print(f"Starting ROS-GZ bridge...")
    gz_bridge_params_file = os.path.join(get_package_share_directory(PACKAGE_NAME),'config', 'gz_bridge.yaml')
    actions.append(Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[{'config_file': gz_bridge_params_file}],
        arguments=[
            '--ros-args',
            '-p',
            f'config_file:={gz_bridge_params_file}',
        ]
    ))
    
    mecanum_remappings = '--ros-args --remap /mecanum_controller/odometry:=/odom --remap /mecanum_controller/reference:=/cmd_vel --remap /mecanum_controller/tf_odometry:=/tf'
    
    # Spawn joint_state_broadcaster
    print(f"Spawning joint state broadcaster...")
    actions.append(Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-ros-args', mecanum_remappings],
        output='screen',
    ))
    
    # , 

    # Spawn wheel controllers
    # num_wheels = 4
    # print(f"Spawning {num_wheels} wheel controllers...")
    # controller_names = [f'wheel{i+1}_controller' for i in range(num_wheels)]
    # spawn_wheel_controllers = Node(
    #     package='controller_manager',
    #     executable='spawner',
    #     arguments=controller_names,
    #     output='screen'
    # )
    
    print(f"Lading mecanum controller...")    
    actions.append(Node(
        package='controller_manager',
        executable='spawner',  # the spawner script/executable
        output='screen',
        arguments=[
            'mecanum_controller', # name of the controller to spawn
            '--controller-manager', '/controller_manager', # controller manager node name (if not default)
            '--controller-ros-args', mecanum_remappings
        ],
    ))
    
    # print(f"Lading top camera controller...")    
    # load_camera_joint_top_controller = Node(
    #     package='controller_manager',
    #     executable='spawner',
    #     output='screen',
    #     arguments=[
    #         'camera_joint_top_position_controller',
    #         '--controller-manager', '/controller_manager',
    #     ]
    # )

    # print(f"Making tf republisher node...")    
    # mecanum_tf_republisher_node = Node(
    #     package='simbot_gz',
    #     executable='mecanum_tf_republisher.py',
    #     name='tf_republisher',
    #     output='screen'
    # )

    # print(f"Making kinematics node...")    
    # kinematics = Node(
    #     package='simbot_gz',
    #     executable="kinematics",
    #     parameters=[{"use_sim_time": use_sim_time}]
    # )
    
    print(f"Making sim_extras node...")    
    actions.append(Node(
        package='simbot_gz',
        executable='sim_extras_publisher_async.py',
        name='sim_extras_publisher',
        parameters=[PathJoinSubstitution([
            FindPackageShare('simbot_gz'),
            'config',
            'sim_extras_config.yaml'
        ])],
        output='screen'
    ))
    
    print(f"Making range converter node...")    
    actions.append(Node(
        package=PACKAGE_NAME,
        executable='laser_to_range_async.py',  
        name='laser_to_range_converter',
        parameters=[PathJoinSubstitution([
            FindPackageShare(PACKAGE_NAME),
            'config',
            'range_config.yaml'
        ])],
        output='screen'
    ))

    # Launch the camera joint service node
    # print(f"Launching camera joint service...")    
    # camera_joint_service_node = Node(
    #     package='simbot_gz',
    #     executable='camera_joint_service.py',
    #     name='camera_joint_service',
    #     output='screen',
    # )

    # print(f"Setting camera joint position pub node...")    
    # set_camera_joint_position_pub_node = Node(
    #     package='simbot_gz',
    #     executable='set_camera_joint_position_pub.py',
    #     name='set_camera_joint_position_pub',
    #     output='screen',
    # )

    # Create launch description and add actions
    
    
    # for can_gz_bridge in can_bridges:
    #     ld.add_action(can_gz_bridge)
    # ld.add_action(spawn_wheel_controllers)
    
    
    # ld.add_action(load_camera_joint_top_controller)
    
    
    # ld.add_action(camera_joint_service_node)
    # ld.add_action(set_camera_joint_position_pub_node)
    # ld.add_action(mecanum_tf_republisher_node)
    # ld.add_action(kinematics)
    # ld.add_action(rviz_node)
    return actions

def generate_launch_description():
    
    return LaunchDescription(ARGUMENTS + [
        OpaqueFunction(function=launch_setup)
    ])
