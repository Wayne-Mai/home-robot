from typing import Any, Dict, List, Optional

import numpy as np
import rospy
from slap_manipulation.utils.slap_planner import CombinedSLAPPlanner

import home_robot
from home_robot.core.interfaces import (
    Action,
    ContinuousFullBodyAction,
    DiscreteNavigationAction,
    HybridAction,
    Observations,
)
from home_robot.motion.stretch import STRETCH_TO_GRASP
from home_robot.utils.geometry import xyt2sophus, xyt_base_to_global, xyt_global_to_base
from home_robot.utils.pose import to_matrix
from home_robot_hw.env.stretch_pick_and_place_env import DETIC, StretchPickandPlaceEnv
from home_robot_hw.ros.visualizer import ArrayVisualizer, Visualizer


class GeneralLanguageEnv(StretchPickandPlaceEnv):
    def __init__(
        self,
        config,
        goal_options: List[str] = None,
        segmentation_method: str = DETIC,
        visualize_planner: bool = False,
        ros_grasping: bool = True,
        test_grasping: bool = False,
        dry_run: bool = False,
        debug: bool = False,
        *args,
        **kwargs
    ):
        super().__init__(
            config,
            goal_options,
            segmentation_method,
            visualize_planner,
            ros_grasping,
            test_grasping,
            dry_run,
            debug,
            *args,
            **kwargs
        )
        self.current_goal_id = None
        self.current_goal_name = None
        self.skill_planner = CombinedSLAPPlanner(self.robot, {})
        self.debug_visualizer = Visualizer("orientation_goal", [0, 0.5, 0.5, 0.5])
        self.interaction_visualizer = Visualizer("interaction_point", [1, 0, 0, 0.5])
        self.action_visualizer = ArrayVisualizer("slap_actions", [0.5, 0.5, 0, 0.5])

    def reset(self):
        # TODO (@priyam): clean goal info if in obs
        rospy.sleep(0.5)  # Make sure we have time to get ROS messages
        self.robot.wait()
        self._episode_start_pose = xyt2sophus(self.robot.nav.get_base_pose())
        if self.visualizer is not None:
            self.visualizer.reset()

        # Switch control mode on the robot to nav
        # Also set the robot's head into "navigation" mode - facing forward
        self.robot.move_to_nav_posture()

    def set_goal(self, info: Dict):
        vocab = ["other"] + info["object_list"] + ["other"]
        self.segmentation.reset_vocab(vocab)

        if len(info["object_list"]) > 1:
            self.current_goal_id = 2
            self.current_goal_name = info["object_list"][1]
        else:
            self.current_goal_id = 1
            self.current_goal_name = info["object_list"][0]

    def _switch_to_manip_mode(self, grasp_only=False, pre_demo_pose=False):
        """Rotate the robot and put it in the right configuration for grasping"""

        # We switch to navigation mode in order to rotate by 90 degrees
        if not self.robot.in_navigation_mode() and not self.dry_run:
            self.robot.switch_to_navigation_mode()

        # Dummy out robot execution code for perception tests
        # Also do not rotate if you are just doing grasp testing
        if grasp_only:
            if pre_demo_pose:
                self.robot.move_to_pre_demo_posture()
            else:
                self.robot.move_to_manip_posture()
            return
        if not self.dry_run and not self.test_grasping:
            print("[ENV] Rotating robot")
            self.robot.nav.navigate_to([0, 0, np.pi / 2], relative=True, blocking=True)
            self.robot.move_to_manip_posture()
            rospy.sleep(5.0)

    def apply_action(self, action: Action, info: Optional[Dict[str, Any]] = None):
        """Handle all sorts of different actions we might be inputting into this class.
        We provide both a discrete and a continuous action handler."""
        # Process the action so we know what to do with it
        if not isinstance(action, HybridAction):
            action = HybridAction(action)
        # By default - no arm control
        joints_action = None
        gripper_action = 0
        # Handle discrete actions first
        if action.is_discrete():
            action = action.get()
            continuous_action = np.zeros(3)
            if action == DiscreteNavigationAction.MOVE_FORWARD:
                print("[ENV] Move forward")
                continuous_action[0] = self.forward_step
            elif action == DiscreteNavigationAction.TURN_RIGHT:
                print("[ENV] TURN RIGHT")
                continuous_action[2] = -self.rotate_step
            elif action == DiscreteNavigationAction.TURN_LEFT:
                print("[ENV] Turn left")
                continuous_action[2] = self.rotate_step
            elif action == DiscreteNavigationAction.STOP:
                # Do nothing if "stop"
                continuous_action = None
                return True
            elif action == DiscreteNavigationAction.EXTEND_ARM:
                """Extend the robot arm"""
                print("[ENV] Extending arm")
                joints_action = self.robot.model.create_action(
                    lift=STRETCH_ARM_LIFT, arm=STRETCH_ARM_EXTENSION
                ).joints
                continuous_action = None
            elif action == DiscreteNavigationAction.MANIPULATION_MODE:
                # set goal based on info dict here
                self.set_goal(info)
                # sleeping here so observation comes from view after turning head
                if not self.robot.in_manipulation_mode():
                    self._switch_to_manip_mode()
                    rospy.sleep(2.0)
                continuous_action = None
            elif action == DiscreteNavigationAction.NAVIGATION_MODE:
                # set goal based on info dict here
                self.set_goal(info)
                continuous_action = None
                if not self.robot.in_navigation_mode():
                    self._switch_to_nav_mode()
                    print("[GeneralLanguageEnv] Sending robot to 0,0,0")
                    self.robot.nav.navigate_to(
                        np.zeros(3), relative=False, blocking=True
                    )
                continuous_action = None
            elif action == DiscreteNavigationAction.PICK_OBJECT:
                print("[ENV] Discrete pick policy")
                continuous_action = None
                # Run in a while loop until we have succeeded
                while not rospy.is_shutdown():
                    if self.dry_run:
                        # Dummy out robot execution code for perception tests
                        break
                    ok = self.grasp_planner.try_grasping(
                        wait_for_input=self.debug, visualize=self.test_grasping
                    )
                    if ok:
                        break
            elif action == DiscreteNavigationAction.SNAP_OBJECT:
                # Close the gripper
                gripper_action = 1
            elif action == DiscreteNavigationAction.DESNAP_OBJECT:
                # Open the gripper
                gripper_action = -1
            else:
                print(
                    "[Env] Action not implemented in pick-and-place environment:",
                    action,
                )
                continuous_action = None
        elif action.is_navigation():
            continuous_action = action.get()
        elif action.is_manipulation():
            if isinstance(action, ContinuousFullBodyAction):
                joints_action, continuous_action = action.get()
            else:
                pos, ori, gripper = action.get()
                continuous_action = None
                print("[ENV] Receiving a ContinuousEndEffectorAction")
                debug = False
                if debug:
                    curr_pos, curr_quat = self.robot.manip.get_ee_pose()
                    gripper = 1
                    new_pos = curr_pos + np.array([0, 0, 0.1])
                    ok = self.skill_planner.try_executing_skill(
                        [(new_pos, curr_quat, gripper)], self.robot.get_joint_state()
                    )
                # visualize p_i
                # convert p_i to global frame
                import trimesh.transformations as tra

                quat = np.array([0, 0, 0, 1])
                p_i_global = np.copy(info["interaction_point"])
                base_matrix = xyt2sophus(self.robot.nav.get_base_pose()).matrix()
                p_i_global = tra.transform_points(
                    np.expand_dims(p_i_global, axis=0), base_matrix
                )
                p_i_matrix = to_matrix(p_i_global, quat)
                self.interaction_visualizer.publish_2d(p_i_matrix)
                p_i_global = p_i_matrix[:3, 3].reshape(3)
                # TODO: visualize actions so we can introspect
                pose_matrix_array = []
                for i in range(len(pos)):
                    pose_matrix = to_matrix(pos[i], ori[i], trimesh_format=True)
                    pose_matrix_array.append(pose_matrix)
                self.action_visualizer(pose_matrix_array, frame_id="base_link")
                combined_action = np.concatenate((pos, ori, gripper), axis=-1)
                ok = self.skill_planner.try_executing_skill(combined_action, False)

        # Move, if we are not doing anything with the arm
        if continuous_action is not None and not self.test_grasping:
            print("Execute navigation action:", continuous_action)
            if not self.robot.in_navigation_mode():
                self.robot.switch_to_navigation_mode()
                # rospy.sleep(self.msg_delay_t)
            if not self.dry_run:
                print("GOTO", continuous_action)
                if "SLAP" in info.keys():
                    quat = np.array([0, 0, 0, 1])
                    # visualize everything in rviz so we can introspect
                    p_i_local = np.copy(info["interaction_point"])
                    p_i_local_matrix = to_matrix(p_i_local, quat)
                    self.interaction_visualizer.publish_2d(
                        p_i_local_matrix, frame_id="base_link"
                    )

                    # convert p_i to global frame
                    import trimesh.transformations as tra

                    p_i_global = np.copy(info["interaction_point"])
                    base_matrix = xyt2sophus(self.robot.nav.get_base_pose()).matrix()
                    p_i_global = tra.transform_points(
                        np.expand_dims(p_i_global, axis=0), base_matrix
                    )
                    p_i_matrix = to_matrix(p_i_global, quat)
                    self.interaction_visualizer.publish_2d(p_i_matrix)
                    p_i_global = p_i_matrix[:3, 3].reshape(3)

                    # add global offsets and assign global orientation
                    desired_pose_in_global = (
                        p_i_global
                        + info["offset_distance"] * info["global_offset_vector"]
                    )
                    desired_pose_in_global[2] = info["global_orientation"]
                    # Visualize
                    goal_matrix = xyt2sophus(desired_pose_in_global).matrix()
                    self.debug_visualizer(goal_matrix)
                    self.robot.nav.navigate_to(
                        desired_pose_in_global, relative=False, blocking=True
                    )
                else:
                    self.robot.nav.navigate_to(
                        continuous_action, relative=True, blocking=True
                    )
        self._handle_joints_action(joints_action)
        self._handle_gripper_action(gripper_action)
        # Update the visualizer
        if self.visualizer is not None and info is not None and "viz" in info.keys():
            print("[ENV] visualizing")
            self.visualizer.visualize(**info["viz"])
        return False

    def get_observation(self) -> Observations:
        """Get Detic and rgb/xyz/theta from the robot. Read RGB + depth + point cloud from the robot's cameras, get current pose, and use all of this to compute the observations

        Returns:
            obs: observations containing everything the robot policy will be using to make decisions, other than its own internal state.
        """
        rgb, depth, xyz = self.robot.head.get_images(
            compute_xyz=True,
        )
        current_pose = xyt2sophus(self.robot.nav.get_base_pose())

        # use sophus to get the relative translation
        relative_pose = self._episode_start_pose.inverse() * current_pose
        euler_angles = relative_pose.so3().log()
        theta = euler_angles[-1]

        # GPS in robot coordinates
        gps = relative_pose.translation()[:2]

        # Get joint state information
        joint_positions, _, _ = self.robot.get_joint_state()

        # Create the observation
        obs = home_robot.core.interfaces.Observations(
            rgb=rgb.copy(),
            depth=depth.copy(),
            xyz=xyz.copy(),
            gps=gps,
            compass=np.array([theta]),
            task_observations=self.task_info,
            # camera_pose=self.get_camera_pose_matrix(rotated=True),
            camera_pose=self.robot.head.get_pose(rotated=True),
            joint=self.robot.model.config_to_hab(joint_positions),
            relative_resting_position=np.array([0.3878479, 0.12924957, 0.4224413]),
            is_holding=np.array([0.0]),
        )
        if self.segmentation_method == DETIC:
            obs = self.segmentation.predict(obs)

            # Make sure we only have one "other" - for ??? some reason
            obs.semantic[obs.semantic == 0] = len(self.goal_options) - 1

            # Choose instance mask with highest score for goal mask
            instance_scores = obs.task_observations["instance_scores"].copy()
            class_mask = (
                obs.task_observations["instance_classes"] == self.current_goal_id
            )
            valid_instances = (
                instance_scores * class_mask
            ) > self.min_detection_threshold
            class_map = np.zeros_like(obs.task_observations["instance_map"]).astype(
                bool
            )

            # If we detected anything... check to see if our target object was found, and if so pass in the mask.
            if len(instance_scores) and np.any(class_mask):
                # Compute mask of all detected objects fitting the description
                print(valid_instances)
                for i, valid in enumerate(valid_instances):
                    if not valid:
                        continue
                    class_map = np.bitwise_or(
                        class_map, obs.task_observations["instance_map"] == i
                    )

                # Mask of the most likely candidate is "goal"
                chosen_instance_idx = np.argmax(instance_scores * class_mask)
                obs.task_observations["goal_mask"] = (
                    obs.task_observations["instance_map"] == chosen_instance_idx
                )
            else:
                obs.task_observations["goal_mask"] = np.zeros_like(obs.semantic).astype(
                    bool
                )

            obs.task_observations["goal_class_mask"] = class_map.astype(bool)
        # # Run the segmentation model here
        # if self.current_goal_id is not None:
        #     if self.segmentation_method == DETIC:
        #         obs = self.segmentation.predict(obs)
        #
        #         # Make sure we only have one "other" - for ??? some reason
        #         obs.semantic[obs.semantic == 0] = len(self.goal_options) - 1
        #
        #         # Choose instance mask with highest score for goal mask
        #         instance_scores = obs.task_observations["instance_scores"].copy()
        #         class_mask = (
        #             obs.task_observations["instance_classes"] == self.current_goal_id
        #         )
        #
        #         # If we detected anything... check to see if our target object was found, and if so pass in the mask.
        #         if len(instance_scores) and np.any(class_mask):
        #             chosen_instance_idx = np.argmax(instance_scores * class_mask)
        #             obs.task_observations["goal_mask"] = (
        #                 obs.task_observations["instance_map"] == chosen_instance_idx
        #             )
        #         else:
        #             obs.task_observations["goal_mask"] = np.zeros_like(
        #                 obs.semantic
        #             ).astype(bool)
        obs.task_observations[
            "base_camera_pose"
        ] = self.robot.head.get_pose_in_base_coords(rotated=True)

        # TODO: remove debug code
        debug_rgb_bgr = False
        if debug_rgb_bgr:
            import matplotlib.pyplot as plt

            plt.figure()
            plt.subplot(121)
            plt.imshow(obs.rgb)
            plt.subplot(122)
            plt.imshow(obs.task_observations["semantic_frame"])
            plt.show()
        return obs
