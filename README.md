# Home Robot

[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/facebookresearch/home-robot/blob/main/LICENSE)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-370/)
[![CircleCI](https://dl.circleci.com/status-badge/img/gh/facebookresearch/home-robot/tree/main.svg?style=shield)](https://dl.circleci.com/status-badge/redirect/gh/facebookresearch/home-robot/tree/main)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat)](https://timothycrosley.github.io/isort/)

Your open-source robotic mobile manipulation stack!

HomeRobot lets you get started running a range of robotics tasks on a low-cost mobile manipulator, starting with _Open Vocabulary Mobile Manipulation_, or OVMM. OVMM is a challenging task which means that, in an unknown environment, a robot must:
  - Explore its environment
  - Find an object
  - Find a receptacle -- a location on which it must place this object
  - Put the object down on the receptacle.

## Core Concepts

This package assumes you have a low-cost mobile robot with limited compute -- initially a [Hello Robot Stretch](hello-robot.com/) -- and a "workstation" with more GPU compute. Both are assumed to be running on the same network.

This is the recommended workflow for hardware robots:
  - Turn on your robot; for the Stretch, run `stretch_robot_home.py` to get it ready to use.
  - From your workstation, SSH into the robot and start a [ROS launch file](http://wiki.ros.org/roslaunch) which brings up necessary low-level control and hardware drivers.
  - If desired, run [rviz](http://wiki.ros.org/rviz) on the workstation to see what the robot is seeing.
  - Start running your AI code on the workstation - For example, you can run `python projects/stretch_grasping/eval_episode.py` to run the OVMM task.

We provide a couple connections for useful perception libraries like [Detic](https://github.com/facebookresearch/Detic) and [Contact Graspnet](https://github.com/NVlabs/contact_graspnet), which you can then use as a part of your methods.

There are two core classes in HomeRobot that you need to be concerned with:
  - *Environments* extend the [abstract Environment class](https://github.com/facebookresearch/home-robot/blob/main/src/home_robot/home_robot/core/abstract_env.py) and provide *observations* of the world, and a way to *apply actions*.
  - *Agents* extend the [abstract Agent class](https://github.com/facebookresearch/home-robot/blob/main/src/home_robot/home_robot/core/abstract_agent.py), which takes in an [observation](https://github.com/facebookresearch/home-robot/blob/main/src/home_robot/home_robot/core/interfaces.py#L95) and produces an [action](https://github.com/facebookresearch/home-robot/blob/main/src/home_robot/home_robot/core/interfaces.py#L50).

### Organization

[HomeRobot](https://github.com/facebookresearch/home-robot/) is broken up into three different packages:

| Resource | Description |
| -------- | ----------- |
| [home_robot](src/home_robot) | Core package |
| [home_robot_sim](src/home_robot_sim) | Simulation |
| [home_robot_hw](src/home_robot_hw) | ROS package containing hardware drivers for the Hello Stretch Robot |

The [home_robot](src/home_robot) package contains embodiment-agnostic agent code, such as our [ObjectNav agent](https://github.com/facebookresearch/home-robot/blob/main/src/home_robot/home_robot/agent/objectnav_agent/objectnav_agent.py) (finds objects in scenes) and our [hierarchical OVMM agent](https://github.com/facebookresearch/home-robot/blob/main/src/home_robot/home_robot/agent/ovmm_agent/ovmm_agent.py). YThese agents can be extended or modified to implement your own solution.

Importantly, agents use a fixed set of [interfaces](https://github.com/facebookresearch/home-robot/blob/main/src/home_robot/home_robot/core/interfaces.py)

The [home_robot_sim](src/home_robot_sim) package contains code for interface

## Installation

### Preliminary

Installation on a workstation requires [conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html) and [mamba](https://mamba.readthedocs.io/en/latest/user_guide/mamba.html).

Installation on a robot assumes Ubuntu 20.04 and [ROS Noetic](http://wiki.ros.org/noetic).


### Instructions for Hardware stack on a Hello Robot Stretch
See the [ROS installation instructions](src/home_robot_hw/install_robot.md) in `home_robot_hw`. 

### Instructions for GPU-enabled workstation

```
# Create a conda env
mamba env create  -f ./src/home_robot_hw/environment.yml 
conda activate home_robot_env

# Install PyTorch depending on your workstation CUDA version 
# See [here](https://pytorch.org/get-started/locally/)

# Install the core home_robot package
pip install -e src/home_robot

# Install home_robot_hw
pip install -e src/home_robot_hw
```

Follow the [workstation setup instructions](src/home_robot_hw/install_workstation.md) to setup ROS Network on your GPU-enabled workstation. 

### Instructions for Simulation stack with Habitat
1. Install torch version based on your system's CUDA version. Check CUDA version with `nvidia-smi`.
1. Use need to be in `home-robot` folder to execute the following commands.
    ```
    # currently in home-robot dir and home_robot_env conda/mamba environment!

    # Install habitat sim and update submodules
    mamba install -c conda-forge -c aihabitat habitat-sim withbullet
    git submodule update --init --recursive

    # Install habitat lab on the correct (object rearrange) branch
    pip install -e src/third_party/habitat-lab/habitat-lab  # NOTE: Habitat-lab@v0.2.2 only works in editable mode

    # Install home robot sim interfaces
    pip install -e src/home_robot_sim
    ```
1. To test your installation, you can run:
    ```
    <!-- TODO -->
    ```
For general details, see the [installation instructions]() in `home_robot_sim`. 

### OVMM challenge

#### Object Nav
1. Download Detic checkpoint as per the instructions [here](https://github.com/facebookresearch/Detic)
    ```
    cd $HOME-ROBOT-PATH/src/home_robot/perception/detection/detic/Detic/
    mkdir models
    wget https://dl.fbaipublicfiles.com/detic/Detic_LCOCOI21k_CLIP_SwinB_896b32_4x_ft4x_max-size.pth -O models/Detic_LCOCOI21k_CLIP_SwinB_896b32_4x_ft4x_max-size.pth --no-check-certificate
    ```
1. [ WIP ] Run the Object Nav test to make the robot navigate to a cup.  
    ```
    python projects/stretch_objectnav/eval_episode.py
    ```
    To change the objects detected, modify the `REAL_WORLD_CATEGORIES` list  in `src/home_robot_hw/home_robot_hw/env/stretch_object_nav_env.py`. 
<!-- TODO: add main aspects like stretch_objectnav, stretch_ovmm (for grasping). -->

#### Grasping
See [here](projects/stretch_ovmm/README.md).

### Network Setup

Proper network setup is crucial to getting good performance with HomeRobot. Low-cost mobile robots often do not have sufficient GPU to run state-of-the-art perception models. Instead, we rely on a client-server architecture, where ROS and low-level controllers run on the robot, and CPU- and GPU-intensive AI code runs on a workstation.

After following the installation instructions, we recommend setting up your `~/.bashrc` on the robot workstation:

```
# Whatever your workstation's IP address is
export WORKSTATION_IP=10.0.0.2
# Whatever your robot's IP address is
export HELLO_ROBOT_IP=10.0.0.6

export ROS_IP=$WORKSTATION_IP
export ROS_MASTER_URI=http://$HELLO_ROBOT_IP:11311

# Optionally - make it clear to avoid issues
echo "Setting ROS_MASTER_URI to $ROS_MASTER_URI"
echo "Setting ROS IP to $ROS_IP"

# Helpful alias - connect to the robot
alias ssh-robot="ssh hello-robot@$HELLO_ROBOT_IP"
```

## Code Contribution

We use linters for enforcing good code style. The `lint` test will not pass if your code does not conform.

Install the git [pre-commit](https://pre-commit.com/) hooks by running
```bash
python -m pip install pre-commit
cd $HOME_ROBOT_ROOT
pre-commit install
```

To format manually, run: `pre-commit run --show-diff-on-failure --all-files`

## Troubleshooting
- Errors on installing Detectron2: check `nvcc --version` and make sure it matches the cuda drivers.
- 

## License
Home Robot is MIT licensed. See the [LICENSE](./LICENSE) for details.

## References (temp)

- [hello-robot/stretch_body](https://github.com/hello-robot/stretch_body)
  - Base API for interacting with the Stretch robot
  - Some scripts for interacting with the Stretch
- [hello-robot/stretch_ros](https://github.com/hello-robot/stretch_ros)
  - Builds on top of stretch_body
  - ROS-related code for Stretch
- [RoboStack/ros-noetic](https://github.com/RoboStack/ros-noetic)
  - Conda stream with ROS binaries
