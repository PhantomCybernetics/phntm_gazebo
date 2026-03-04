# Phantom Gazebo

Headless Gazebo sim with GPU rendering used as a demo but also for internal development & testing purposes.

This simulation utilizes Gazebo Harmonic and ROS2 Jazzy, combined with forked version of [gz-sensors8](https://github.com/PhantomCybernetics/gz-sensors) and [gz-rendering8](https://github.com/PhantomCybernetics/gz-rendering), which introduce Direct ROS2 node for low-latency publishing (skipping Gazebo message typings and gz-ros-bridge entirely). The used CameraSensor either generates raw camera frames into a ROS2 Image topic or encodes frames into H.264 (via libavcodec) and produces them as ffmpeg_image_transport_msgs::msg::FFMPEGPacket messages.

### Clone this repo and build the Docker image
```bash
cd ~
git clone git@github.com:PhantomCybernetics/phntm_gazebo.git phntm_gazebo
cd phntm_gazebo
# GPU options: amd, nvidia or not set for sw encoding (not recommended)
GPU=amd; docker build -f Dockerfile -t phntm/gazebo:harmonic-jazzy-$GPU --build-arg GPU=$GPU .
```

This builds Gazebo Harmonic with our forked gz-sensors8 & gz-rendering8 packages.

### Install Phantom Bridge Client

Follow the instructions [here](https://github.com/PhantomCybernetics/phntm_bridge_client?tab=readme-ov-file#phantom-bridge-client)

### Link compose.yaml
```bash
ln -s ~/phntm_gazebo/config/compose_demo.yaml ~/compose.yaml
```

### Generate DEMO phntm_bridge.yaml
All demos are made identical with only a few changes. `config/phntm_bridge.templ.yaml` is used as a template.
Register a new machine using `http://register.phntm.yaml/robot`, then use obtained ID/KEY values in a YAML file like this:
```yaml
dwight:
    id_robot: ID_FROM_REGISTRATION
    robot_key: KEY_FROM_REGISTRATION
    name: 'Simbot Dwight (Germany)'
    bridge_server_address: https://eu-ch.bridge.phntm.io
    location: 'Frankfurt, Germany'
    demo_url: https://phntm.io/demo-dwight
```
Save it as say `conf/demo_some_name.yaml`, then run `config/generate_demo_config.py demo_some_name.yaml`. This will generate `config/phntm_bridge.yaml` referenced by `config/compose.yaml`.

### Launch
```bash
docker compose up
```

You can observe logs using `docker logs` like so:

```bash
docker logs -t -f phntm-bridge
docker logs -t -f phntm-gazebo
```


### Argument examples 
`encoder_hw_device:=cuda` - hardware device for the H.264 video encoding (`cuda` - default, `vaapi` or `sw`) \
`cameras_pixel_format:=BGR_INT8` - internal format generated bu the Gazebo/Ogre2 cameras (`RGB_INT8` default) \
`cameras_resolution:=1280x720` - resolutions for all cameras \
`encoder_input_pixel_format:=bgr0` - input pixel format for the H.264 video encoder (autodetected and defaults to `nv12` if not set) 

The rendering cameras generate a raw RGB (or BGR) frames that need to be wrapped in an OpenCV Mat and if necessary, transformed to match the supported input pixel format of the encoder. This scaling operation is performed on CPU (on a dedicated thread) and could be expensive. Some formats (such as `yuv420` or `nv12`) require this scaling. If supported by the encoder, it is recommended to use `bgr0` or similar to skip this scaling step. A Vaapi device may only support vaapi input. Supported input pixel formats are printed when AVCodec is instanced.

## Hardware Notes

### AWS g4ad.xlarge insance (AMD Radeon Pro V520 GPU)
This is the recommended option as AMD GPU instances are more cost-effective than instances with Nvidia GPUs. 

Install drivers (in the host machine, not Docker container):
```bash
sudo apt-get update --fix-missing
sudo apt install build-essential linux-firmware linux-modules-extra-aws -y
wget https://repo.radeon.com/amdgpu-install/6.4.2/ubuntu/jammy/amdgpu-install_6.4.60402-1_all.deb
sudo apt install ./amdgpu-install_6.4.60402-1_all.deb
sudo amdgpu-install -y --usecase=graphics,rocm
sudo usermod -a -G render,video $LOGNAME
sudo reboot
```

### AWS g4dn.xlarge insance (NVIDIA T4 GPU)
Hw rendering and frame encoding utilizes the GPU at about 20% with 3 cameras @ 1290x720

### Jetson Orin Nano
Frame encoding is done on the CPU as the GPU has no video encoding capabilities

## Known Issues
- Gazebo often leaves behind zombie processes, kill them with `pkill -9 -f "gz sim"`
- Gazebo sometimes crashes with `ODE INTERNAL ERROR 1: assertion "aabbBound >= dMinIntExact && aabbBound < dMaxIntExact" failed in collide() [collision_space.cpp:460]`. This is an error of the physics engine. It happens when an object runs away of falls through the ground, causing an integer overflow
- The hardware H.264 encoder requires NV12 frames as the input. The Ogre2 engine produces rgb8 textures and offers an OpenGL texture handle. This means a transformation needs to take place before we can feed the input frames to the encoder. It is theoretically possible to do this completely on the GPU with zero-copy to RAM, minimal CPU involvement and very low latency, however, this has proven to be very challenging and more work is needed, [see details here](https://www.reddit.com/r/GraphicsProgramming/comments/1mn0gpn/zerocopy_h264_video_encoding_from_opengl_texture/). At the moment, every frame if copied to RAM and transformed on the CPU, which means we're losing about 3-5 FPS per active camera (all cameras in Gazebo run on the same rendering thread).
- The Range sensors are implemented as GPU lidars with limited FOV, then converted to sensor_msgs/msg/Range by the laser_to_range_converter. This is not ideal but fine for now.
- Only sensors present in our demos are tested, some features (such as saving static images from a camera) may not work