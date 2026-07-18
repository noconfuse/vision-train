"""定义项目命名规则与默认目录常量。"""

from contexts.training.domain.training_constants import TRAINING_DATA_DIRNAME, TRAINING_OUTPUTS_DIRNAME
from shared.utils.name_utils import TOKEN_NAME_PATTERN, validate_token_name

PROJECT_NAME_PATTERN = TOKEN_NAME_PATTERN
PROJECT_RESERVED_NAMES = {"__pycache__"}
PROJECT_MODEL_DIRNAME = "models"
PROJECT_VIDEO_DIRNAME = "videos"
PROJECT_TEMP_TASKS_DIRNAME = "temp_tasks"
PROJECT_DEFAULT_SUBDIRS = (
    TRAINING_DATA_DIRNAME,
    TRAINING_OUTPUTS_DIRNAME,
    PROJECT_MODEL_DIRNAME,
    PROJECT_VIDEO_DIRNAME,
)


def validate_project_name(name):
    """校验项目名长度、字符集与保留名称。"""
    return validate_token_name(
        name,
        empty_message="项目名不能为空",
        invalid_message="项目名只能包含字母、数字、下划线(_)、短横线(-)，长度不能超过 64 个字符",
        reserved_names=PROJECT_RESERVED_NAMES,
    )
