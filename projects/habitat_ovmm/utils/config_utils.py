# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import os
from typing import Optional, Tuple

from habitat_baselines.config.default import _BASELINES_CFG_DIR
from habitat_baselines.config.default import get_config as _get_habitat_config
from omegaconf import DictConfig, OmegaConf


def get_habitat_config(
    config_path: str,
    overrides: Optional[list] = None,
    configs_dir: str = _BASELINES_CFG_DIR,
) -> Tuple[DictConfig, str]:
    """Returns habitat config object composed of configs from yaml file (config_path) and overrides."""
    config = _get_habitat_config(
        config_path, overrides=overrides, configs_dir=configs_dir
    )
    return config, ""


def get_omega_config(config_path: str) -> DictConfig:
    """Returns the baseline configuration."""
    config = OmegaConf.load(config_path)
    OmegaConf.set_readonly(config, True)
    return config


def merge_configs(
    habitat_config: DictConfig, baseline_config: DictConfig, env_config: DictConfig
) -> Tuple[DictConfig, DictConfig]:
    """
    Merges habitat and baseline configurations.

    Adjusts the configuration based on the provided arguments:
    1. Removes third person sensors to improve speed if visualization is not required.
    2. Processes the episode range if specified and updates the EXP_NAME accordingly.

    :param habitat_config: habitat configuration.
    :param baseline_config: baseline configuration.
    :return: (merged agent configuration, merged env configuration)
    """

    env_config = DictConfig({**habitat_config, **env_config})

    visualize = env_config.VISUALIZE or env_config.PRINT_IMAGES
    if not visualize:
        if "robot_third_rgb" in env_config.habitat.gym.obs_keys:
            env_config.habitat.gym.obs_keys.remove("robot_third_rgb")
        if "third_rgb_sensor" in env_config.habitat.simulator.agents.main_agent.sim_sensors:
            env_config.habitat.simulator.agents.main_agent.sim_sensors.pop(
                "third_rgb_sensor"
            )

    episode_ids_range = env_config.habitat.dataset.episode_indices_range
    if episode_ids_range is not None:
        env_config.EXP_NAME = os.path.join(
            env_config.EXP_NAME, f"{episode_ids_range[0]}_{episode_ids_range[1]}"
        )

    agent_config = DictConfig({**env_config, 'AGENT': baseline_config})

    OmegaConf.set_readonly(env_config, True)
    OmegaConf.set_readonly(agent_config, True)


    return agent_config, env_config
