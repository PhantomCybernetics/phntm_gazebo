import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import OpaqueFunction, ExecuteProcess, RegisterEventHandler
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable, EmitEvent, AppendEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node
from launch.events import Shutdown
from launch.event_handlers import OnProcessExit
from moveit_configs_utils import MoveItConfigsBuilder
from pathlib import Path
import yaml
import time

PACKAGE_NAME = "phntm_gazebo"

ARGUMENTS = [
    DeclareLaunchArgument(
        'world',
        default_value='demo_world.sdf',
        description='Gazebo World file (with extension)'
    ),
    DeclareLaunchArgument(
        'use_sim_time',
        default_value='True',
        description='Use sim time if true'
    ),
    DeclareLaunchArgument(
        'camera_top_z',
        default_value='2.0',
        description='Position of the top-down camera above the robot'
    ),
    DeclareLaunchArgument(
        'cameras_pixel_format',
        default_value='RGB_INT8',
        description='Internal format used by the camera'
    ),
    DeclareLaunchArgument(
        'encoder_hw_device',
        default_value='cuda',
        description='H264 encoder hw device ("cuda", "vaapi" or "sw")'
    ),
    DeclareLaunchArgument(
        'encoder_bit_rate',
        default_value='2000000',
        description='H264 encoder bit rate'
    ),
    DeclareLaunchArgument(
        'encoder_thread_count',
        default_value='2',
        description='H264 encoder thread count'
    ),
    DeclareLaunchArgument(
        'encoder_input_pixel_format',
        default_value='nv12',
        description='Force H264 encoder input format ("nv12", "rgb0", "bgr0", etc)'
    ),
     DeclareLaunchArgument(
        'cameras_resolution',
        default_value='1280x720',
        description='Set resolution for cameras'
    ),
]

robot_model_list = [
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
    use_sim_time = LaunchConfiguration('use_sim_time', default='True')

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
    cameras_resolution_str = LaunchConfiguration('cameras_resolution').perform(context);
    parts = cameras_resolution_str.split('x')
    cameras_width = 1280
    cameras_height = 720
    if len(parts) == 2:
        cameras_width = parts[0]
        cameras_height = parts[1]
    print("cameras_width=", cameras_width, "cameras_height=", cameras_height, parts)
    print(f"Loading {xacro_file}...")
    try:
        robot_description_config = Command(['xacro ', xacro_file,
                                            ' camera_top_z:=', LaunchConfiguration('camera_top_z'),
                                            ' cameras_width:=', str(cameras_width),
                                            ' cameras_height:=', str(cameras_height),
                                            ' cameras_pixel_format:=', LaunchConfiguration('cameras_pixel_format'),
                                            ' encoder_hw_device:=', LaunchConfiguration('encoder_hw_device'),
                                            ' encoder_bit_rate:=', LaunchConfiguration('encoder_bit_rate'),
                                            ' encoder_thread_count:=', LaunchConfiguration('encoder_thread_count'),
                                            ' encoder_input_pixel_format:=', LaunchConfiguration('encoder_input_pixel_format')
                                            ])
    except():
        return LaunchDescription([
            EmitEvent(event=Shutdown(reason=f'Failed loading {xacro_file}'))
        ])
    
    print(f"Creating state publisher...")
    params = {
        'robot_description': robot_description_config,
        'use_sim_time': use_sim_time,
        'publish_frequency': 90.0,
    }
    actions.append(Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[params]
    ))

    world_sdf_path = PathJoinSubstitution([pkg_path, 'worlds', LaunchConfiguration('world')])

    # launch modified gazebo
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
                         ' --render-engine-api-backend opengl', # was vulkan
                         ' ',
                         world_sdf_path])
        ]
    ))
    # ' --physics-engine gz-physics-bullet-plugin ',
    
    position_x = LaunchConfiguration('position_x', default='0.0')
    position_y = LaunchConfiguration('position_y', default='0.0')
    position_z = LaunchConfiguration('position_z', default='0.5')
    orientation_yaw = LaunchConfiguration('orientation_yaw', default='0.0')
    
    # Spawn the robot in Gazebo
    print(f"Spawning the robot...")
    actions.append(Node(package='ros_gz_sim', executable='create',
                        arguments=['-topic', 'robot_description',
                                   '-name', robot_model,
                                   '-x', position_x,
                                   '-y', position_y,
                                   '-z', position_z,
                                   '-Y', orientation_yaw,
                                   ],
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
    
    mecanum_remappings = '--ros-args --remap /mecanum_controller/odometry:=/odom' \
                                 + ' --remap /mecanum_controller/reference:=/cmd_vel' \
                                 + ' --remap /mecanum_controller/tf_odometry:=/tf'
    
    # Spawn joint_state_broadcaster
    print(f"Spawning joint state broadcaster...")
    actions.append(Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-ros-args', mecanum_remappings
                   ],
        output='screen',
    ))
    
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

    # print(f"Making kinematics node...")    
    # kinematics = Node(
    #     package='phntm_gazebo',
    #     executable="kinematics",
    #     parameters=[{"use_sim_time": use_sim_time}]
    # )
    
    print(f"Making sim_extras node...")    
    actions.append(Node(
        package=PACKAGE_NAME,
        executable='sim_extras_publisher.py',
        name='sim_extras_publisher',
        parameters=[PathJoinSubstitution([
            FindPackageShare(PACKAGE_NAME),
            'config', 'sim_extras_config.yaml'
        ]), { 'camera_top_z': LaunchConfiguration('camera_top_z') }],
        output='screen',
    ))
    
    print(f"Making range converter node...")    
    actions.append(Node(
        package=PACKAGE_NAME,
        executable='laser_to_range_converter.py',  
        name='laser_to_range_converter',
        parameters=[PathJoinSubstitution([
            FindPackageShare(PACKAGE_NAME),
            'config', 'range_config.yaml'
        ])],
        output='screen'
    ))
    
    
    kuka_robot_name = LaunchConfiguration('kuka_robot_name', default='kuka_arm')
    kuka_namespace = LaunchConfiguration('kuka_namespace', default='kuka')
    kuka_gripper_name = LaunchConfiguration('kuka_gripper_name', default='robotiq_2f_140')
    kuka_position_x = LaunchConfiguration('kuka_position_x', default='0.0')
    kuka_position_y = LaunchConfiguration('kuka_position_y', default='-7.0')
    kuka_orientation_yaw = LaunchConfiguration('kuka_orientation_yaw', default='0.0')

    kuka_robot_name_val = kuka_robot_name.perform(context)
    kuka_namespace_val = kuka_namespace.perform(context)
    kuka_gripper_name_val = kuka_gripper_name.perform(context)
    
    print(f"Loading Kuka Robot [{kuka_gripper_name_val}] with name: {kuka_robot_name_val}, namespace: {kuka_namespace_val}")
    
    if kuka_gripper_name_val == "robotiq_2f_85":
        kuka_controller_yaml = "kuka_2f85_controllers.yaml"
        kuka_moveit_pkg = "kuka_2f85_moveit"
    elif kuka_gripper_name_val == "robotiq_2f_140": # default
        kuka_controller_yaml = "kuka_2f140_controllers.yaml"
        kuka_moveit_pkg = "kuka_2f140_moveit"
    else:
        kuka_controller_yaml = "kuka_controllers.yaml"
        kuka_moveit_pkg = "kuka_moveit"
    
    kuka_description_pkg_dir = get_package_share_directory('kuka_description')
    
    kuka_controller_file = rewrite_yaml(
        source_file= os.path.join(get_package_share_directory(PACKAGE_NAME), 'config', kuka_controller_yaml),
        root_key=kuka_namespace_val
    )

    # Loading Kuka Robot Model ------------------------------------------------------------------------------------------
    robot_xacro = Command([
        'xacro ', os.path.join(kuka_description_pkg_dir, 'urdf/kr70_r2100.urdf.xacro'),
        ' robot_name:=', kuka_robot_name,
        ' namespace:=', kuka_namespace,
        ' gripper_name:=', kuka_gripper_name,
        ' controller_file:=', kuka_controller_file,
        ' cameras_width:=', str(cameras_width),
        ' cameras_height:=', str(cameras_height),
        ' cameras_pixel_format:=', LaunchConfiguration('cameras_pixel_format'),
        ' encoder_hw_device:=', LaunchConfiguration('encoder_hw_device'),
        ' encoder_bit_rate:=', LaunchConfiguration('encoder_bit_rate'),
        ' encoder_thread_count:=', LaunchConfiguration('encoder_thread_count'),
        ' encoder_input_pixel_format:=', LaunchConfiguration('encoder_input_pixel_format')
        ])
    
    #kuka_robot_description = {"robot_description": robot_xacro}
    kuka_params = {
        'robot_description': robot_xacro,
        'use_sim_time': use_sim_time,
        'publish_frequency': 90.0,
    }
     
    # Publish TF
    kuka_remappings = [("/tf", "tf"), ("/tf_static", "tf_static")]
    # kuka_remappings_str = '--ros-args --remap /mecanum_controller/odometry:=/odom' \
    #                               + ' --remap /mecanum_controller/reference:=/cmd_vel' \
    #                               + ' --remap /mecanum_controller/tf_odometry:=/tf'
    actions.append(Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher_kuka",
        namespace=kuka_namespace,
        remappings=kuka_remappings,
        output="both",
        parameters=[kuka_params]
    ))

    # Spawn Robot in Gazebo
    spawn_kuka_robot_node = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-topic", f"{kuka_namespace_val}/robot_description",
            "-name", kuka_robot_name,
            "-robot_namespace", kuka_namespace,
            "-x", kuka_position_x,
            "-y", kuka_position_y,
            "-Y", kuka_orientation_yaw,
        ],
        output="both"
    )
    actions.append(spawn_kuka_robot_node)
    
     # Load Controllers
    # kuka_joint_state_controller = ExecuteProcess(
    #     cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 'joint_state_broadcaster', '-c', f"{kuka_namespace_val}/controller_manager"],
    #     output="screen"
    # )

    print(f"Spawning Kuka joint state broadcaster...")
    kuka_joint_state_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-manager', f'{kuka_namespace_val}/controller_manager', # controller manager node name (if not default)
                #    '--controller-ros-args', kuka_remappings
                   ],
        # namespace=kuka_namespace,
        output='screen'
    )
    #actions.append(kuka_joint_state_controller)

    # kuka_arm_controller = ExecuteProcess(
    #     cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 'kuka_arm_controller', '-c', f"{kuka_namespace_val}/controller_manager"],
    #     output="screen"
    # )
    
    print(f"Spawning Kuka arm controller...")
    kuka_arm_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['kuka_arm_controller',
                   '--controller-manager', f'{kuka_namespace_val}/controller_manager' # controller manager node name (if not default)
                   ],
        # namespace=kuka_namespace,
        #remappings=kuka_remappings,
        output='screen',
    )
    #actions.append(kuka_arm_controller)
    
    kuka_robotiq_controller = None
    if kuka_gripper_name_val == "robotiq_2f_85":
        kuka_robotiq_controller = ExecuteProcess(
            cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 'robotiq_2f85_controller', '-c', f"{kuka_namespace_val}/controller_manager"],
            output="screen"
        )
    elif kuka_gripper_name_val == "robotiq_2f_140": # default
        kuka_robotiq_controller = ExecuteProcess(
            cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 'robotiq_2f140_controller', '-c', f"{kuka_namespace_val}/controller_manager"],
            output="screen"
        )
    else:
        kuka_robotiq_controller = ExecuteProcess(
            cmd=['echo', '"No grippers loaded"'],
            output="screen"
        )
    
    actions.append(RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_kuka_robot_node,
            on_exit=[
                kuka_joint_state_controller,
                kuka_arm_controller,
                kuka_robotiq_controller
            ]
        )
    ))
    
    # moveit 
    # moveit_config = (
    #     MoveItConfigsBuilder("kr70_r2100", package_name=kuka_moveit_pkg)
    #     .robot_description(
    #         file_path="config/kr70_r2100.urdf.xacro",
    #         mappings={
    #             "robot_name": kuka_robot_name_val,
    #             "namespace": kuka_namespace_val,
    #             "gripper_name": kuka_gripper_name_val,
    #             "controller_file": kuka_controller_file,
    #         }
    #     )
    #     .planning_pipelines("pilz_industrial_motion_planner")
    #     .joint_limits(file_path="config/joint_limits.yaml")
    #     .robot_description_kinematics(file_path="config/kinematics.yaml")
    #     .robot_description_semantic(file_path="config/kr70_r2100.srdf")
    #     .trajectory_execution(file_path="config/moveit_controllers.yaml")
    #     .pilz_cartesian_limits(file_path="config/pilz_cartesian_limits.yaml")
    #     .to_moveit_configs()
    # )

    # planning_scene_parameters={
    #     "publish_planning_scene": True,
    #     "publish_geometry_updates": True,
    #     "publish_state_updates": True,
    #     "publish_transforms_updates": True,
    #     "publish_robot_description": True,
    #     "publish_robot_description_semantic": True
    # }

    # ompl_planning_pipeline_config = {
    #     "ompl": {
    #         "planning_plugin": "ompl_interface/OMPLPlanner",
    #         "request_adapters": [
    #             "default_planner_request_adapters/AddTimeOptimalParameterization",
    #             "default_planner_request_adapters/ResolveConstraintFrames",
    #             "default_planner_request_adapters/FixWorkspaceBounds",
    #             "default_planner_request_adapters/FixStartStateBounds",
    #             "default_planner_request_adapters/FixStartStateCollision",
    #             "default_planner_request_adapters/FixStartStatePathConstraints"
    #         ],
    #         "start_state_max_bounds_error": 0.1,
    #     },
    # }

    # ompl_planning_yaml = load_yaml(
    #     get_package_share_directory(kuka_moveit_pkg), "config/ompl_planning.yaml"
    # )

    # #ompl_planning_pipeline_config["ompl"].update(ompl_planning_yaml)

    # pilz_pipeline = {
    #         'pilz_industrial_motion_planner': {
    #         'planning_plugin': 'pilz_industrial_motion_planner/CommandPlanner', 
    #         # 'request_adapters': 'default_planner_request_adapters/FixWorkspaceBounds default_planner_request_adapters/FixStartStateBounds default_planner_request_adapters/FixStartStateCollision default_planner_request_adapters/FixStartStatePathConstraints', 
    #         "request_adapters": [ "" ],
    #         "start_state_max_bounds_error": 0.1,
    #         'default_planner_config': 'PTP', 
    #         'capabilities': 'pilz_industrial_motion_planner/MoveGroupSequenceAction pilz_industrial_motion_planner/MoveGroupSequenceService'
    #     }
    # }

    # move_group_node = Node(
    #     package="moveit_ros_move_group",
    #     executable="move_group",
    #     namespace=kuka_namespace_val,
    #     output="screen",
    #     parameters=[
    #         moveit_config.to_dict(),
    #         planning_scene_parameters,
    #         ompl_planning_pipeline_config,
    #         pilz_pipeline,
    #         {"use_sim_time": use_sim_time}
    #     ]
    # )
    # #actions.append(move_group_node)

    # load_move_group = RegisterEventHandler(
    #     event_handler=OnProcessExit(
    #         target_action=kuka_robotiq_controller,
    #         on_exit=[move_group_node]
    #     )
    # )
    # actions.append(load_move_group)

    # *** PLANNING CONTEXT *** #
    # Robot description SRDF
    robot_description_semantic_config = load_file(kuka_moveit_pkg, "config/kr70_r2100.srdf")
    robot_description_semantic = {"robot_description_semantic": robot_description_semantic_config}

    # Kinematics YAML file
    kinematics_yaml = load_yaml(get_package_share_directory(kuka_moveit_pkg), "config/kinematics.yaml")

    # actions.append(Node(
    #     package="control_scripts",
    #     executable="move_robot",
    #     output="screen",
    #     parameters=[kuka_robot_description, robot_description_semantic, kinematics_yaml, {"use_sim_time": True}, {"ENV_PARAM": "gazebo"}],
    # ))
    
    # ld.add_action(kinematics)
    # ld.add_action(rviz_node)
    return actions

def rewrite_yaml(source_file: str, root_key: str):
    if not root_key:
        return source_file

    with open(source_file, 'r') as file:
        ori_data = yaml.safe_load(file)

    updated_yaml = {root_key: ori_data}
    dst_path = f"/tmp/{time.time()}.yaml"
    with open(dst_path, 'w') as file:
        yaml.dump(updated_yaml, file)
    return dst_path

def load_yaml(package_path, file_path):

    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path, "r") as file:
            return yaml.safe_load(file)
    except EnvironmentError:
        return None

# LOAD FILE:
def load_file(package_name, file_path):
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return file.read()
    except EnvironmentError:
        # parent of IOError, OSError *and* WindowsError where available.
        return None

def generate_launch_description():
    
    return LaunchDescription(ARGUMENTS + [
        OpaqueFunction(function=launch_setup)
    ])
