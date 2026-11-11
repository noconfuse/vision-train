"""在远端 GPU 服务器上独立跑一次 Ultralytics 训练的脚本。

这个文件会被上传到服务器、由服务器上的 python 直接执行，因此它不 import 本产品的任何
模块，只依赖 torch 和 ultralytics。它唯一的对外契约是 stdout 上的「一行一个 JSON 事件」：

    {"evt": "start",   "pid": 1234, "python": "3.11.9", "ultralytics": "8.3.0"}
    {"evt": "batch",   "ni": 30, "total": 3000}
    {"evt": "epoch",   "epoch": 1, "of": 50, "losses": [1.2, 2.3, 0.4], "metrics": {"metrics/mAP50(B)": 0.31}}
    {"evt": "done"}
    {"evt": "stopped"}
    {"evt": "error",   "error": "...", "traceback": "..."}

本地监督进程读这些行写进度和曲线；Ultralytics 自己打印的普通文本行原样留在日志里。
"""

import argparse
import json
import math
import os
import sys
import time
import traceback

STOP_FILENAME = ".stop-request"
BATCH_EVENT_MIN_INTERVAL_SECONDS = 15.0


def emit(payload):
    """输出一条事件；非 JSON 行也允许，本地按行分流处理。"""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def error_event(exc, tb_text=None):
    """把异常整理成一条能直接读的错误事件。"""
    text = tb_text if tb_text is not None else traceback.format_exc()
    return {"evt": "error", "error": str(exc), "traceback": text[-4000:]}


def to_float_list(value):
    """把 loss_items 这类张量/序列转成 float 列表，转不动就返回空列表。"""
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (int, float)):
        return [float(value)]
    result = []
    for item in value if isinstance(value, (list, tuple)) else []:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            return []
    return result


def to_float_dict(value):
    """把 trainer.metrics 转成纯 float 字典，非数值的键直接丢掉。"""
    if not isinstance(value, dict):
        return {}
    out = {}
    for key, raw in value.items():
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isnan(number) or math.isinf(number):
            continue
        out[str(key)] = number
    return out


def read_job(job_path):
    """读取本地监督进程写好的任务描述。"""
    with open(job_path, "r", encoding="utf-8") as handle:
        job = json.load(handle)
    for key in ("data", "weights", "project", "name", "device"):
        if not job.get(key):
            raise ValueError(f"任务描述缺少字段 {key}")
    return job


def stop_requested(save_dir):
    """训练目录里出现停止信号文件就代表用户点了停止。"""
    return bool(save_dir) and os.path.exists(os.path.join(save_dir, STOP_FILENAME))


def build_callbacks(state, save_dir):
    """构造写事件用的 Ultralytics 回调。"""

    def on_train_batch_end(trainer):
        now = time.time()
        if now - state["last_batch_emit"] < BATCH_EVENT_MIN_INTERVAL_SECONDS:
            return
        state["last_batch_emit"] = now
        if stop_requested(save_dir):
            raise InterruptedError("收到停止请求")
        try:
            total = len(trainer.train_loader) * max(int(trainer.epochs), 1)
        except Exception:
            total = 0
        emit({"evt": "batch", "ni": int(getattr(trainer, "ni", 0) or 0), "total": int(total)})

    def on_train_epoch_end(trainer):
        if stop_requested(save_dir):
            raise InterruptedError("收到停止请求")
        emit(
            {
                "evt": "epoch",
                "epoch": int(trainer.epoch) + 1,
                "of": int(trainer.epochs),
                "losses": to_float_list(getattr(trainer, "loss_items", None)),
                "metrics": to_float_dict(getattr(trainer, "metrics", None)),
            }
        )

    return on_train_batch_end, on_train_epoch_end


def main():
    """跑一次远端训练，把过程逐事件打到标准输出。"""
    parser = argparse.ArgumentParser(description="vision-train 远端训练入口")
    parser.add_argument("--job", required=True, help="任务描述 JSON 的路径")
    args = parser.parse_args()

    try:
        job = read_job(args.job)
    except Exception as exc:
        emit(error_event(exc))
        return 1

    import ultralytics
    from ultralytics import YOLO

    save_dir = os.path.join(job["project"], job["name"])
    emit({"evt": "start", "pid": os.getpid(), "python": sys.version.split()[0], "ultralytics": getattr(ultralytics, "__version__", "")})

    train_args = dict(job.get("args") or {})
    train_args.update(
        {
            "data": job["data"],
            "device": job["device"],
            "project": job["project"],
            "name": job["name"],
            "exist_ok": True,
            "save": True,
        }
    )
    state = {"last_batch_emit": 0.0}
    on_train_batch_end, on_train_epoch_end = build_callbacks(state, save_dir)
    try:
        model = YOLO(job["weights"])
        model.add_callback("on_train_batch_end", on_train_batch_end)
        model.add_callback("on_train_epoch_end", on_train_epoch_end)
        model.train(**train_args)
    except InterruptedError:
        emit({"evt": "stopped"})
        return 0
    except BaseException as exc:  # KeyboardInterrupt / SystemExit 也要留下可读的一行
        emit(error_event(exc))
        return 1

    emit({"evt": "done"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
