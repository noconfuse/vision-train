"""归一化并校验 GPU 服务器配置的各个字段。"""

import re

from shared.kernel.errors import DomainError
from shared.utils.value_utils import parse_bool

SSH_HOST_PATTERN = re.compile(r"^[A-Za-z0-9@._:\[\]-]+$")
DEVICE_PATTERN = re.compile(r"^\d+(,\d+)*$")
NAME_MAX_LENGTH = 64
# 远端工作目录留空时的默认落点：Linux 上 /dev/shm 就是内存盘，数据不落服务器硬盘。
DEFAULT_REMOTE_WORKSPACE = "/dev/shm/vision-train"
DEFAULT_DEVICE = "0"


class RemoteWorkspaceNotAbsolute(DomainError):
    """远端工作目录必须是绝对路径，否则拼出来的路径跟着启动时的 cwd 走。"""


def normalize_name(name):
    """整理服务器名称。"""
    cleaned = str(name or "").strip()
    if not cleaned:
        raise DomainError("服务器名称不能为空")
    if len(cleaned) > NAME_MAX_LENGTH:
        raise DomainError(f"服务器名称不能超过 {NAME_MAX_LENGTH} 个字符")
    return cleaned


def normalize_ssh_host(ssh_host):
    """整理 SSH 主机：别名或 `[user@]host[:port]`，不允许空白与 shell 元字符。"""
    cleaned = str(ssh_host or "").strip()
    if not cleaned:
        raise DomainError("SSH 主机不能为空")
    if not SSH_HOST_PATTERN.match(cleaned):
        raise DomainError(
            f"SSH 主机写法不合法：{cleaned}；请用 ~/.ssh/config 里的别名，或 user@host 形式"
        )
    return cleaned


def normalize_workspace(remote_workspace):
    """整理远端工作目录：必须是绝对路径。"""
    cleaned = str(remote_workspace or "").strip() or DEFAULT_REMOTE_WORKSPACE
    if not cleaned.startswith("/"):
        raise RemoteWorkspaceNotAbsolute(f"远端工作目录必须是绝对路径：{cleaned}")
    return cleaned.rstrip("/") or "/"


def normalize_device(device):
    """整理远端 GPU 序号：`0` 或 `0,1` 这种 Ultralytics 写法。"""
    cleaned = str(device or "").strip() or DEFAULT_DEVICE
    if not DEVICE_PATTERN.match(cleaned):
        raise DomainError(f"GPU 序号写法不合法：{cleaned}；用 0 或 0,1 这种形式")
    return cleaned


def normalize_target_fields(
    *,
    name=None,
    ssh_host=None,
    remote_workspace=None,
    device=None,
    keep_remote_copy=None,
):
    """把用户提交的一组字段整理成可直接落库的字典，只带提交过的键。"""
    patch = {}
    if name is not None:
        patch["name"] = normalize_name(name)
    if ssh_host is not None:
        patch["ssh_host"] = normalize_ssh_host(ssh_host)
    if remote_workspace is not None:
        patch["remote_workspace"] = normalize_workspace(remote_workspace)
    if device is not None:
        patch["device"] = normalize_device(device)
    if keep_remote_copy is not None:
        patch["keep_remote_copy"] = bool(parse_bool(keep_remote_copy, default=False))
    return patch
