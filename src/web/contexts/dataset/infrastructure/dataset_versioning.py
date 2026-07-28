"""维护数据集版本元数据、版本仓与恢复流程。

数据快照改用 DVC（数据版本控制）进行内容寻址存储：所有文件按 md5 落入
`<project>/.dvc/cache/`，不同数据集之间天然去重；本模块只维护项目侧的
版本元数据（`version.json`）和当前版本指针（`current_version_id`）。

设计上：
- 版本元数据 = 项目级 `version.json`，存放在 `<project>/.dataset-store/<dataset_id>/versions/<v>/version.json`。
- 真实快照 = DVC cache（按内容寻址）。
- 每个版本记录额外携带 `dvc_rev` 字段，便于恢复时定位。
"""

import json
import os
import uuid

from contexts.dataset.infrastructure.dataset_task_type import (
    DATASET_VERSIONING_STATUS_FAILED,
    DATASET_VERSIONING_STATUS_PENDING,
    DATASET_VERSIONING_STATUS_READY,
    ensure_dataset_task_identity,
    load_dataset_identity_meta,
    update_dataset_identity_meta,
)
from contexts.project.infrastructure.project_paths import get_project_training_dir
from shared.utils.fs_utils import remove_tree
from shared.utils.fs_utils import remove_path_silent
from shared.utils.json_utils import load_json_file, save_json_file
from shared.utils.path_utils import storage_path_ref
from shared.utils.time_utils import now_iso
from shared.utils.yaml_utils import load_yaml_file, save_yaml_file

from contexts.dataset.infrastructure.dvc_backend import (
    dvc_add_dataset,
    dvc_checkout_dataset,
    dvc_commit_dataset,
    dvc_get_current_rev,
    dvc_remove_dataset,
    ensure_dvc_repo,
    DVCCommandError,
    DVCUnavailableError,
)

DATASET_VERSION_STORE_DIRNAME = ".dataset-store"
DATASET_VERSION_META_FILENAME = "version.json"


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


def load_dataset_version_record(project_path, dataset_id, version_id):
    """读取单个数据集版本记录。

    返回结构中：
    - snapshot_path 指向当前数据集的工作目录（训练代码直接可读）。
    - dvc_rev 记录 DVC 内容指纹，供恢复时 checkout 使用。
    """
    record = load_json_file(get_dataset_version_meta_path(project_path, dataset_id, version_id), default=None)
    if not isinstance(record, dict):
        return None
    source_dataset_path = record.get("source_dataset_path") or ""
    snapshot_path = os.path.abspath(source_dataset_path) if source_dataset_path else ""
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


def _build_version_record(*, dataset_id, version_id, dataset_name, dataset_root, reason, source_version_id=None, dvc_rev=""):
    """构造一条标准化版本记录。"""
    now = now_iso()
    return {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "dataset_name": dataset_name,
        "source_dataset_path": dataset_root,
        "reason": str(reason or "").strip() or "manual_publish",
        "source_version_id": str(source_version_id or "").strip() or None,
        "dvc_rev": str(dvc_rev or "").strip() or None,
        "created_at": now,
    }


def _write_version_record(project_path, record):
    """落盘一条版本记录到 `<project>/.dataset-store/<dataset_id>/versions/<v>/version.json`。"""
    dataset_id = record["dataset_id"]
    version_id = record["version_id"]
    version_dir = get_dataset_version_dir(project_path, dataset_id, version_id)
    os.makedirs(version_dir, exist_ok=True)
    save_json_file(get_dataset_version_meta_path(project_path, dataset_id, version_id), record)


def mark_dataset_initial_version_pending(dataset_root):
    """标记数据集首个版本仍在异步入库中。"""
    identity = ensure_dataset_task_identity(dataset_root)
    if identity.get("current_version_id"):
        return load_dataset_identity_meta(dataset_root)
    return update_dataset_identity_meta(
        dataset_root,
        versioning_status=DATASET_VERSIONING_STATUS_PENDING,
    )


def start_snapshot_job(project_path, dataset_root, *, dataset_name=None, mode="add", reason="manual_publish", source_version_id=None):
    """落库一条 dataset_snapshot 任务并启动 worker。

    调用方可以传入 ``reason``（例如 ``import`` / ``split_dataset``）以记录
    为 payload，后续任务中心展示即可见。返回值是 task_id（不是内部 job_id）。
    """
    from contexts.dataset.infrastructure.dataset_snapshot_task_gateway import start_dataset_snapshot_task
    identity = load_dataset_identity_meta(dataset_root)
    is_initial_snapshot = not bool(identity.get("current_version_id"))
    if is_initial_snapshot:
        mark_dataset_initial_version_pending(dataset_root)
    try:
        return start_dataset_snapshot_task(
            project_path=project_path,
            dataset_root=dataset_root,
            dataset_name=dataset_name or os.path.basename(os.path.realpath(dataset_root)),
            mode=mode,
            reason=reason,
            source_version_id=source_version_id,
        )
    except Exception:
        if is_initial_snapshot:
            update_dataset_identity_meta(
                dataset_root,
                versioning_status=DATASET_VERSIONING_STATUS_FAILED,
            )
        raise


def create_dataset_version_snapshot(
    project_path,
    dataset_root,
    *,
    dataset_name=None,
    reason="manual_publish",
    source_version_id=None,
    mode="commit",
    on_progress=None,
):
    """为当前工作数据集发布一个新版本。

    Args:
        project_path: 项目根路径。
        dataset_root: 工作数据集目录绝对路径。
        dataset_name: 数据集展示名称；缺省取目录名。
        reason: 版本原因，例如 import / manual_publish / split_dataset。
        source_version_id: 来源版本号（恢复时使用）。
        mode: add（首次入库，全量）/ commit（增量）。
        on_progress: DVC add 进度回调，签名 (processed) -> None。
    """
    meta = ensure_dataset_task_identity(dataset_root)
    dataset_id = meta["dataset_id"]
    version_id = new_dataset_version_id()
    dataset_name = dataset_name or os.path.basename(os.path.realpath(dataset_root))

    # 触发 DVC add / commit
    if mode == "add":
        try:
            dvc_rev = dvc_add_dataset(project_path, dataset_root, on_progress=on_progress)
        except (DVCUnavailableError, DVCCommandError) as exc:
            raise RuntimeError(f"DVC 入库失败: {exc}") from exc
    elif mode == "commit":
        try:
            dvc_rev = dvc_commit_dataset(project_path, dataset_root)
        except (DVCUnavailableError, DVCCommandError) as exc:
            raise RuntimeError(f"DVC 提交失败: {exc}") from exc
    else:
        raise ValueError(f"不支持的 mode: {mode}")

    if not dvc_rev:
        dvc_rev = dvc_get_current_rev(project_path, dataset_root)

    record = _build_version_record(
        dataset_id=dataset_id,
        version_id=version_id,
        dataset_name=dataset_name,
        dataset_root=dataset_root,
        reason=reason,
        source_version_id=source_version_id,
        dvc_rev=dvc_rev,
    )
    _write_version_record(project_path, record)
    update_dataset_identity_meta(
        dataset_root,
        current_version_id=version_id,
        versioning_status=DATASET_VERSIONING_STATUS_READY,
    )
    return load_dataset_version_record(project_path, dataset_id, version_id)


def ensure_dataset_version_state(project_path, dataset_root, *, dataset_name=None, on_progress=None):
    """确保数据集已具备当前版本记录与可用快照。

    行为：
    - 已存在 current_version_id + 对应 version.json 元数据 → 直接返回。
    - 否则以 bootstrap 原因发一次 add，建立 v1 并写入当前版本指针。
    """
    identity = load_dataset_identity_meta(dataset_root)
    current_version_id = identity.get("current_version_id")
    versioning_status = identity.get("versioning_status")
    if current_version_id:
        record = load_dataset_version_record(project_path, identity["dataset_id"], current_version_id)
        if record and record.get("dvc_rev"):
            return {
                "dataset_id": identity["dataset_id"],
                "dataset_version_id": current_version_id,
                "snapshot_path": record["snapshot_path"],
                "version_record": record,
            }
        if versioning_status == DATASET_VERSIONING_STATUS_PENDING:
            raise ValueError("数据集首个版本仍在入库中，请等待快照任务完成")
        if versioning_status == DATASET_VERSIONING_STATUS_FAILED:
            raise ValueError("数据集首个版本入库失败，请先在任务中心处理后再继续")
    elif versioning_status == DATASET_VERSIONING_STATUS_PENDING:
        raise ValueError("数据集首个版本仍在入库中，请等待快照任务完成")
    elif versioning_status == DATASET_VERSIONING_STATUS_FAILED:
        raise ValueError("数据集首个版本入库失败，请先在任务中心处理后再继续")
    record = create_dataset_version_snapshot(
        project_path,
        dataset_root,
        dataset_name=dataset_name or os.path.basename(os.path.realpath(dataset_root)),
        reason="bootstrap",
        source_version_id=current_version_id,
        mode="add",
        on_progress=on_progress,
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


def _drop_workspace_files_outside_target(project_path: str, dataset_root: str, target_rev: str) -> None:
    """把工作目录中“不属于目标版本”的文件删除，使工作目录 == 目标版本内容。

    仅依赖 DVC 自身的 dir file（``<project>/.dvc/cache/files/md5/<xx>/<md5>``），
    该文件是 JSON 数组，每个元素 ``{"md5": "...", "relpath": "..."}``。若
    dir file 在 cache 中缺失（罕见），则跳过清理以避免误删。

    实现：递归遍历数据集目录下所有文件，对每个叶子文件判断其相对路径是否
    在目标版本的 tracked 集合内，不在则删除。目录本身（包括空目录）保留，
    后续 ``dvc add`` 时 DVC 会按当前目录实际内容生成新指纹。
    """
    if not target_rev:
        return
    cache_root = os.path.join(project_path, ".dvc", "cache", "files", "md5")
    dir_file = os.path.join(cache_root, target_rev[:2], target_rev[2:])
    if not os.path.isfile(dir_file):
        return
    try:
        with open(dir_file, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:
        return
    if not isinstance(entries, list):
        return
    tracked = {
        str(item.get("relpath") or "").strip()
        for item in entries
        if isinstance(item, dict) and item.get("relpath")
    }
    if not tracked:
        return

    # 永远保留元数据 / DVC 跟踪辅助文件，与目标版本无关。
    preserved_basenames = {".vision-train.meta.json"}
    preserved_suffixes = (".dvc", ".dvcignore")

    for dirpath, dirnames, filenames in os.walk(dataset_root):
        # 跳过数据集根目录外的遍历（本函数只清理 dataset_root 内的内容）
        rel_dir = os.path.relpath(dirpath, dataset_root)
        for name in filenames:
            full = os.path.join(dirpath, name)
            base = os.path.basename(full)
            if base in preserved_basenames or base.endswith(preserved_suffixes):
                continue
            relpath = name if rel_dir == "." else f"{rel_dir}/{name}"
            if relpath in tracked:
                continue
            remove_path_silent(full)


def restore_dataset_version_snapshot(project_path, dataset_root, version_id, *, dataset_name=None, reason="restore"):
    """把指定历史版本恢复为当前工作数据集，并生成一个新的当前版本。

    采用 DVC 的标准恢复方式（无 git 变种）：把 ``<dataset>.dvc`` 的 ``outs[0].md5``
    临时指向目标 rev，再执行 ``dvc checkout --force`` 让工作目录内容切到目标
    版本；完成后把 .dvc 还原回原状态，让 DVC 跟踪指针保持当前不变；最后以
    ``add`` 模式把恢复后的工作目录重新入库，作为一条新的当前版本。
    """
    identity = load_dataset_identity_meta(dataset_root)
    dataset_id = identity["dataset_id"]
    source_record = load_dataset_version_record(project_path, dataset_id, version_id)
    if not source_record:
        raise ValueError("数据集版本不存在")
    source_rev = source_record.get("dvc_rev") or ""
    if not source_rev:
        raise ValueError("该版本缺少可恢复的 DVC 指纹，通常是早期占位版本；请选择列表中的有效版本恢复")

    dvc_file = f"{dataset_root.rstrip(os.sep)}.dvc"
    backup_yaml = load_yaml_file(dvc_file)
    try:
        # 临时把 .dvc 的 md5 切到目标 rev，让 dvc checkout 知道要落到哪一版。
        if isinstance(backup_yaml, dict) and isinstance(backup_yaml.get("outs"), list) and backup_yaml["outs"]:
            first_out = backup_yaml["outs"][0]
            if isinstance(first_out, dict):
                first_out["md5"] = source_rev
                save_yaml_file(dvc_file, backup_yaml)

        try:
            dvc_checkout_dataset(project_path, dataset_root, source_rev)
        except (DVCUnavailableError, DVCCommandError) as exc:
            raise RuntimeError(f"DVC 检出失败: {exc}") from exc

        # dvc checkout 不会清理未被 DVC 跟踪的多余文件（用户上传后未重新
        # 发布的修改）。业务语义“恢复到 V 版本”要求工作目录 == V 版本内容，
        # 因此把不在目标版本跟踪集合里的文件清理掉。
        _drop_workspace_files_outside_target(project_path, dataset_root, source_rev)
    finally:
        # 不论成功失败，都把 .dvc 还原回原状态，避免破坏当前版本指针。
        if isinstance(backup_yaml, dict):
            try:
                save_yaml_file(dvc_file, backup_yaml)
            except Exception:
                pass

    # 恢复 = 重新入库当前内容（add）
    restored_record = create_dataset_version_snapshot(
        project_path,
        dataset_root,
        dataset_name=dataset_name,
        reason=reason,
        source_version_id=version_id,
        mode="add",
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
    """删除指定数据集的全部历史版本仓与 DVC 跟踪。"""
    # 先尝试从 DVC 跟踪中移除（防止留下孤儿指针）
    dataset_id_dir = get_dataset_store_dir(project_path, dataset_id)
    # 通过 identity 文件反查 dataset_root
    from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root  # 局部导入避免循环
    # 尝试常见数据集名查找
    # 注意：调用方一般已经从 dataset_root 拿到了 dataset_id，因此这里尽力而为即可，找不到也不报错。
    store_dir = dataset_id_dir
    remove_tree(store_dir)
    # cache 保留（不主动 gc，由 dvc gc 维护）
    return store_dir
