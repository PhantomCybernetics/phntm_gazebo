# Gazebo Simbot

Headless Gazebo sim with GPU rendering used as a demo but also for internal development & testing purposes.
This simulation utilizes Gazebo Harmonic and ROS2 Jazzy, combined with forked version of [gz-sensors8](https://github.com/PhantomCybernetics/gz-sensors), which introsuced Direct ROS2 node for low-latency publishing (skipping Gazebo message typings and gz-ros-bridge entirely). The used CameraSensor either generates raw camera frames into a ROS2 Image topic or encodes frames into H.264 (via libavcodec) and produces them as ffmpeg_image_transport_msgs::msg::FFMPEGPacket messages.

### Clone this repo and build the Docker image
```bash
cd ~
git clone git@github.com:PhantomCybernetics/simbot_gz.git simbot_gz
cd simbot_gz
docker build -f Dockerfile -t phntm/simbot-gz:harmonic-jazzy .
```

This builds Gazebo Harmonic with our forked gz-sensors8 package.

### Install Phantom Bridge Client
Follow instructions [[here|PhantomCybernetics/phntm_bridge_client?tab=readme-ov-file#phantom-bridge-client]]

In `./config/phntm_bridge_example.yaml` you'll find a template for the Sim's Bridge congiguration that uses default inpit config from `./config/phntm_input_config.json`. There's also an example of the Agent config in `./config/phntm_agent_example.yaml` configured for this sim.

### Add service to your compose.yaml
```yaml
services:
    simbot-gz:
    image: phntm/simbot-gz:harmonic-jazzy
    container_name: simbot-gz
    hostname: simbot-gz.local
    # GPU integration
    runtime: nvidia           # compose v2 syntax
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: all   # graphics,compute,video,utility …
      GZ_SIM_RESOURCE_PATH: /usr/share/gz
      GZ_CONFIG_PATH: /usr/share/gz
    volumes:
      - /dev/shm:/dev/shm
      - ~/simbot_gz:/ros2_ws/src/simbot_gz
    group_add:
      - video
    network_mode: host
    # ipc: host  # Bridge needs this to see other local containers
    shm_size: '200mb'
    command:
      ros2 launch simbot_gz simbot_gz.launch.py encoder_hw_device:=cuda camera_top_z:=5.0
      # on g4dn_xlarge launch:
      # ros2 launch simbot_gz simbot_gz.launch.py encoder_hw_device:=cuda cameras_pixel_format:=BGR_INT8 encoder_input_pixel_format:=bgr0
      # on jetson orin nano:
      # ros2 launch simbot_gz simbot_gz.launch.py encoder_hw_device:=sw camera_top_z:=5.0 cameras_pixel_format:=RGB_INT8 encoder_input_pixel_format:=nv12 encoder_thread_count:=3 cameras_resolution:=640x480

  phntm-bridge:
    image: phntm/bridge:jazzy
    container_name: phntm-bridge
    hostname: phntm-bridge.local
    restart: unless-stopped  # Restarts after first run
    privileged: true  # Bridge needs this
    # cpuset: '0,1,2' # Consider dedicating a few CPU cores for maximal responsiveness
    network_mode: host  # WebRTC needs this
    ipc: host  # Bridge needs this to see other local containers
    shm_size: '200mb'
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
    volumes:
      - ~/phntm_bridge.yaml:/ros2_ws/phntm_bridge_params.yaml  # Bridge config goes here
      - ~/phntm_agent.yaml:/ros2_ws/phntm_agent_params.yaml  # Agent config goes here
      - ~/simbot_gz/config/phntm_input_config.json:/ros2_ws/phntm_input_config.json # default input mapping
      - /var/run:/host_run  # Docker file extractor and WiFi control need this
      - /tmp:/tmp  # WiFi control needs this
      - ~/simbot_gz:/ros2_ws/src/simbot_gz # srv defs
    devices:
      - /dev:/dev  # LED control needs this
      - /dev/nvidia0:/dev/nvidia0
      - /dev/nvidiactl:/dev/nvidiactl
      - /dev/nvidia-uvm:/dev/nvidia-uvm
      - /dev/nvidia-uvm-tools:/dev/nvidia-uvm-tools
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

    command:
      ros2 launch simbot_gz simbot_gz.launch.py encoder_hw_device:=cuda camera_top_z:=5.0 cameras_pixel_format:=BGR_INT8 encoder_input_pixel_format:=bgr0
```

### Launch
```bash
docker compose up simbot-gz
```

### Argument examples
`camera_top_z:=5.0` - initial distance of the top-down camera above the robot [m]

`encoder_hw_device:=cuda` - hardware device for the H.264 video encoding (`cuda` - default, `vaapi` or `sw`)
`cameras_pixel_format:=BGR_INT8` - internal format generated bu the Gazebo/Ogre2 cameras (`RGB_INT8` default)
`cameras_resolution:=1280x720` - resolutions for all cameras
`encoder_input_pixel_format:=bgr0` - input pixel format for the H.264 video encoder (autodetected and defaults to `nv12` if not set)

The rendering cameras generate a raw RGB (or BGR) frames that need to be wrapped in an OpenCV Mat and if necessary, transformed to match the supported input pixel format of the encoder. This scaling operation is performed on CPU (on a dedicated thread) and could be expencive. Some formats (such as `yuv420` or `nv12`) require this scaling. If supported by the encoder, it is recommended to use `bgr0` or similar to skip this scaling step.

### Hardware Notes

#### Jetson Orin Nano
Frame encoding is done on CPU as the GPU has no such capabilities

#### AWS g4dn_xlarge insance
Hw rendering and frame encoding utilizes the GPU at abou 20% with 3 cameras @ 1290x720
