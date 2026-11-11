"""GPU 服务器配置的数据库读写。"""

import logging

from db import session_scope
from db.models import ComputeTarget
from shared.utils.time_utils import now_iso

logger = logging.getLogger(__name__)


def list_targets():
    """按名称排序返回全部 GPU 服务器。"""
    with session_scope() as session:
        rows = session.query(ComputeTarget).order_by(ComputeTarget.name).all()
        return [row.to_dict() for row in rows]


def get_target(target_id):
    """按 id 返回单台 GPU 服务器，不存在返回 None。"""
    with session_scope() as session:
        row = session.get(ComputeTarget, str(target_id or ""))
        return row.to_dict() if row else None


def create_target(name, ssh_host, remote_workspace, device, keep_remote_copy=False):
    """新建一台 GPU 服务器。"""
    now = now_iso()
    target = ComputeTarget(
        name=name,
        ssh_host=ssh_host,
        remote_workspace=remote_workspace,
        device=device,
        keep_remote_copy=bool(keep_remote_copy),
        created_at=now,
        updated_at=now,
    )
    with session_scope() as session:
        session.add(target)
        session.flush()
        return target.to_dict()


def update_target(target_id, patch):
    """按补丁更新一台 GPU 服务器；没有任何字段变化时返回 None。"""
    with session_scope() as session:
        target = session.get(ComputeTarget, str(target_id or ""))
        if not target:
            logger.warning("compute_target %s 不存在，跳过更新", target_id)
            return None
        for key, value in patch.items():
            if hasattr(target, key) and value is not None:
                setattr(target, key, value)
        target.updated_at = now_iso()
        session.flush()
        return target.to_dict()


def delete_target(target_id):
    """删除一台 GPU 服务器记录，返回是否删掉了一行。"""
    with session_scope() as session:
        target = session.get(ComputeTarget, str(target_id or ""))
        if not target:
            return False
        session.delete(target)
    return True


def require_target(target_id):
    """取一台必须存在的 GPU 服务器，取不到就把原因说清。"""
    target = get_target(target_id)
    if not target:
        raise ValueError(f"GPU 服务器不存在（id={target_id}），请在训练页面重新选择运行位置")
    return target
