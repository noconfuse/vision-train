#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def log(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def which(cmd: str) -> str | None:
    return shutil.which(cmd)

def parse_remote_spec(remote: str) -> tuple[str | None, str]:
    remote = remote.strip()
    if not remote:
        raise ValueError("remote 不能为空")
    if "@" in remote:
        user, host = remote.split("@", 1)
        user = user.strip() or None
        host = host.strip()
        if not host:
            raise ValueError("remote host 不能为空")
        return user, host
    return None, remote

def parse_remote_path_and_override_remote(remote: str, remote_file: str) -> tuple[str, str, str]:
    remote_user, remote_host = parse_remote_spec(remote)
    user = remote_user or "ubuntu"
    host = remote_host

    remote_file = remote_file.strip()
    if not remote_file:
        raise ValueError("remote-file 不能为空")

    if ":" in remote_file and not remote_file.startswith("/"):
        left, path = remote_file.split(":", 1)
        if path.startswith("/"):
            override_user, override_host = parse_remote_spec(left)
            if override_user:
                user = override_user
            host = override_host
            return user, host, path

    return user, host, remote_file


def build_command(
    tool: str,
    host: str,
    user: str,
    port: int,
    identity_file: str | None,
    remote_path: str,
    dest_file: Path,
) -> list[str]:
    host_spec = f"{user}@{host}"

    if tool == "rsync":
        ssh_parts: list[str] = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]
        if port and port != 22:
            ssh_parts.extend(["-p", str(port)])
        if identity_file:
            ssh_parts.extend(["-i", identity_file])
        ssh_cmd = " ".join(ssh_parts)
        return [
            "rsync",
            "-avP",
            "--partial",
            "--inplace",
            "-e",
            ssh_cmd,
            f"{host_spec}:{remote_path}",
            str(dest_file),
        ]
    if tool == "scp":
        cmd: list[str] = [
            "scp",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-p",
        ]
        if port and port != 22:
            cmd.extend(["-P", str(port)])
        if identity_file:
            cmd.extend(["-i", identity_file])
        cmd.extend([f"{host_spec}:{remote_path}", str(dest_file)])
        return cmd
    if tool == "sftp":
        cmd = [
            "sftp",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        if port and port != 22:
            cmd.extend(["-P", str(port)])
        if identity_file:
            cmd.extend(["-i", identity_file])
        cmd.append(host_spec)
        return cmd

    raise ValueError(f"Unsupported tool: {tool}")


def run_with_password_if_available(command: list[str], password: str | None) -> int:
    if password and which("sshpass"):
        command = ["sshpass", "-p", password, *command]
    proc = subprocess.run(command)
    return int(proc.returncode)


def run_sftp_get(
    host: str,
    user: str,
    port: int,
    identity_file: str | None,
    remote_path: str,
    dest_file: Path,
    password: str | None,
) -> int:
    host_spec = f"{user}@{host}"
    command = ["sftp", "-o", "StrictHostKeyChecking=accept-new"]
    if port and port != 22:
        command.extend(["-P", str(port)])
    if identity_file:
        command.extend(["-i", identity_file])
    command.append(host_spec)
    if password and which("sshpass"):
        command = ["sshpass", "-p", password, *command]

    script = f'get -p "{remote_path}" "{str(dest_file)}"\nbye\n'
    proc = subprocess.run(command, input=script.encode("utf-8"))
    return int(proc.returncode)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    default_dest_dir = project_root / "projects"

    parser = argparse.ArgumentParser(description="从远程服务器下载 layer3_behavior_detection.zip 到本地 projects 目录")
    parser.add_argument(
        "--remote",
        default="ubuntu@117.50.91.40",
        help="形如 ubuntu@117.50.91.40",
    )
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--identity-file", default="")
    parser.add_argument(
        "--remote-file",
        default="/home/ubuntu/workspace/vision-train/projects/layer3_behavior_detection.zip",
        help='远程文件路径，支持 "/abs/path/file.zip" 或 "ubuntu@host:/abs/path/file.zip"',
    )
    parser.add_argument("--dest-dir", default=str(default_dest_dir))
    parser.add_argument(
        "--password",
        default="",
        help="SSH 密码（可选；建议用环境变量 VISION_TRAIN_SSH_PASS）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dest_dir = Path(args.dest_dir).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    identity_file = str(args.identity_file).strip() or None
    user, host, remote_path = parse_remote_path_and_override_remote(str(args.remote), str(args.remote_file))
    dest_file = dest_dir / Path(remote_path).name

    password = str(args.password).strip() or os.getenv("VISION_TRAIN_SSH_PASS") or None

    log(f"开始下载: {user}@{host}:{remote_path}")
    log(f"保存到: {dest_file}")
    if password:
        if which("sshpass"):
            log("检测到密码，将使用 sshpass")
        else:
            log("检测到密码，但未找到 sshpass，将尝试交互式登录")

    for tool in ("rsync", "scp"):
        if which(tool):
            log(f"使用 {tool} 下载（会显示进度输出）")
            cmd = build_command(tool, host, user, args.port, identity_file, remote_path, dest_file)
            return run_with_password_if_available(cmd, password)

    if which("sftp"):
        log("使用 sftp 下载（会显示进度输出）")
        return run_sftp_get(host, user, args.port, identity_file, remote_path, dest_file, password)

    log("错误: 未找到 rsync/scp/sftp 任一命令")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
