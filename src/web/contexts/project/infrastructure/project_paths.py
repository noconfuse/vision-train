"""统一项目目录、数据集目录与任务目录路径访问。"""

import os

from contexts.project.domain.policies import (
    PROJECT_MODEL_DIRNAME,
    PROJECT_TEMP_TASKS_DIRNAME,
    PROJECT_VIDEO_DIRNAME,
)
from contexts.training.domain.training_constants import TRAINING_DATA_DIRNAME


def get_project_training_dir(project_path):
    """返回项目训练数据根目录。"""
    return os.path.join(project_path, TRAINING_DATA_DIRNAME)


def get_project_models_dir(project_path):
    """返回项目模型目录。"""
    return os.path.join(project_path, PROJECT_MODEL_DIRNAME)


def get_project_videos_dir(project_path):
    """返回项目视频目录。"""
    return os.path.join(project_path, PROJECT_VIDEO_DIRNAME)


def get_project_dataset_dir(project_path, dataset_name):
    """返回项目下某个数据集目录。"""
    return os.path.join(get_project_training_dir(project_path), str(dataset_name))


def get_project_task_dir(project_path, task_id):
    """返回任务专属工作目录。"""
    return os.path.join(project_path, PROJECT_TEMP_TASKS_DIRNAME, str(task_id))


def get_project_task_images_dir(project_path, task_id):
    """返回任务抽帧图片目录。"""
    return os.path.join(get_project_task_dir(project_path, task_id), "images")
