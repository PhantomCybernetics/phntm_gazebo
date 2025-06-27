ARG ROS_DISTRO=jazzy
FROM ros:$ROS_DISTRO

RUN echo "Building docker image with ROS_DISTRO=$ROS_DISTRO"

RUN apt-get update -y --fix-missing

# dev conveniences
RUN apt-get install -y vim mc \
                       iputils-ping net-tools iproute2 \
                       curl

RUN apt-get install -y lsb-release gnupg

# GZ Harmonic (goes with Jazzy)
RUN curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
RUN apt-get update
RUN apt-get install -y gz-harmonic

RUN apt-get install -y ros-$ROS_DISTRO-ros-gz \
    ros-$ROS_DISTRO-gz-ros2-control \
    ros-$ROS_DISTRO-ros2-control \
    ros-$ROS_DISTRO-ros2-controllers \
    ros-$ROS_DISTRO-navigation2 \
    ros-$ROS_DISTRO-controller-manager
    # ros-$ROS_DISTRO-nav2-bringup \
    # ros-$ROS_DISTRO-slam-toolbox

# RUN apt-get install -y \
#     libgz-common6-dev \
#     libgz-plugin3-dev \
#     libgz-rendering9-dev

# init workspace
ENV ROS_WS=/ros2_ws
RUN mkdir -p $ROS_WS/src
WORKDIR $ROS_WS

# clone and install Phntm Interfaces
RUN git clone https://github.com/PhantomCybernetics/phntm_interfaces.git /ros2_ws/src/phntm_interfaces
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    rosdep update --rosdistro $ROS_DISTRO && \
    rosdep install -i --from-path src/phntm_interfaces --rosdistro $ROS_DISTRO -y && \
    colcon build --symlink-install --packages-select phntm_interfaces

#optix deps
# RUN apt install -y g++ freeglut3-dev build-essential libx11-dev libxmu-dev libxi-dev libglu1-mesa-dev libfreeimage-dev libglfw3-dev
# RUN apt install wget -y
# WORKDIR /root/
# RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
# RUN dpkg -i cuda-keyring_1.1-1_all.deb
# RUN apt-get update
# RUN apt install -y cuda-toolkit-12-9
# RUN apt install -y cuda-drivers
# WORKDIR $ROS_WS

# h264 video output
RUN apt install -y ffmpeg
RUN apt install -y libnvidia-encode-535

# build the sim
COPY ./ $ROS_WS/src/simbot_gz
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    . /ros2_ws/install/setup.sh && \
    rosdep install -i --from-path src/simbot_gz --rosdistro $ROS_DISTRO -y && \
    colcon build --symlink-install --packages-select simbot_gz

# generate entrypoint script
RUN echo '#!/bin/bash \n \
set -e \n \
\n \
# setup ros environment \n \
source "/opt/ros/'$ROS_DISTRO'/setup.bash" \n \
test -f "/ros2_ws/install/setup.bash" && source "/ros2_ws/install/setup.bash" \n \
\n \
exec "$@"' > /ros_entrypoint.sh
RUN chmod a+x /ros_entrypoint.sh

# source underlay on every login
RUN echo 'source /opt/ros/'$ROS_DISTRO'/setup.bash' >> /root/.bashrc
RUN echo 'test -f "/ros2_ws/install/setup.bash" && source "/ros2_ws/install/setup.bash"' >> /root/.bashrc

# set startup path
WORKDIR $ROS_WS

# pimp up prompt with hostame and color
RUN echo "PS1='\${debian_chroot:+(\$debian_chroot)}\\[\\033[01;35m\\]\\u@\\h\\[\\033[00m\\] \\[\\033[01;34m\\]\\w\\[\\033[00m\\] '"  >> /root/.bashrc

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD [ "bash" ]