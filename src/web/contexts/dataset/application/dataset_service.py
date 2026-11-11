"""数据集上下文的跨域用例门面。

其他上下文需要读取数据集布局、配置、任务类型与版本快照时，统一走本模块。
"""

from contexts.dataset.infrastructure.dataset_import_yolo import ensure_dataset_yaml
from contexts.dataset.infrastructure.dataset_layout import (
    STANDARD_DATASET_SPLITS,
    build_label_relpath,
    extract_classification_class_name,
    get_dataset_auto_labels_dir,
    get_dataset_auto_meta_path,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_split_content_dir,
    get_dataset_split_dir,
    get_dataset_unlabeled_dir,
)
from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_schema import (
    find_dataset_config,
    load_dataset_names,
    load_dataset_yaml,
    load_dataset_yaml_ref,
    normalize_dataset_yaml_for_training,
    resolve_dataset_names_list,
    save_standard_dataset_yaml,
)
from contexts.dataset.infrastructure.dataset_task_type import (
    ensure_dataset_task_identity,
    load_dataset_identity_meta,
    load_dataset_vision_task_type,
)
from contexts.dataset.infrastructure.dataset_versioning import (
    ensure_dataset_version_state,
    get_dataset_store_dir,
    require_current_dataset_snapshot,
)

__all__ = [
    "STANDARD_DATASET_SPLITS",
    "build_label_relpath",
    "ensure_dataset_task_identity",
    "ensure_dataset_version_state",
    "ensure_dataset_yaml",
    "extract_classification_class_name",
    "find_dataset_config",
    "get_dataset_auto_labels_dir",
    "get_dataset_auto_meta_path",
    "get_dataset_images_dir",
    "get_dataset_labels_dir",
    "get_dataset_split_content_dir",
    "get_dataset_split_dir",
    "get_dataset_store_dir",
    "get_dataset_unlabeled_dir",
    "load_dataset_identity_meta",
    "load_dataset_names",
    "load_dataset_vision_task_type",
    "load_dataset_yaml",
    "load_dataset_yaml_ref",
    "normalize_dataset_yaml_for_training",
    "require_current_dataset_snapshot",
    "resolve_dataset_names_list",
    "resolve_project_dataset_root",
    "save_standard_dataset_yaml",
]
