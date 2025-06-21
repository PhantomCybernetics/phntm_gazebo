#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from ros2_omni_robot_sim.srv import SetFloat64, GetFloat64
import threading
from sensor_msgs.msg import JointState

class CameraJointService(Node):
    def __init__(self):
        super().__init__('camera_joint_service')
        self.publisher = self.create_publisher(Float64MultiArray, '/camera_joint_top_position_controller/commands', 10)
        self.srv = self.create_service(SetFloat64, 'set_top_camera_distance', self.callback)
        self.get_srv = self.create_service(GetFloat64, 'get_top_camera_distance', self.get_callback)
        self.joint_position = 0.0
        self.joint_name = 'camera_joint_top'
        self.joint_state_lock = threading.Lock()
        self.create_subscription(JointState, '/joint_states', self.joint_state_callback, 10)
        self.get_logger().info('Camera joint service ready.')

    def joint_state_callback(self, msg):
        if self.joint_name in msg.name:
            idx = msg.name.index(self.joint_name)
            with self.joint_state_lock:
                self.joint_position = msg.position[idx]

    def callback(self, request, response):
        value = request.data
        msg = Float64MultiArray()
        msg.data = [value]
        self.publisher.publish(msg)
        response.success = True
        response.message = 'done'
        self.get_logger().info(f'Set camera joint to {value}')
        return response

    def get_callback(self, request, response):
        # request is empty for GetFloat64.srv now
        with self.joint_state_lock:
            response.data = self.joint_position
        self.get_logger().info(f'Returning camera joint position: {response.data}')
        return response

def main(args=None):
    rclpy.init(args=args)
    node = CameraJointService()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

