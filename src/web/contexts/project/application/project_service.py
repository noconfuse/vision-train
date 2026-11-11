"""项目上下文的跨域路径用例门面。"""

from contexts.project.infrastructure.project_paths import (
    get_project_dataset_dir,
    get_project_models_dir,
    get_project_task_dir,
    get_project_task_images_dir,
    get_project_training_dir,
    get_project_videos_dir,
)

__all__ = [
    "get_project_dataset_dir",
    "get_project_models_dir",
    "get_project_task_dir",
    "get_project_task_images_dir",
    "get_project_training_dir",
    "get_project_videos_dir",
]
