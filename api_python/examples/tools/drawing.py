#! /usr/bin/env python3

###
# KINOVA (R) KORTEX (TM)
#
# Copyright (c) 2018 Kinova inc. All rights reserved.
#
# This software may be modified and distributed
# under the terms of the BSD 3-Clause license.
#
# Refer to the LICENSE file for details.
#
###

import sys
import os
import time
import threading

from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient

from kortex_api.autogen.messages import Base_pb2, BaseCyclic_pb2, Common_pb2

# Maximum allowed waiting time during actions (in seconds)
TIMEOUT_DURATION = 20

# Create closure to set an event after an END or an ABORT 
# 这个函数返回一个闭包，用于检查动作是否结束（END）或中止（ABORT），并在检测到这些事件时设置一个线程事件e
def check_for_end_or_abort(e):
    """Return a closure checking for END or ABORT notifications

    Arguments:
    e -- event to signal when the action is completed
        (will be set when an END or ABORT occurs)
    """
    def check(notification, e = e):
        print("EVENT : " + \
              Base_pb2.ActionEvent.Name(notification.action_event))
        if notification.action_event == Base_pb2.ACTION_END \
        or notification.action_event == Base_pb2.ACTION_ABORT:
            e.set()
    return check
 
def example_move_to_home_position(base):
    # Make sure the arm is in Single Level Servoing mode
    base_servo_mode = Base_pb2.ServoingModeInformation()
    base_servo_mode.servoing_mode = Base_pb2.SINGLE_LEVEL_SERVOING
    base.SetServoingMode(base_servo_mode)
    
    # Move arm to ready position
    print("Moving the arm to a safe position")
    action_type = Base_pb2.RequestedActionType()
    action_type.action_type = Base_pb2.REACH_JOINT_ANGLES
    action_list = base.ReadAllActions(action_type)
    action_handle = None
    for action in action_list.action_list:
        if action.name == "Home":
            action_handle = action.handle

    if action_handle == None:
        print("Can't reach safe position. Exiting")
        return False

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(
        check_for_end_or_abort(e),
        Base_pb2.NotificationOptions()
    )

    base.ExecuteActionFromReference(action_handle)
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)

    if finished:
        print("Safe position reached")
    else:
        print("Timeout on action notification wait")
    return finished


def example_cartesian_action_movement(base, base_cyclic, pose_x, pose_y, pose_z):
    '''
    Arg:
    base: an instance of BaseClient 基础客户端
    base_cyclic: an instance of BaseCyclicClient 循环基础客户端
    '''
    
    print("Starting Cartesian action movement ...")
    action = Base_pb2.Action()
    action.name = "Example Cartesian action movement"
    action.application_data = "" 

    feedback = base_cyclic.RefreshFeedback() # 从base_cyclic客户端获取当前的反馈信息

    cartesian_pose = action.reach_pose.target_pose
    cartesian_pose.x = pose_x          # (meters)
    cartesian_pose.y = pose_y   # (meters)
    cartesian_pose.z = pose_z    # (meters)
    cartesian_pose.theta_x = feedback.base.tool_pose_theta_x # (degrees)夹爪角度：+往下；-往上
    cartesian_pose.theta_y = feedback.base.tool_pose_theta_y # (degrees)夹爪角度：+逆时针；-顺时针
    cartesian_pose.theta_z = feedback.base.tool_pose_theta_z # (degrees)夹爪角度：+左转；-右转

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(
        check_for_end_or_abort(e),
        Base_pb2.NotificationOptions()
    )

    print("Executing action")
    base.ExecuteAction(action)

    print("Waiting for movement to finish ...")
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)

    if finished:
        print("Cartesian movement completed")
    else:
        print("Timeout on action notification wait")
    return finished

def main():
    
    # Import the utilities helper module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import utilities

    # Parse arguments
    args = utilities.parseConnectionArguments()
    
    # Create connection to the device and get the router
    with utilities.DeviceConnection.createTcpConnection(args) as router:

        # Create required services
        base = BaseClient(router)
        base_cyclic = BaseCyclicClient(router)

        # Example core
        success = True

        feedback = base_cyclic.RefreshFeedback() # 从base_cyclic客户端获取当前的反馈信息
        success &= example_move_to_home_position(base)

        feedback = base_cyclic.RefreshFeedback()
        # 绘图初始点
        drawing_default_pose = (feedback.base.tool_pose_x + 0.2, feedback.base.tool_pose_y + 0.1, feedback.base.tool_pose_z - 0.37)
        success &= example_cartesian_action_movement(base, base_cyclic, drawing_default_pose[0], drawing_default_pose[1], drawing_default_pose[2])
        # 定义矩形的四个顶点
        feedback = base_cyclic.RefreshFeedback()
        points = [
            (feedback.base.tool_pose_x + 0.05, feedback.base.tool_pose_y),
            (feedback.base.tool_pose_x + 0.05, feedback.base.tool_pose_y + 0.05),
            (feedback.base.tool_pose_x - 0.05, feedback.base.tool_pose_y + 0.05),
            (feedback.base.tool_pose_x - 0.05, feedback.base.tool_pose_y - 0.05) # 回到起点以完成矩形
        ]

        pose_z = feedback.base.tool_pose_z # 矩形高度
        for pose_x, pose_y in points:   # 画四个点
            print(pose_x, pose_y, pose_z)
            success &= example_cartesian_action_movement(base, base_cyclic, pose_x, pose_y, pose_z)

        return 0 if success else 1

if __name__ == "__main__":
    exit(main())

