#!/usr/bin/env python3

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from custom_action_interfaces.action import Fibonacci

from control_msgs.action import FollowJointTrajectory

class KukaArmServices(Node):

    def __init__(self):
        super().__init__('kuka_arm_services')
        self._action_client = ActionClient(self, FollowJointTrajectory, '/kuka/kuka_arm_controller/follow_joint_trajectory')

    def send_goal(self, xyz):
        goal_msg = FollowJointTrajectory.Goal()
        # goal_msg.order = order

        self._action_client.wait_for_server()

        return self._action_client.send_goal_async(goal_msg)


def main(args=None):
    try:
        with rclpy.init(args=args):

            kuka_services = KukaArmServices()

            future = kuka_services.send_goal(10)

            rclpy.spin_until_future_complete(action_client, future)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()