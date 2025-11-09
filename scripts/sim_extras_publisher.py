#!/usr/bin/env python3

import rclpy
import math
import random
import asyncio
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from sensor_msgs.msg import BatteryState
from nav_msgs.msg import Odometry
from phntm_interfaces.msg import IWStatus
from rclpy.qos import QoSProfile, ReliabilityPolicy
# from tf2_msgs.msg import TFMessage
# from geometry_msgs.msg import TransformStamped, Transform
# from simbot_gz.srv import GetFloat32, SetFloat32
# import time

# NOTE:
# Move a scene obj like this:
# gz service -s /world/demo_world/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --req "name: 'slope_0', position: { x: 3, y: -4, z: 0 }, orientation: { x: 0.0, y: 0.0, z: 0.0, w: 1.0 }"

class SimExtrasPublisher(Node):
    
    def __init__(self):
        node_name = 'sim_extras_publisher'
        
        super().__init__(node_name)

        self.declare_parameter('refresh_period_sec', 5.0)
        self.declare_parameter('ui_battery_topic', '/ui/battery')
        self.declare_parameter('ui_wifi_topic', '/iw_status')
        self.declare_parameter('wifi_quality_max', 1.0)
        self.declare_parameter('wifi_quality_min', 0.1)
        self.declare_parameter('wifi_max_distance', 10.0)
        self.declare_parameter('nominal_voltage', 22.2)
        self.declare_parameter('min_voltage', 19.2)
        self.declare_parameter('max_voltage', 25.2)
        self.declare_parameter('max_linear_speed', 10.0)
        self.declare_parameter('max_angular_speed', 10.0)
        self.declare_parameter('voltage_drop_range', 1.0)
        # self.declare_parameter('camera_top_z', 0.0)
        # self.declare_parameter('tf_topic', '/tf')
        # self.declare_parameter('top_camera_parent_frame_id', 'base_link')
        # self.declare_parameter('top_camera_frame_id', 'camera_joint_top')
        
        self.battery_topic = self.get_parameter('ui_battery_topic').get_parameter_value().string_value
        self.wifi_topic = self.get_parameter('ui_wifi_topic').get_parameter_value().string_value
        self.wifi_quality_max = self.get_parameter('wifi_quality_max').get_parameter_value().double_value
        self.wifi_quality_min = self.get_parameter('wifi_quality_min').get_parameter_value().double_value
        self.wifi_max_distance = self.get_parameter('wifi_max_distance').get_parameter_value().double_value
        self.nominal_voltage = self.get_parameter('nominal_voltage').get_parameter_value().double_value
        self.min_voltage = self.get_parameter('min_voltage').get_parameter_value().double_value
        self.max_voltage = self.get_parameter('max_voltage').get_parameter_value().double_value
        self.max_linear_speed = self.get_parameter('max_linear_speed').get_parameter_value().double_value
        self.max_angular_speed = self.get_parameter('max_angular_speed').get_parameter_value().double_value
        self.drop_range = self.get_parameter('voltage_drop_range').get_parameter_value().double_value

        self.battery_pub = self.create_publisher(BatteryState, self.battery_topic, 10)
        self.wifi_pub = self.create_publisher(IWStatus, self.wifi_topic, 10)

        self.last_cmd_vel = None
        self.last_position = None
        self.shutting_down = False
        self.battery_task = None
        self.wifi_task = None

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=1
        )
        self.create_subscription(TwistStamped, '/cmd_vel', self.cmd_vel_callback, qos)
        self.create_subscription(Odometry, '/odom', self.odom_callback, qos)
        
        # self.top_camera_z_position = self.get_parameter('camera_top_z').get_parameter_value().double_value
        # self.tf_topic = self.get_parameter('tf_topic').get_parameter_value().string_value
        # self.top_camera_parent_frame_id = self.get_parameter('top_camera_parent_frame_id').get_parameter_value().string_value
        # self.top_camera_frame_id = self.get_parameter('top_camera_frame_id').get_parameter_value().string_value
        # print(f'Initial top Camera Z set to {self.top_camera_z_position}', flush=True)
        # self.set_top_camera_z_srv = self.create_service(SetFloat32, f'/{node_name}/set_top_camera_z', self.set_top_camera_z_callback)
        # self.get_top_camera_z_srv = self.create_service(GetFloat32, f'/{node_name}/get_top_camera_z', self.get_top_camera_z_callback)
        # self.tf_pub = self.create_publisher(TFMessage, self.tf_topic, 1)

        
    # def set_top_camera_z_callback(self, request:SetFloat32.Request, response:SetFloat32.Response):
    #     self.top_camera_z_position = request.data
    #     print(f'Top Camera Z set to {self.top_camera_z_position}', flush=True)

    #     time_nanosec:int = time.time_ns()
    #     msg = TFMessage()
    #     ts = TransformStamped()
    #     ts.header.stamp.sec = math.floor(time_nanosec / 1000000000)
    #     ts.header.stamp.nanosec = time_nanosec % 1000000000
    #     ts.header.frame_id = self.top_camera_parent_frame_id
    #     ts.child_frame_id = self.top_camera_frame_id
    #     ts.transform = Transform()
    #     ts.transform.translation.z = self.top_camera_z_position
    #     msg.transforms = []
    #     msg.transforms.append(ts)
        
    #     self.tf_pub.publish(msg)
        
    #     response.success = True
    #     return response        
        
    # def get_top_camera_z_callback(self, request:GetFloat32.Request, response:GetFloat32.Response):
    #     response.data = self.top_camera_z_position
    #     return response

    def cmd_vel_callback(self, msg):
        self.last_cmd_vel = msg


    def odom_callback(self, msg):
        self.last_position = msg.pose.pose.position


    def publish_battery_status(self):
        msg = self.last_cmd_vel or TwistStamped()
        linear = math.sqrt(msg.twist.linear.x**2 + msg.twist.linear.y**2 + msg.twist.linear.z**2)
        angular = math.sqrt(msg.twist.angular.x**2 + msg.twist.angular.y**2 + msg.twist.angular.z**2)

        load_factor = 0.5 * ((linear / self.max_linear_speed) + (angular / self.max_angular_speed))
        voltage_drop = load_factor * self.drop_range
        voltage = self.nominal_voltage - voltage_drop + random.uniform(-0.1, 0.1)
        voltage = max(self.min_voltage, min(self.max_voltage, voltage))

        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.voltage = voltage
        msg.design_capacity = self.max_voltage
        msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        msg.present = True

        voltage_range = self.max_voltage - self.min_voltage
        msg.percentage = (voltage - self.min_voltage) / voltage_range if voltage_range > 0 else 1.0
        msg.percentage = max(0.0, min(1.0, msg.percentage))

        self.battery_pub.publish(msg)


    def publish_wifi_status(self):
        pos = self.last_position
        if pos is None:
            return

        distance = math.sqrt(pos.x**2 + pos.y**2 + pos.z**2)
        quality = self.wifi_quality_min if distance >= self.wifi_max_distance else self.wifi_quality_max - (distance / self.wifi_max_distance) * (self.wifi_quality_max - self.wifi_quality_min)
        quality = max(0.0, min(1.0, quality))

        msg = IWStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.frequency = 5.5221
        msg.access_point = "C0:94:35:CD:00:1B"
        msg.bit_rate = 1.2
        msg.essid = "GAZEBO-SIM-AP"
        msg.mode = 1
        msg.quality = int(quality * 100)
        msg.quality_max = 100
        msg.level = 200
        msg.noise = 0
        msg.supports_scanning = False

        self.wifi_pub.publish(msg)


    async def main_loop(self):
        try:
            while not self.shutting_down:
                rclpy.spin_once(self, timeout_sec=0.1)

                if not self.battery_task or self.battery_task.done():
                    self.battery_task = asyncio.get_event_loop().run_in_executor(None, self.publish_battery_status)

                if not self.wifi_task or self.wifi_task.done():
                    self.wifi_task = asyncio.get_event_loop().run_in_executor(None, self.publish_wifi_status)

                await asyncio.sleep(self.get_parameter('refresh_period_sec').get_parameter_value().double_value)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass


    async def shutdown_cleanup(self):
        self.shutting_down = True
        if self.battery_pub:
            self.battery_pub.destroy()
        if self.wifi_pub:
            self.wifi_pub.destroy()


async def main_async():
    node = SimExtrasPublisher()
    loop_task = asyncio.create_task(node.main_loop())

    try:
        await loop_task
    except asyncio.CancelledError:
        pass
    finally:
        await node.shutdown_cleanup()
        node.destroy_node()


def main(args=None):
    rclpy.init()
    asyncio.run(main_async())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
