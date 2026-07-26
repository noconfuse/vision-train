"""维护数据集版本仓、不可变快照与恢复流程。"""

import os
import shutil
import tempfile
import uuid

from contexts.dataset.infrastructure.dataset_task_type import (
    ensure_dataset_task_identity,
    load_dataset_identity_meta,
    update_dataset_identity_meta,
)
from contexts.project.infrastructure.project_paths import get_project_training_dir
from shared.utils.fs_utils import move_path, remove_tree
from shared.utils.json_utils import load_json_file, save_json_file
from shared.utils.path_utils import storage_path_ref
from shared.utils.time_utils import now_iso

DATASET_VERSION_STORE_DIRNAME = ".dataset-store"
DATASET_VERSION_META_FILENAME = "version.json"
DATASET_VERSION_SNAPSHOT_DIRNAME = "snapshot"


def new_dataset_version_id():
    """生成短格式数据集版本标识。"""
    return uuid.uuid4().hex[:12]


def get_project_dataset_store_dir(project_path):
    """返回项目级数据集版本仓目录。"""
    return os.path.join(get_project_training_dir(project_path), DATASET_VERSION_STORE_DIRNAME)


def get_dataset_store_dir(project_path, dataset_id):
    """返回指定数据集的版本仓目录。"""
    return os.path.join(get_project_dataset_store_dir(project_path), str(dataset_id))


def get_dataset_versions_dir(project_path, dataset_id):
    """返回指定数据集的版本目录。"""
    return os.path.join(get_dataset_store_dir(project_path, dataset_id), "versions")


def get_dataset_version_dir(project_path, dataset_id, version_id):
    """返回指定版本目录。"""
    return os.path.join(get_dataset_versions_dir(project_path, dataset_id), str(version_id))


def get_dataset_version_meta_path(project_path, dataset_id, version_id):
    """返回指定版本元数据文件路径。"""
    return os.path.join(get_dataset_version_dir(project_path, dataset_id, version_id), DATASET_VERSION_META_FILENAME)


def get_dataset_version_snapshot_dir(project_path, dataset_id, version_id):
    """返回指定版本快照目录。"""
    return os.path.join(get_dataset_version_dir(project_path, dataset_id, version_id), DATASET_VERSION_SNAPSHOT_DIRNAME)


def load_dataset_version_record(project_path, dataset_id, version_id):
    """读取单个数据集版本记录。"""
    record = load_json_file(get_dataset_version_meta_path(project_path, dataset_id, version_id), default=None)
    if not isinstance(record, dict):
        return None
    snapshot_path = get_dataset_version_snapshot_dir(project_path, dataset_id, version_id)
    return {
        **record,
        "snapshot_path": snapshot_path,
    }


def list_dataset_version_records(project_path, dataset_id):
    """列出指定数据集的全部版本记录。"""
    versions_dir = get_dataset_versions_dir(project_path, dataset_id)
    if not os.path.isdir(versions_dir):
        return []
    records = []
    for version_id in os.listdir(versions_dir):
        record = load_dataset_version_record(project_path, dataset_id, version_id)
        if record:
            records.append(record)
    records.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return records


def get_current_dataset_version_record(project_path, dataset_root):
    """读取当前工作数据集绑定的版本记录。"""
    identity = load_dataset_identity_meta(dataset_root)
    current_version_id = identity.get("current_version_id")
    if not current_version_id:
        return None
    return load_dataset_version_record(project_path, identity["dataset_id"], current_version_id)


def ensure_dataset_version_state(project_path, dataset_root, *, dataset_name=None):
    """确保数据集已具备当前版本记录与可用快照。"""
    identity = load_dataset_identity_meta(dataset_root)
    current_version_id = identity.get("current_version_id")
    if current_version_id:
        record = load_dataset_version_record(project_path, identity["dataset_id"], current_version_id)
        if record and os.path.isdir(record["snapshot_path"]):
            return {
                "dataset_id": identity["dataset_id"],
                "dataset_version_id": current_version_id,
                "snapshot_path": record["snapshot_path"],
                "version_record": record,
            }
    record = create_dataset_version_snapshot(
        project_path,
        dataset_root,
        dataset_name=dataset_name or os.path.basename(os.path.realpath(dataset_root)),
        reason="bootstrap",
        source_version_id=current_version_id,
    )
    return {
        "dataset_id": record["dataset_id"],
        "dataset_version_id": record["version_id"],
        "snapshot_path": record["snapshot_path"],
        "version_record": record,
    }


def require_current_dataset_snapshot(project_path, dataset_root):
    """返回当前数据集绑定的快照路径及其版本信息。"""
    return ensure_dataset_version_state(project_path, dataset_root)


def _copy_dataset_tree(source_root, target_root):
    """复制整个数据集目录为不可变快照。"""
    shutil.copytree(source_root, target_root)


def _build_version_record(*, dataset_id, version_id, dataset_name, dataset_root, reason, source_version_id=None):
    """构造一条标准化版本记录。"""
    now = now_iso()
    return {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "dataset_name": dataset_name,
        "source_dataset_path": dataset_root,
        "reason": str(reason or "").strip() or "manual_publish",
        "source_version_id": str(source_version_id or "").strip() or None,
        "created_at": now,
    }


def create_dataset_version_snapshot(project_path, dataset_root, *, dataset_name=None, reason="manual_publish", source_version_id=None):
    """为当前工作数据集创建一份不可变版本快照。"""
    meta = ensure_dataset_task_identity(dataset_root)
    dataset_id = meta["dataset_id"]
    version_id = new_dataset_version_id()
    dataset_name = dataset_name or os.path.basename(os.path.realpath(dataset_root))
    version_record = _build_version_record(
        dataset_id=dataset_id,
        version_id=version_id,
        dataset_name=dataset_name,
        dataset_root=dataset_root,
        reason=reason,
        source_version_id=source_version_id,
    )

    versions_dir = get_dataset_versions_dir(project_path, dataset_id)
    os.makedirs(versions_dir, exist_ok=True)
    temp_version_dir = tempfile.mkdtemp(prefix=f"vt_dataset_version_{version_id}_", dir=versions_dir)
    try:
        snapshot_dir = os.path.join(temp_version_dir, DATASET_VERSION_SNAPSHOT_DIRNAME)
        _copy_dataset_tree(dataset_root, snapshot_dir)
        update_dataset_identity_meta(snapshot_dir, current_version_id=version_id)
        save_json_file(os.path.join(temp_version_dir, DATASET_VERSION_META_FILENAME), version_record)
        final_version_dir = get_dataset_version_dir(project_path, dataset_id, version_id)
        if os.path.exists(final_version_dir):
            raise ValueError(f"数据集版本 {version_id} 已存在")
        move_path(temp_version_dir, final_version_dir)
    except Exception:
        remove_tree(temp_version_dir)
        raise

    update_dataset_identity_meta(dataset_root, current_version_id=version_id)
    return load_dataset_version_record(project_path, dataset_id, version_id)


def restore_dataset_version_snapshot(project_path, dataset_root, version_id, *, dataset_name=None, reason="restore"):
    """把指定历史版本恢复为当前工作数据集，并生成一个新的当前版本。"""
    identity = load_dataset_identity_meta(dataset_root)
    dataset_id = identity["dataset_id"]
    source_record = load_dataset_version_record(project_path, dataset_id, version_id)
    if not source_record:
        raise ValueError("数据集版本不存在")
    source_snapshot_dir = source_record["snapshot_path"]
    if not os.path.isdir(source_snapshot_dir):
        raise ValueError("数据集版本快照不存在")

    parent_dir = os.path.dirname(os.path.realpath(dataset_root))
    temp_restore_root = tempfile.mkdtemp(prefix="vt_dataset_restore_", dir=parent_dir)
    try:
        remove_tree(temp_restore_root)
        _copy_dataset_tree(source_snapshot_dir, temp_restore_root)
        remove_tree(dataset_root)
        move_path(temp_restore_root, dataset_root)
    except Exception:
        remove_tree(temp_restore_root)
        raise

    restored_record = create_dataset_version_snapshot(
        project_path,
        dataset_root,
        dataset_name=dataset_name,
        reason=reason,
        source_version_id=version_id,
    )
    return {
        "restored_from_version": {
            **source_record,
            "snapshot_path": storage_path_ref(source_record["snapshot_path"]),
            "source_dataset_path": storage_path_ref(source_record["source_dataset_path"]),
        },
        "current_version": {
            **restored_record,
            "snapshot_path": storage_path_ref(restored_record["snapshot_path"]),
            "source_dataset_path": storage_path_ref(restored_record["source_dataset_path"]),
        },
    }


def delete_dataset_version_store(project_path, dataset_id):
    """删除指定数据集的全部历史版本仓。"""
    store_dir = get_dataset_store_dir(project_path, dataset_id)
    remove_tree(store_dir)
    return store_dir
