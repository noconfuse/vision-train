"""用 ssh / rsync 操作远端 GPU 服务器。

本机这一侧一律用 argv 列表起进程，不经过本机 shell；交给远端的命令由 `shlex.quote`
逐词拼接后作为 ssh 的单个参数，由远端 shell 解析。所有对外函数都建立在 `run` 和
`popen` 两个原语上，测试只打桩这两个，不碰网络。
"""

import posixpath
import shlex
import subprocess

from contexts.compute.domain.errors import RemoteExecutionError

SSH_BASE_OPTIONS = (
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=20",
    "-o", "ServerAliveInterval=20",
    "-o", "ServerAliveCountMax=4",
    "-o", "StrictHostKeyChecking=accept-new",
)
RSYNC_TRANSPORT = "ssh " + " ".join(SSH_BASE_OPTIONS)
# rsync 每传一个条目打印一行路径，用它换算同步进度；新版 rsync 打在 stderr、
# openrsync 打在 stdout，所以两边合并成一个流读。
RSYNC_OUT_FORMAT = "%n"
DEFAULT_TIMEOUT_SECONDS = 60


def run(argv, *, timeout=None, input_text=None):
    """执行一条本机命令并返回 CompletedProcess（测试打桩点）。"""
    return subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=timeout,
    )


def popen(argv):
    """起一条本机命令并把标准输出（含标准错误）接成可逐行读的管道（测试打桩点）。"""
    return subprocess.Popen(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def remote_command_text(remote_argv):
    """把远端命令逐词加引号拼成一条 shell 字符串。"""
    return " ".join(shlex.quote(str(token)) for token in remote_argv)


def build_ssh_argv(host, remote_argv):
    """构造一条 `ssh host cmd...` 的本机命令行。"""
    return ["ssh", *SSH_BASE_OPTIONS, str(host), remote_command_text(remote_argv)]


def build_rsync_to_argv(host, local_dir, remote_dir):
    """构造把本地目录内容推到远端目录的 rsync 命令行。"""
    return [
        "rsync", "-a",
        "--out-format", RSYNC_OUT_FORMAT,
        "-e", RSYNC_TRANSPORT,
        f"{str(local_dir).rstrip('/')}/",
        f"{host}:{remote_dir.rstrip('/')}/",
    ]


def build_rsync_from_argv(host, remote_dir, local_dir):
    """构造把远端目录内容拉回本地目录的 rsync 命令行。"""
    return [
        "rsync", "-a",
        "--out-format", RSYNC_OUT_FORMAT,
        "-e", RSYNC_TRANSPORT,
        f"{host}:{remote_dir.rstrip('/')}/",
        f"{str(local_dir).rstrip('/')}/",
    ]


def build_rsync_file_to_argv(host, local_file, remote_dir):
    """构造把单个本地文件推到远端目录的 rsync 命令行。"""
    return [
        "rsync", "-a",
        "--out-format", RSYNC_OUT_FORMAT,
        "-e", RSYNC_TRANSPORT,
        str(local_file),
        f"{host}:{remote_dir.rstrip('/')}/",
    ]


def build_detached_script(remote_argv, cwd, log_path):
    """构造「脱离 ssh 会话后台运行并把输出写日志」的远端脚本，脚本回显进程号。"""
    command = remote_command_text(remote_argv)
    return f"cd {shlex.quote(str(cwd))} && nohup {command} > {shlex.quote(str(log_path))} 2>&1 & echo $!"


def remote_run(target, remote_argv, *, timeout=DEFAULT_TIMEOUT_SECONDS):
    """在远端执行一条命令，返回 (退出码, 标准输出, 标准错误)。"""
    completed = run(build_ssh_argv(target["ssh_host"], remote_argv), timeout=timeout)
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def remote_check(target, remote_argv, *, action, timeout=DEFAULT_TIMEOUT_SECONDS):
    """在远端执行一条命令，失败就把服务器原始报错原样抛出。"""
    returncode, stdout, stderr = remote_run(target, remote_argv, timeout=timeout)
    if returncode != 0:
        detail = (stderr.strip() or stdout.strip() or "远端没有任何输出")
        raise RemoteExecutionError(
            f"{action}：{target['ssh_host']} 上退出码 {returncode}\n{detail}"
        )
    return stdout


def remote_mkdir(target, path):
    """在远端建目录（含父级）。"""
    return remote_check(target, ["mkdir", "-p", path], action=f"创建远端目录 {path}")


def remote_write_text(target, path, text, *, timeout=DEFAULT_TIMEOUT_SECONDS):
    """把一段文本写到远端文件（父目录自动建好）。"""
    parent = posixpath.dirname(path)
    script = f"mkdir -p {shlex.quote(parent)} && cat > {shlex.quote(path)}"
    completed = run(build_ssh_argv(target["ssh_host"], ["sh", "-c", script]), input_text=text, timeout=timeout)
    if completed.returncode != 0:
        raise RemoteExecutionError(
            f"写入远端文件 {path} 失败：退出码 {completed.returncode}\n"
            f"{(completed.stderr or completed.stdout or '').strip() or '远端没有任何输出'}"
        )


def remote_touch(target, path):
    """在远端留下一个信号文件。"""
    return remote_check(target, ["touch", path], action=f"写入远端信号文件 {path}")


def remote_remove(target, path):
    """删除远端目录或文件（只用于本次运行自己建的目录）。"""
    return remote_check(target, ["rm", "-rf", path], action=f"清理远端 {path}")


def remote_pid_alive(target, pid):
    """判断远端进程是否还活着。"""
    returncode, _, _ = remote_run(target, ["kill", "-0", str(pid)])
    return returncode == 0


def remote_kill(target, pid, *, force=False):
    """向远端进程发停止信号；force 时升级为强杀。"""
    signal_name = "KILL" if force else "TERM"
    return remote_check(target, ["kill", f"-{signal_name}", str(pid)], action=f"终止远端进程 {pid}")


def remote_start_detached(target, remote_argv, *, cwd, log_path):
    """在远端后台启动一条命令，返回它的进程号。"""
    stdout = remote_check(
        target,
        ["sh", "-c", build_detached_script(remote_argv, cwd, log_path)],
        action="启动远端训练进程",
        timeout=120,
    )
    pid_text = stdout.strip().splitlines()[-1] if stdout.strip() else ""
    try:
        return int(pid_text)
    except ValueError:
        raise RemoteExecutionError(
            f"启动远端训练进程后拿不到进程号，{target['ssh_host']} 返回：{stdout.strip() or '空'}"
        )


def remote_tail(target, log_path, *, from_line=1):
    """从远端日志的第 from_line 行开始跟随输出，返回逐行可读的管道。"""
    return popen(build_ssh_argv(target["ssh_host"], ["tail", "-n", f"+{int(from_line)}", "-F", str(log_path)]))


def sync_to_remote(target, local_dir, remote_dir, *, on_entry=None, timeout=1800):
    """rsync 推送本地目录内容到远端，返回实际传输的条目数。"""
    remote_mkdir(target, remote_dir)
    return _sync_lines(build_rsync_to_argv(target["ssh_host"], local_dir, remote_dir), on_entry, timeout, "推送数据集")


def sync_from_remote(target, remote_dir, local_dir, *, timeout=1800):
    """rsync 拉回远端目录内容到本地，返回实际传输的条目数。"""
    return _sync_lines(build_rsync_from_argv(target["ssh_host"], remote_dir, local_dir), None, timeout, "回传训练产物")


def copy_file_to_remote(target, local_file, remote_dir, *, timeout=600):
    """rsync 推送单个本地文件到远端目录（权重文件用）。"""
    remote_mkdir(target, remote_dir)
    return _sync_lines(build_rsync_file_to_argv(target["ssh_host"], local_file, remote_dir), None, timeout, "推送权重文件")


def _sync_lines(argv, on_entry, timeout, action):
    """跑一条 rsync 并按行回报进度；rsync 自己非零退出就带原始输出抛出。"""
    proc = popen(argv)
    transferred = 0
    collected = []
    for line in proc.stdout or []:
        collected.append(line.rstrip("\n"))
        entry = line.strip()
        # 目录行以 / 结尾，不计入条目数：进度按「传了多少个文件」算才有意义
        if entry and not entry.endswith("/"):
            transferred += 1
            if on_entry:
                on_entry(transferred)
    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RemoteExecutionError(f"{action} 超时（{timeout} 秒）")
    if returncode != 0:
        raise RemoteExecutionError(
            f"{action} 失败：退出码 {returncode}\n" + "\n".join(collected[-20:])
        )
    return transferred
