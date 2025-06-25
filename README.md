# Gazebo Simbot

Headless Gazebo sim with GPU rendering used as a demo but also for internal development & testing purposes.

### Clone this repo and build the Docker image
```bash
cd ~
git clone git@github.com:PhantomCybernetics/simbot_gz.git simbot_gz
cd simbot_gz
docker build -f Dockerfile -t phntm/simbot-gz:harmonic-jazzy .
```

### Install Phantom Bridge Client
Follow instructions [[here|PhantomCybernetics/phntm_bridge_client?tab=readme-ov-file#phantom-bridge-client]]

In ./config/phntm_bridge_example.yaml you'll find a template for the Sim's Bridge congiguration that uses default inpit config from ./config/phntm_input_config.json. There's also an example of the Agent config in ./config/phntm_agent_example.yaml configured for this sim.

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
      ros2 launch simbot_gz simbot_gz.launch.py

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
      ros2 launch phntm_bridge client_agent_launch.py
```

### Launch
```bash
docker compose up simbot-gz
```