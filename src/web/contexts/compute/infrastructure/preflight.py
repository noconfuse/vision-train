"""远端 GPU 服务器预检：一次跑完所有能跑的检查，把问题一次列全。

预检不通过时训练启动会硬失败并把原因原样带到界面上；这里绝不「退回本机继续跑」。
"""

import json

from contexts.compute.domain.errors import RemoteExecutionError
from contexts.compute.infrastructure import remote_shell

PROBE_SCRIPT = r"""
import json, sys
result = {"python": sys.version.split()[0], "python_executable": sys.executable}
try:
    import torch
    result["torch"] = torch.__version__
    result["cuda_available"] = bool(torch.cuda.is_available())
    result["gpu_names"] = [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())]
except Exception as exc:
    result["torch_error"] = repr(exc)
try:
    import ultralytics
    result["ultralytics"] = getattr(ultralytics, "__version__", "")
except Exception as exc:
    result["ultralytics_error"] = repr(exc)
print(json.dumps(result))
"""

MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024


def _parse_df_available(text):
    """从 `df -Pk` 输出里取可用 KB 数，取不到返回 0。"""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return 0
    fields = lines[1].split()
    if len(fields) < 4:
        return 0
    try:
        return int(fields[3]) * 1024
    except ValueError:
        return 0


def run_preflight(target):
    """检查一台 GPU 服务器能不能直接开始训练，返回逐项结果。"""
    host = target["ssh_host"]
    workspace = target["remote_workspace"]
    report = {
        "target_id": target["id"],
        "name": target["name"],
        "host": host,
        "device": target["device"],
        "workspace": workspace,
        "reachable": False,
        "workspace_writable": False,
        "free_bytes": 0,
        "python": "",
        "torch": "",
        "ultralytics": "",
        "cuda_available": False,
        "gpu_names": [],
        "problems": [],
    }

    try:
        remote_shell.remote_check(target, ["true"], action="连接服务器", timeout=30)
        report["reachable"] = True
    except (RemoteExecutionError, OSError) as exc:
        report["problems"].append(f"SSH 连不上：{exc}")
        # 连不上就没有后面可言：后面的检查全都会以同一个原因失败
        report["ok"] = False
        return report

    try:
        remote_shell.remote_check(target, ["mkdir", "-p", workspace], action=f"准备远端目录 {workspace}", timeout=30)
        probe_path = f"{workspace.rstrip('/')}/.vision-train-probe"
        remote_shell.remote_check(target, ["touch", probe_path], action=f"检查 {workspace} 可写", timeout=30)
        remote_shell.remote_run(target, ["rm", "-f", probe_path])
        report["workspace_writable"] = True
    except (RemoteExecutionError, OSError) as exc:
        report["problems"].append(f"远端工作目录不可用：{exc}")

    try:
        df_text = remote_shell.remote_check(target, ["df", "-Pk", workspace], action="读取剩余空间", timeout=30)
        report["free_bytes"] = _parse_df_available(df_text)
        if report["free_bytes"] and report["free_bytes"] < MIN_FREE_BYTES:
            report["problems"].append(
                f"{workspace} 只剩 {report['free_bytes'] // (1024 * 1024)} MB，不足以放下数据集（建议至少 2 GB）"
            )
    except (RemoteExecutionError, OSError) as exc:
        report["problems"].append(f"读不到剩余空间：{exc}")

    try:
        probe_text = remote_shell.remote_check(target, ["python3", "-c", PROBE_SCRIPT], action="探测远端训练环境", timeout=120)
    except (RemoteExecutionError, OSError) as exc:
        report["problems"].append(f"远端跑不了 python3：{exc}")
        probe_text = ""
    if probe_text:
        payload = _read_probe_json(probe_text)
        if payload is None:
            report["problems"].append(f"远端环境探测输出无法解析：{probe_text.strip()[:400]}")
        else:
            report["python"] = payload.get("python") or ""
            report["torch"] = payload.get("torch") or ""
            report["ultralytics"] = payload.get("ultralytics") or ""
            report["cuda_available"] = bool(payload.get("cuda_available"))
            report["gpu_names"] = list(payload.get("gpu_names") or [])
            if payload.get("torch_error"):
                report["problems"].append(f"远端 import torch 失败：{payload['torch_error']}")
            if payload.get("ultralytics_error"):
                report["problems"].append(f"远端 import ultralytics 失败：{payload['ultralytics_error']}")
            elif not report["ultralytics"]:
                report["problems"].append("远端 ultralytics 没有版本号，无法确认训练框架可用")
            if not report["cuda_available"]:
                report["problems"].append("远端 torch.cuda.is_available() 为 False，这台机器现在用不了 GPU")

    report["ok"] = not report["problems"]
    return report


def require_preflight_passed(target):
    """训练启动前的硬门：预检不过就把全部问题抛出去。"""
    report = run_preflight(target)
    if report["ok"]:
        return report
    raise RemoteExecutionError(
        f"{report['name']}（{report['host']}）预检未通过：\n" + "\n".join(f"- {item}" for item in report["problems"])
    )


def _read_probe_json(text):
    """从探测输出里取最后一行 JSON，前置的告警文本不参与判断。"""
    for line in reversed([item for item in (text or "").splitlines() if item.strip()]):
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
