#!/usr/bin/env python3

import rclpy
import asyncio
from rclpy.node import Node
from tf2_msgs.msg import TFMessage

class TFRepublisher(Node):
    def __init__(self):
        super().__init__('tf_republisher_async')

        # === CONFIGURATION ===
        self.republish_rate_hz = 50  # Set desired republish rate here
        # ======================

        self.input_topic = '/mecanum_controller/tf_odometry'
        self.output_topic = '/tf'
        self.latest_msg = None
        self.shutting_down = False
        self.republish_interval = 1.0 / self.republish_rate_hz

        # Create the publisher with VOLATILE durability
        qos = rclpy.qos.QoSProfile(
            depth=10,
            reliability=rclpy.qos.QoSReliabilityPolicy.RELIABLE,
            durability=rclpy.qos.QoSDurabilityPolicy.VOLATILE
        )
        self.publisher = self.create_publisher(TFMessage, self.output_topic, qos)

        # Subscriber inherits QoS from publisher
        self.create_subscription(
            TFMessage,
            self.input_topic,
            self.callback,
            qos
        )

    def callback(self, msg):
        self.latest_msg = msg

    async def main_loop(self):
        try:
            while not self.shutting_down:
                rclpy.spin_once(self, timeout_sec=0.1)
                if self.latest_msg:
                    self.publisher.publish(self.latest_msg)
                    self.latest_msg = None
                await asyncio.sleep(self.republish_interval)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

    async def shutdown_cleanup(self):
        self.shutting_down = True
        await asyncio.sleep(0.1)
        self.destroy_node()

async def main_async():
    rclpy.init()
    node = TFRepublisher()
    try:
        await node.main_loop()
    finally:
        await node.shutdown_cleanup()
        rclpy.shutdown()

def main():
    asyncio.run(main_async())

if __name__ == '__main__':
    main()
