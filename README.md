# Gazebo Simbot

Headless Gazebo sim with GPU rendering used as a demo but also for internal development & testing purposes.

### Clone this repo and build the Docker image
```bash
cd ~
git clone git@github.com:PhantomCybernetics/simbot_gz.git simbot_gz
cd simbot_gz
docker build -f Dockerfile -t phntm/simbot-gz:harmonic-jazzy .
```

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
            # ROS_DOMAIN_ID: 0
            # OGRE_RTSYS: EGL
            # __EGL_VENDOR_LIBRARY_FILENAMES: /usr/share/glvnd/egl_vendor.d/10_nvidia.json
            # XDG_RUNTIME_DIR: /tmp/xdg          # silences Wayland helper
        volumes:
            - /dev/shm:/dev/shm
            - ~/simbot_gz:/ros2_ws/src/simbot_gz
        group_add:
            - video
        network_mode: host
        # ipc: host  # Bridge needs this to see other local containers
        shm_size: '200mb'
        # stdin_open: true
        # tty: true
        command:
            /bin/sh -c "while sleep 1000; do :; done"
```

### Launch
```bash
docker compose up simbot-gz
```