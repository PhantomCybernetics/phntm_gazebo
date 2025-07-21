#!/usr/bin/env python3

import rclpy
import math
import asyncio
from rclpy.node import Node
from sensor_msgs.msg import LaserScan, Range
from functools import partial

class LaserToRangeConverter(Node):
    def __init__(self):
        super().__init__('laser_to_range_converter')

        self.declare_parameter('scan_topics', '/scan')
        self.declare_parameter('fov_deg', 10.0)
        self.declare_parameter('target_angle_rad', 0.0)
        self.declare_parameter('publish_rate_hz', 10.0)

        self.scan_topics = self.get_parameter('scan_topics').get_parameter_value().string_value
        self.scan_topic_list = self.scan_topics.split(',')
        self.fov_rad = math.radians(self.get_parameter('fov_deg').get_parameter_value().double_value)
        self.target_angle = self.get_parameter('target_angle_rad').get_parameter_value().double_value
        self.publish_interval = 1.0 / self.get_parameter('publish_rate_hz').get_parameter_value().double_value
        self.scan_to_range_dict = {topic: topic + '_ranged' for topic in self.scan_topic_list}

        print("Range publish interval is " + str(self.publish_interval))
        
        self.latest_scans = {topic: None for topic in self.scan_topic_list}
        self.shutting_down = False
        
        self.range_publishers = {}
        for topic in self.scan_topic_list:
            self.range_publishers[topic] = self.create_publisher(Range, self.scan_to_range_dict[topic], 1)
            self.create_subscription(
                LaserScan,
                topic,
                partial(self.scan_callback, topic_name=topic),
                1
            )

    def scan_callback(self, msg: LaserScan, topic_name: str):
        if topic_name not in self.scan_topic_list:
            self.get_logger().warn(f"Received message on unexpected topic: {topic_name}")
            return
        self.latest_scans[topic_name] = msg


    def convert_scan_to_range(self):
        for topic, msg in self.latest_scans.items():
            if msg is None:
                continue
            angle_min = msg.angle_min
            angle_inc = msg.angle_increment
            total_beams = len(msg.ranges)
            
            center_index = int(round((self.target_angle - angle_min) / angle_inc))
            half_width = int(round((self.fov_rad / 2) / angle_inc))
            
            start = max(center_index - half_width, 0)
            end = min(center_index + half_width + 1, total_beams)
            
            avg_range = 0.0
            valid_ranges = [r for r in msg.ranges[start:end] if msg.range_min <= r <= msg.range_max]
            if valid_ranges:
                avg_range = sum(valid_ranges) / len(valid_ranges)
            
            range_msg = Range()
            range_msg.header = msg.header
            range_msg.radiation_type = Range.ULTRASOUND
            range_msg.field_of_view = self.fov_rad
            range_msg.min_range = msg.range_min
            range_msg.max_range = msg.range_max
            range_msg.range = avg_range
            self.range_publishers[topic].publish(range_msg)
        self.latest_scans = {topic: None for topic in self.scan_topic_list}
    

    async def main_loop(self):
        try:
            while not self.shutting_down:
                for i in range(len(self.scan_topic_list)):
                    rclpy.spin_once(self, timeout_sec=0.01)
                self.convert_scan_to_range()
                await asyncio.sleep(self.publish_interval)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

    async def shutdown_cleanup(self):
        self.shutting_down = True
        for topic in self.scan_topic_list:
            if topic in self.range_publishers:
                self.range_publishers[topic].destroy()
        self.range_publishers.clear()
        await asyncio.sleep(0.1)


async def main_async():
    node = LaserToRangeConverter()
    task = asyncio.create_task(node.main_loop())
    try:
        await task
    finally:
        await node.shutdown_cleanup()
        node.destroy_node()

def main():
    rclpy.init()
    asyncio.run(main_async())
    rclpy.shutdown()

if __name__ == '__main__':
    main()

