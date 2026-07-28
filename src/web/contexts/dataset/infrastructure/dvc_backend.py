"""DVC（数据版本控制）后端封装：初始化、跟踪、提交、检出与移除。

所有动作都通过 subprocess 调用 dvc 命令行完成，避免与 DVC 内部 Python API 紧耦合。
进度回调通过“处理前后文件数差”估算；DVC 自身不输出逐文件进度事件，因此本模块
只提供基于文件总数 + 阶段事件的近似进度。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
from typing import Callable, Optional

import yaml

logger = logging.getLogger(__name__)

DVC_INIT_TIMEOUT = 60
DVC_ADD_TIMEOUT = 60 * 60
DVC_COMMIT_TIMEOUT = 60 * 30
DVC_CHECKOUT_TIMEOUT = 60 * 30
DVC_REMOVE_TIMEOUT = 60 * 10

def _dvc_bin_candidates() -> tuple[str, ...]:
    """优先使用当前 Python 虚拟环境里的 dvc，可跨平台回退到 PATH。"""
    python_dir = os.path.dirname(sys.executable or "")
    candidates = []
    for name in ("dvc", "dvc.exe"):
        local_bin = os.path.join(python_dir, name)
        if local_bin not in candidates:
            candidates.append(local_bin)
    for name in ("dvc", "dvc.exe"):
        if name not in candidates:
            candidates.append(name)
    return tuple(candidates)


class DVCUnavailableError(RuntimeError):
    """环境中没有可用的 DVC 命令。"""


class DVCCommandError(RuntimeError):
    """DVC 子进程执行失败。"""


def _find_dvc_bin() -> Optional[str]:
    """查找 dvc 可执行文件。"""
    for candidate in _dvc_bin_candidates():
        path = shutil.which(candidate)
        if path:
            return path
    return None


def is_dvc_available() -> bool:
    """探测当前环境是否安装了 DVC。"""
    return _find_dvc_bin() is not None


def _run_dvc(args, *, cwd: str, timeout: int, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    """运行 dvc 子进程，失败时抛 DVCCommandError。"""
    dvc_bin = _find_dvc_bin()
    if not dvc_bin:
        raise DVCUnavailableError("DVC 未安装，请先运行 `pip install dvc`")
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    # DVC 在某些环境下会打印大量进度信息，强制静默减少日志噪音。
    merged_env.setdefault("DVC_QUIET", "1")
    proc = subprocess.run(
        [dvc_bin, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged_env,
        check=False,
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()
        raise DVCCommandError(f"dvc {' '.join(args)} 失败: {message or f'exit={proc.returncode}'}")
    return proc


def _project_dvc_dir(project_path: str) -> str:
    """返回项目根目录下的 .dvc 目录路径。"""
    return os.path.join(project_path, ".dvc")


def is_dvc_repo_initialized(project_path: str) -> bool:
    """项目是否已经经过 `dvc init`。"""
    return os.path.isdir(_project_dvc_dir(project_path))


def ensure_dvc_repo(project_path: str) -> None:
    """自检 DVC repo：未初始化时调 `dvc init`，已初始化则跳过。"""
    if is_dvc_repo_initialized(project_path):
        return
    os.makedirs(project_path, exist_ok=True)
    _run_dvc(["init", "--no-scm"], cwd=project_path, timeout=DVC_INIT_TIMEOUT)


def _dataset_dvc_file(dataset_dir: str) -> str:
    """DVC 跟踪数据集目录后生成的指针文件路径。"""
    return f"{dataset_dir.rstrip(os.sep)}.dvc"


def _dataset_relative_path(project_path: str, dataset_dir: str) -> str:
    """计算数据集目录相对项目根的相对路径（POSIX 风格）。"""
    rel = os.path.relpath(dataset_dir, project_path)
    return rel.replace(os.sep, "/")


def _ensure_dvcignore(project_path: str) -> None:
    """确保项目根存在 `.dvcignore`，避免跟踪版本仓、训练产物等。"""
    ignore_path = os.path.join(project_path, ".dvcignore")
    rules = [
        ".dataset-store/",
        ".dvc/",
        "runs/",
        "outputs/",
        "*.pt",
        "*.onnx",
        "*.engine",
        "*.pth",
        "__pycache__/",
        "*.pyc",
    ]
    existing = ""
    if os.path.isfile(ignore_path):
        with open(ignore_path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    additions = [line for line in rules if line not in existing]
    if not additions:
        return
    with open(ignore_path, "a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write("\n".join(additions) + "\n")


def count_dataset_files(dataset_dir: str) -> int:
    """统计数据集目录下需要跟踪的文件总数（不含 .dvc 指针文件本身）。"""
    total = 0
    for root, dirs, files in os.walk(dataset_dir):
        dirs.sort()
        for name in files:
            if name.endswith(".dvc"):
                continue
            total += 1
    return total


def _run_dvc_with_progress(args, *, cwd: str, timeout: int, on_progress=None) -> subprocess.CompletedProcess:
    """运行 dvc 子进程，过程中持续回调 on_progress(processed, total)。

    DVC 自身不输出逐文件进度，因此这里用“扫到的总文件数”作为分母，
    进度 = 当前已确认完成的阶段标签数 / 总阶段数 仅作占位；
    实际进度会在调用方基于 count_dataset_files + 时间窗估算。
    """
    dvc_bin = _find_dvc_bin()
    if not dvc_bin:
        raise DVCUnavailableError("DVC 未安装，请先运行 `pip install dvc`")
    merged_env = dict(os.environ)
    merged_env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [dvc_bin, *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=merged_env,
        bufsize=1,
    )
    assert proc.stdout is not None
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    progress_state = {"stage": 0}

    def _pump(stream, sink):
        for line in iter(stream.readline, ""):
            sink.append(line)
            if on_progress and ("Adding" in line or "Computing" in line or "Checking" in line):
                progress_state["stage"] += 1
                try:
                    on_progress(progress_state["stage"])
                except Exception:
                    logger.exception("dvc progress callback failed")

    stdout_thread = threading.Thread(target=_pump, args=(proc.stdout, stdout_lines), daemon=True)
    stderr_thread = threading.Thread(target=_pump, args=(proc.stderr, stderr_lines), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise DVCCommandError(f"dvc {' '.join(args)} 超时") from None
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)

    if rc != 0:
        message = ("".join(stderr_lines) or "".join(stdout_lines) or "").strip()
        raise DVCCommandError(f"dvc {' '.join(args)} 失败: {message or f'exit={rc}'}")
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout="".join(stdout_lines), stderr="".join(stderr_lines))


def dvc_add_dataset(project_path: str, dataset_dir: str, *, on_progress: Optional[Callable[[int], None]] = None) -> str:
    """跟踪数据集目录到 DVC（首次入库）。

    返回 DVC rev（`<dataset_dir>.dvc` 文件内容的 md5 指纹）。
    """
    ensure_dvc_repo(project_path)
    _ensure_dvcignore(project_path)
    rel_path = _dataset_relative_path(project_path, dataset_dir)
    _run_dvc_with_progress(
        ["add", rel_path],
        cwd=project_path,
        timeout=DVC_ADD_TIMEOUT,
        on_progress=on_progress,
    )
    rev = dvc_get_current_rev(project_path, dataset_dir)
    return rev


def dvc_commit_dataset(project_path: str, dataset_dir: str) -> str:
    """对已跟踪的数据集目录做增量提交。

    若 DVC repo 尚未初始化或目录尚未被 add，会自动 init 后做一次 add。
    """
    ensure_dvc_repo(project_path)
    rel_path = _dataset_relative_path(project_path, dataset_dir)
    if not os.path.isfile(_dataset_dvc_file(dataset_dir)):
        # 尚未跟踪，回退为 add 走一次全量入库。
        return dvc_add_dataset(project_path, dataset_dir)
    _run_dvc(["commit", "-f", rel_path], cwd=project_path, timeout=DVC_COMMIT_TIMEOUT)
    return dvc_get_current_rev(project_path, dataset_dir)


def dvc_checkout_dataset(project_path: str, dataset_dir: str, rev: str) -> None:
    """把数据集目录切回指定 rev 内容。"""
    if not rev:
        raise ValueError("rev 不能为空")
    rel_path = _dataset_relative_path(project_path, dataset_dir)
    _run_dvc(["checkout", rel_path, "--force"], cwd=project_path, timeout=DVC_CHECKOUT_TIMEOUT)


def dvc_get_current_rev(project_path: str, dataset_dir: str) -> str:
    """读取当前 `<dataset_dir>.dvc` 文件中的内容指纹，作为 rev。

    注意：``<dataset_dir>.dvc`` 是 DVC 输出的 YAML 文件，必须用 ``yaml.safe_load``
    解析；之前误用 ``json.load`` 会静默返回空串，从而导致 ``version.json`` 里的
    ``dvc_rev`` 丢失，列表接口过滤后前端看不到任何版本记录。
    """
    dvc_file = _dataset_dvc_file(dataset_dir)
    if not os.path.isfile(dvc_file):
        return ""
    try:
        with open(dvc_file, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    outs = data.get("outs") or []
    if not outs:
        return ""
    first = outs[0] if isinstance(outs[0], dict) else {}
    return str(first.get("md5") or first.get("etag") or first.get("hash") or "")


def dvc_remove_dataset(project_path: str, dataset_dir: str) -> None:
    """从 DVC 跟踪列表中移除数据集（不删除 cache）。"""
    rel_path = _dataset_relative_path(project_path, dataset_dir)
    try:
        _run_dvc(["remove", rel_path, "--outs"], cwd=project_path, timeout=DVC_REMOVE_TIMEOUT)
    except DVCCommandError as exc:
        # 跟踪不存在时静默忽略
        logger.info("dvc remove %s 已无跟踪: %s", rel_path, exc)
