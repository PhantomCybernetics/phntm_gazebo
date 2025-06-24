import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable, EmitEvent, AppendEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node
from launch.events import Shutdown
from pathlib import Path

PACKAGE_NAME = "simbot_gz"

ARGUMENTS = [
    DeclareLaunchArgument('world', default_value='maze_2_brick.sdf', description='Gazebo World file (with extension)'),
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

def generate_launch_description():
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

    # Source Environment (Need it to be able find mesh files)
    pkg_path = get_package_share_directory(PACKAGE_NAME)
    ign_resource_path_worlds = AppendEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=PathJoinSubstitution([pkg_path, 'worlds'])
    )
    ign_resource_path_meshes = AppendEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=PathJoinSubstitution([pkg_path, 'meshes'])
    )
    
    # Add custom model path
    ign_resource_path_models = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        PathJoinSubstitution([pkg_path, 'models'])
    )
    
    append_ign_path = AppendEnvironmentVariable(
        name='IGN_GAZEBO_RESOURCE_PATH',
        value='/ros2_ws/src/'
    )
    
    append_gz_path = AppendEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value='/ros2_ws/src/'
    )

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
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[params]
    )

    world_path = PathJoinSubstitution([pkg_path, 'worlds', LaunchConfiguration('world')])

    # launch gazebo
    print(f"Launching Gazebo with world {world_path}")
    gazebo_launch_path = PathJoinSubstitution([
        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py'
    ])
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([gazebo_launch_path]),
        launch_arguments=[
            ('gz_args', [' -r',
                          ' -s',
                          ' -v 4',
                          ' --render-engine ogre2 ', world_path])
        ]
    )
    
    # Spawn the robot in Gazebo
    print(f"Spawning the robot...")
    spawn_robot = Node(package='ros_gz_sim', executable='create',
                        arguments=['-topic', 'robot_description',
                                   '-name', robot_model,
                                   '-z', '0.5'],
                        output='screen')
    
    # gz bridge 
    print(f"Starting ROS-GZ bridge...")
    gz_bridge_params_file = os.path.join(get_package_share_directory(PACKAGE_NAME),'config', 'gz_bridge.yaml')
    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[{'config_file': gz_bridge_params_file}],
        arguments=[
            '--ros-args',
            '-p',
            f'config_file:={gz_bridge_params_file}',
        ]
    )    
    
    mecanum_remappings = '--ros-args --remap /mecanum_controller/odometry:=/odom --remap /mecanum_controller/reference:=/cmd_vel --remap /mecanum_controller/tf_odometry:=/tf'
    
    # Spawn joint_state_broadcaster
    print(f"Spawning joint state broadcaster...")
    spawn_jsb = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-ros-args', mecanum_remappings],
        output='screen',
    )
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
    load_mecanum_controller = Node(
        package='controller_manager',
        executable='spawner',  # the spawner script/executable
        output='screen',
        arguments=[
            'mecanum_controller', # name of the controller to spawn
            '--controller-manager', '/controller_manager', # controller manager node name (if not default)
            '--controller-ros-args', mecanum_remappings
        ],
    )
    
    print(f"Lading top camera controller...")    
    load_camera_joint_top_controller = Node(
        package='controller_manager',
        executable='spawner',
        output='screen',
        arguments=[
            'camera_joint_top_position_controller',
            '--controller-manager', '/controller_manager',
        ]
    )

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

    # rviz_node = Node(
    #     package='rviz2',
    #     executable='rviz2',
    #     name='rviz2',
    #     output='screen',
    #     arguments=['-d', os.path.join(pkg_path, 'rviz', 'test.rviz')]
    # )
    
    print(f"Making sim_extras node...")    
    sim_extras_node = Node(
        package='simbot_gz',
        executable='sim_extras_publisher_async.py',
        name='sim_extras_publisher',
        parameters=[PathJoinSubstitution([
            FindPackageShare('simbot_gz'),
            'config',
            'sim_extras_config.yaml'
        ])],
        output='screen'
    )
    
    print(f"Making range converter node...")    
    range_converter_node = Node(
        package=PACKAGE_NAME,
        executable='laser_to_range_async.py',  
        name='laser_to_range_converter',
        parameters=[PathJoinSubstitution([
            FindPackageShare(PACKAGE_NAME),
            'config',
            'range_config.yaml'
        ])],
        output='screen'
    )

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
    ld = LaunchDescription(ARGUMENTS)
    ld.add_action(ign_resource_path_meshes)
    ld.add_action(ign_resource_path_worlds)
    ld.add_action(ign_resource_path_models)
    ld.add_action(append_ign_path)
    ld.add_action(append_gz_path)
    ld.add_action(node_robot_state_publisher)
    ld.add_action(gazebo)
    ld.add_action(spawn_robot)
    ld.add_action(ros_gz_bridge)
    # ld.add_action(spawn_wheel_controllers)
    ld.add_action(spawn_jsb)
    ld.add_action(load_mecanum_controller)
    ld.add_action(load_camera_joint_top_controller)
    ld.add_action(sim_extras_node)
    ld.add_action(range_converter_node)
    # ld.add_action(camera_joint_service_node)
    # ld.add_action(set_camera_joint_position_pub_node)
    # ld.add_action(mecanum_tf_republisher_node)
    # ld.add_action(kinematics)
    # ld.add_action(rviz_node)
    return ld

