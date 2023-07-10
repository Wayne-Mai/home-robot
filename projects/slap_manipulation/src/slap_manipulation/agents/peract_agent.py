# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


from typing import Any, Dict, Tuple

import numpy as np
from slap_manipulation.agents.slap_agent import SLAPAgent
from slap_manipulation.policy.peract import PerceiverActorAgent, PerceiverIO

from home_robot.core.interfaces import Observations


class PeractAgent(SLAPAgent):
    def __init__(self, cfg, **kwargs):
        super().__init__(cfg, **kwargs)
        # initialize PerceiverIO Transformer
        self.perceiver_encoder = PerceiverIO(
            depth=6,
            iterations=1,
            voxel_size=self.cfg.PERACT.voxel_sizes[0],
            initial_dim=3 + 3 + 1 + 3,
            low_dim_size=3,
            layer=0,
            num_rotation_classes=72,
            num_grip_classes=2,
            num_collision_classes=2,
            num_latents=self.cfg.PERACT.num_latents,
            latent_dim=512,
            cross_heads=1,
            latent_heads=8,
            cross_dim_head=64,
            latent_dim_head=64,
            weight_tie_layers=False,
            activation="lrelu",
            input_dropout=0.1,
            attn_dropout=0.1,
            decoder_dropout=0.0,
            voxel_patch_size=5,
            voxel_patch_stride=5,
            final_dim=64,
        )
        # initialize PerceiverActor
        self.peract_agent = PerceiverActorAgent(
            coordinate_bounds=self.cfg.PERACT.scene_bounds,
            perceiver_encoder=self.perceiver_encoder,
            camera_names=self.cfg.PERACT.cameras,
            batch_size=1,
            voxel_size=self.cfg.PERACT.voxel_sizes[0],
            voxel_feature_size=3,
            num_rotation_classes=72,
            rotation_resolution=5,
            lr=0.0001,
            image_resolution=[128, 128],
            lambda_weight_l2=0.000001,
            transform_augmentation=False,
            optimizer_type="lamb",
            num_pts=8000,
        )

    def load_models(self):
        """loads weights into the PerAct model"""
        self.peract_agent.build(training=False, device=self.device)
        self.peract_agent.load_weights(self.cfg.PERACT.model_path)
        print(f"---> loaded {self.cfg.PERACT.model_path} <---")
        self._init_input = None
        self._t = None

    def create_peract_input(
        self, input: Dict[str, Any], t: int = 0, num_actions: int = 6
    ) -> Dict[str, Any]:
        """creates input for the PerAct model expecting :input: to follow
        schematics of IPM input created by SLAPAgent
        :t: time-index of the current action
        :num_actions: number of actions in the current task, time-index for
        training is created to communicate "t out of num_actions"
        """
        model_input = {}
        time_index = float((2.0 * t) / num_actions - 1)
        curr_gripper_width = input["gripper-width"]
        gripper_state = input["gripper-state"]
        proprio = np.array([curr_gripper_width, gripper_state, time_index])
        model_input["cmd"] = input["lang"]
        model_input["proprio"] = proprio
        print(proprio)
        model_input = self.to_torch(model_input)
        input.update(model_input)
        if len(input["rgb"].shape) != 3:
            input["rgb"] = input["rgb"].unsqueeze(0)
            input["xyz"] = input["xyz"].unsqueeze(0)
        return input

    def predict(self, obs: Observations) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """High-level prediction method, takes in Observations returned by
        home-robot Env and return a 6D pose for the next action"""
        info = {}
        info["p2p-motion"] = True  # PerAct predicts next pose, so point-to-point motion
        num_actions = obs.task_observations["num-actions"]
        if self._t is None:
            self._t = 0
        else:
            self._t += 1
        action = None
        self._input = self.create_interaction_prediction_input_from_obs(
            obs, filter_depth=True, debug=False
        )
        if self._init_input is None:
            self._init_input = self._input
        self.model_input = self.create_peract_input(
            self._init_input,
            t=self._t,
            num_actions=num_actions,
        )
        v0 = True
        if v0:
            result = self.peract_agent.update_for_rollout(
                self.model_input,
                center=self.model_input["mean"].detach().cpu().numpy(),
                debug=False,
            )
        else:
            result = self.peract_agent.update(
                -1,
                self.model_input,
                val=False,
                backprop=False,
            )
            result["predicted_pos"] = (
                action["predicted_pos"].detach().cpu().numpy()
                + self._init_input["mean"].detach().cpu().numpy()
            )
        return result, info

    def reset(self):
        """reset peract agent to erase previous inputs"""
        self._init_input = None
        self._t = None
