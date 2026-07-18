"""按模块协议启动 worker 并管理子进程探活。"""

import os
import signal
import subprocess
import sys
import time


def spawn_worker_process(task_id, log_path, module_name):
    """按模块名启动独立 worker 进程并把输出重定向到日志文件。"""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "ab") as log_file:
        proc = subprocess.Popen(
            [sys.executable, "-m", module_name, task_id],
            cwd=os.getcwd(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
            env=os.environ.copy(),
        )
    return proc, module_name


def is_process_alive(pid):
    """用轻量探测判断进程是否仍在运行。"""
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError, TypeError):
        return False


def get_process_command(pid):
    """读取指定进程的命令行字符串。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return ""

    proc_cmdline = f"/proc/{pid}/cmdline"
    if os.path.isfile(proc_cmdline):
        try:
            with open(proc_cmdline, "rb") as handle:
                return handle.read().decode("utf-8", errors="replace").replace("\x00", " ").strip()
        except OSError:
            return ""

    try:
        result = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def terminate_process_group(pid, *, wait_seconds=5.0):
    """优先终止 worker 进程组，必要时升级为强杀。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if not is_process_alive(pid):
        return False
    try:
        target_pgid = os.getpgid(pid)
    except OSError:
        target_pgid = None

    def _send(sig):
        try:
            if target_pgid is not None:
                os.killpg(target_pgid, sig)
            else:
                os.kill(pid, sig)
            return True
        except ProcessLookupError:
            return False
        except OSError:
            return False

    _send(signal.SIGTERM)
    deadline = time.time() + max(0.0, float(wait_seconds or 0))
    while time.time() < deadline:
        if not is_process_alive(pid):
            return True
        time.sleep(0.1)
    if not is_process_alive(pid):
        return True
    _send(signal.SIGKILL)
    for _ in range(10):
        if not is_process_alive(pid):
            return True
        time.sleep(0.1)
    return not is_process_alive(pid)
