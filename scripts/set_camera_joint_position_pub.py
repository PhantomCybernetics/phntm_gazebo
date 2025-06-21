#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
import asyncio

class SetCameraJointPositionPub(Node):
    def __init__(self):
        super().__init__('set_camera_joint_position_pub')
        self.publisher = self.create_publisher(Float64MultiArray, '/camera_joint_top_position_controller/commands', 10)
        self.done = False

    async def main_loop(self):
        try:
            while rclpy.ok() and not self.done:
                rclpy.spin_once(self, timeout_sec=0.1)
                if self.publisher.get_subscription_count() > 0:
                    msg = Float64MultiArray()
                    msg.data = [1.5]
                    self.publisher.publish(msg)
                    self.get_logger().info('Published initial camera joint position: 1.5')
                    self.done = True
                else:
                    self.get_logger().info('Waiting for controller to subscribe to /camera_joint_top_position_controller/commands...')
                await asyncio.sleep(0.5)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

    async def shutdown_cleanup(self):
        self.done = True

async def main_async():
    rclpy.init()
    node = SetCameraJointPositionPub()
    try:
        await node.main_loop()
    finally:
        await node.shutdown_cleanup()
        node.destroy_node()
        rclpy.shutdown()

def main():
    asyncio.run(main_async())

if __name__ == '__main__':
    main()

