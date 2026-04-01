ARG ROS_DISTRO=jazzy
# GPU = "nvidia" or "amd"
ARG GPU=amd 
FROM ros:$ROS_DISTRO

RUN echo "Building docker image with ROS_DISTRO=$ROS_DISTRO and GPU=$GPU"

RUN apt-get update -y --fix-missing

# dev conveniences
RUN apt-get install -y vim mc \
                       iputils-ping net-tools iproute2 \
                       curl \
                       gdb gdbserver \
                       clangd

RUN apt-get install -y lsb-release gnupg
RUN apt install -y ros-$ROS_DISTRO-rmw-cyclonedds-cpp

# h264 video output
RUN apt install -y ffmpeg
RUN apt install -y ros-$ROS_DISTRO-ffmpeg-image-transport-msgs
RUN apt install -y libopencv-dev
RUN apt install -y libavdevice-dev
RUN apt install -y \
    libdrm-dev \
    libgbm-dev \
    libegl-dev \
    libgles2-mesa-dev \
    libva-dev \
    libva-drm2 \
    libavcodec-dev \
    libavutil-dev \
    mesa-va-drivers

RUN if [ "$GPU" = "nvidia" ]; then \
        echo "Installing Nvidia GPU extras"; \
        RUN apt install -y libnvidia-encode-535; \
    elif [ "$GPU" = "amd" ]; then \
        echo "Installing AMD GPU extras"; \
        cd ~; \
        curl https://repo.radeon.com/amdgpu-install/6.4.1/ubuntu/noble/amdgpu-install_6.4.60401-1_all.deb --output ~/amdgpu-install_6.4.60401-1_all.deb; \
        apt ~/amdgpu-install_6.4.60401-1_all.deb; \
        amdgpu-install --usecase=workstation --vulkan=pro -y; \
        apt install -y vainfo \
    else \
        echo "No valid GPU specified"; \
    fi

# GZ Harmonic (goes with Jazzy)
RUN curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
RUN curl http://packages.osrfoundation.org/gazebo.key --output - | apt-key add -
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
RUN echo "deb http://packages.osrfoundation.org/gazebo/ubuntu-stable `lsb_release -cs` main" > /etc/apt/sources.list.d/gazebo-stable.list
RUN apt-get update

# Gazebo package source build deps
RUN apt install -y python3-pip python3-venv
RUN python3 -m venv /root/vcs_colcon_installation
RUN . /root/vcs_colcon_installation/bin/activate && \
    pip install vcstool colcon-common-extensions jinja2 typeguard

RUN apt-get install -y ros-$ROS_DISTRO-ros-gz \
    ros-$ROS_DISTRO-gz-ros2-control \
    ros-$ROS_DISTRO-ros2-control \
    ros-$ROS_DISTRO-ros2-controllers \
    ros-$ROS_DISTRO-controller-manager

# init ROS workspace before GZ (using collection-harmonic-custom.yaml)
ENV ROS_WS=/ros2_ws
RUN mkdir -p $ROS_WS/src
WORKDIR $ROS_WS
COPY ./ $ROS_WS/src/phntm_gazebo

WORKDIR $ROS_WS

# clone and install Phntm Interfaces
RUN git clone https://github.com/PhantomCybernetics/phntm_interfaces.git /ros2_ws/src/phntm_interfaces
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    rosdep update --rosdistro $ROS_DISTRO && \
    rosdep install -i --from-path src/phntm_interfaces --rosdistro $ROS_DISTRO -y && \
    colcon build --symlink-install --packages-select phntm_interfaces

# build the sim
WORKDIR $ROS_WS
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    . /ros2_ws/install/setup.sh && \
    rosdep install -i --from-path src/phntm_gazebo --rosdistro $ROS_DISTRO -y && \
    colcon build --symlink-install --packages-select phntm_gazebo

ENV GZ_WS=/gz_ws
RUN mkdir -p $GZ_WS/src

RUN git clone https://github.com/PhantomCybernetics/gz-sensors -b gz-sensors8 $GZ_WS/src/gz-sensors
RUN git clone https://github.com/PhantomCybernetics/gz-rendering -b gz-rendering8 $GZ_WS/src/gz-rendering

RUN apt-get install -y libgz-rendering8-ogre2-dev

WORKDIR $GZ_WS
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    colcon build --symlink-install --packages-select gz-rendering8

# make rendering8 from src preferred
ENV CMAKE_PREFIX_PATH=/gz_ws/install/gz-rendering8
ENV GZ_SIM_RESOURCE_PATH=/gz_ws/install/gz-rendering8/share/:/gz_ws/install/gz-sensors8/share/

# ... then finish sensors
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    . /ros2_ws/install/setup.sh && \
    . /gz_ws/install/setup.sh && \
    colcon build --symlink-install --packages-select gz-sensors8

RUN if [ "$GPU" = "nvidia" ]; then \
        echo "NVIDIA_VISIBLE_DEVICES=all" >> /root/.bashrc; \
        echo "NVIDIA_DRIVER_CAPABILITIES=all" >> /root/.bashrc; \
        echo "__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json" >> /root/.bashrc; \
    elif [ "$GPU" = "amd" ]; then \
        echo "__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json" >> /root/.bashrc; \
    fi

# generate entrypoint script
RUN echo '#!/bin/bash \n \
set -e \n \
\n \
# setup ros environment \n \
source "/opt/ros/'$ROS_DISTRO'/setup.bash" \n \
test -f "/ros2_ws/install/setup.bash" && source "/ros2_ws/install/setup.bash" \n \
test -f "/gz_ws/install/setup.bash" && source "/gz_ws/install/setup.bash" \n \ 
\n \
exec "$@"' > /ros_entrypoint.sh
RUN chmod a+x /ros_entrypoint.sh

# source underlay on every login
RUN echo 'source /opt/ros/'$ROS_DISTRO'/setup.bash' >> /root/.bashrc
RUN echo 'test -f "/ros2_ws/install/setup.bash" && source "/ros2_ws/install/setup.bash"' >> /root/.bashrc
RUN echo 'test -f "/gz_ws/install/setup.bash" && source "/gz_ws/install/setup.bash"' >> /root/.bashrc

!TODO!
# Kuka 
apt install -y ros-jazzy-moveit \
               ros-jazzy-moveit-ros-planning-interface
mv move_group_interface_improved.h /opt/ros/jazzy/include/moveit_ros_planning_interface/moveit/move_group_interface/
cd ~
clone kuka package to ~
symlink projects
cd /ros2_ws
rosdep install -i --from-path src/ --rosdistro $ROS_DISTRO -y
colcon build --symlink-install


# set startup path
WORKDIR $ROS_WS

# pimp up prompt with hostame and color
RUN echo "PS1='\${debian_chroot:+(\$debian_chroot)}\\[\\033[01;35m\\]\\u@\\h\\[\\033[00m\\] \\[\\033[01;34m\\]\\w\\[\\033[00m\\] '"  >> /root/.bashrc

ENTRYPOINT [ "/ros_entrypoint.sh" ]
CMD [ "bash" ]