"""远端 GPU 训练的本地监督进程。

本机负责全部记账：数据同步、启动远端训练、跟随日志并把事件写回本地任务与曲线、
按停止信号收口、回传产物、清理远端临时目录。远端只当一个会算的显卡，不装本产品。
"""

import json
import os
import posixpath
import queue
import threading
import time
import traceback

import yaml

from protocols.task_artifact_keys import (
    ARTIFACT_OUTPUT_DIR,
    ARTIFACT_REMOTE_DATA_DIR,
    ARTIFACT_REMOTE_HOST,
    ARTIFACT_REMOTE_LOG_PATH,
    ARTIFACT_REMOTE_PID,
    ARTIFACT_REMOTE_RUN_DIR,
    ARTIFACT_STOP_SIGNAL_PATH,
)
from protocols.task_status import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_RUNNING, TASK_STATUS_STOPPED
from protocols.task_type import TASK_TYPE_TRAINING
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY
from contexts.compute.application import compute_service
from contexts.compute.application.compute_service import RemoteExecutionError
from contexts.task.application.task_service import (
    append_task_history as write_task_history,
    finish_worker_task,
    is_stop_requested,
    load_task,
    mark_worker_exited,
    mark_worker_started,
    merge_task_artifacts,
    update_task as update_task_status,
    update_worker_task_progress,
)
from contexts.training.infrastructure.execution_context import resolve_task_training_runtime_context
from contexts.training.infrastructure.execution_support import build_training_args
from contexts.training.infrastructure.training_artifacts import build_training_weight_artifacts
from contexts.training.infrastructure.training_runtime_adapter import resolve_training_runtime_adapter
from shared.utils.path_utils import resolve_storage_path
from shared.utils.time_utils import now_iso

REMOTE_PYTHON = "python3"
DATASET_DIR_NAME = "dataset"
MODEL_DIR_NAME = "model"
OUTPUTS_DIR_NAME = "outputs"
RUN_NAME = "run"
ENTRY_FILENAME = "remote_train_entry.py"
JOB_FILENAME = "job.json"
LOG_FILENAME = "train.log"
STOP_FILENAME = ".stop-request"
REMOTE_DATASET_YAML_NAME = "dataset.remote.yaml"

SYNC_PROGRESS_CEILING = 10
TRAIN_PROGRESS_FLOOR = 10
TRAIN_PROGRESS_CEILING = 95
TAIL_RETRY_LIMIT = 10
TAIL_RETRY_SLEEP_SECONDS = 3.0
REMOTE_STOP_GRACE_SECONDS = 60.0
REMOTE_KILL_GRACE_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 1.0
REMOTE_LOG_TAIL_BYTES = 4000

# 要上传给远端执行的脚本在本仓库里的位置；远端服务器上不需要装本产品，所以按文件内容传过去。
ENTRY_SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "compute", "infrastructure", ENTRY_FILENAME)
)
_SPLIT_KEYS = ("path", "train", "val", "test")
_EXTRA_YAML_KEYS = ("names", "nc", "kpt_shape", "flip_idx")


def build_remote_paths(workspace, task_id):
    """按工作目录和任务号拼出这次远端运行用到的全部路径。"""
    run_dir = posixpath.join(str(workspace).rstrip("/") or "/", str(task_id))
    outputs_dir = posixpath.join(run_dir, OUTPUTS_DIR_NAME)
    save_dir = posixpath.join(outputs_dir, RUN_NAME)
    return {
        "run_dir": run_dir,
        "dataset_dir": posixpath.join(run_dir, DATASET_DIR_NAME),
        "model_dir": posixpath.join(run_dir, MODEL_DIR_NAME),
        "outputs_dir": outputs_dir,
        "save_dir": save_dir,
        "entry_path": posixpath.join(run_dir, ENTRY_FILENAME),
        "job_path": posixpath.join(run_dir, JOB_FILENAME),
        "log_path": posixpath.join(run_dir, LOG_FILENAME),
        "stop_path": posixpath.join(save_dir, STOP_FILENAME),
    }


def count_local_files(dir_path):
    """统计数据集目录里的文件数，用来把 rsync 行数换算成百分比。"""
    total = 0
    for _root, _dirs, files in os.walk(dir_path):
        total += len(files)
    return total


def _to_remote_path(value, local_dataset_root, remote_dataset_dir):
    """把本地 yaml 里的一个路径换成远端路径；引用了数据集目录之外的路径就直接失败。"""
    text = str(value or "").strip()
    if not text:
        return ""
    if not os.path.isabs(text):
        return text
    relative = os.path.relpath(text, local_dataset_root)
    if relative == ".":
        return remote_dataset_dir
    if relative.startswith(".."):
        raise RemoteExecutionError(
            f"数据集引用了目录之外的路径，远端无法复现：{text}（数据集根目录：{local_dataset_root}）"
        )
    return posixpath.join(remote_dataset_dir, relative.replace(os.sep, "/"))


def build_remote_dataset_yaml(local_yaml_text, local_dataset_root, remote_dataset_dir):
    """把本地 dataset.yaml 改写成远端路径版本，类别表原样带过去。"""
    data = yaml.safe_load(local_yaml_text) or {}
    remote = {}
    for key in _SPLIT_KEYS:
        if key not in data:
            continue
        value = data.get(key)
        if isinstance(value, str):
            remote[key] = _to_remote_path(value, local_dataset_root, remote_dataset_dir)
        elif isinstance(value, (list, tuple)):
            remote[key] = [
                item for item in (
                    _to_remote_path(value_item, local_dataset_root, remote_dataset_dir)
                    for value_item in value
                ) if item
            ]
    if not any(key in remote for key in ("train", "val")):
        raise RemoteExecutionError("dataset.yaml 里没有可用的 train/val 路径，远端找不到数据")
    for key in _EXTRA_YAML_KEYS:
        if key in data:
            remote[key] = data[key]
    return yaml.safe_dump(remote, sort_keys=False, allow_unicode=True)


def parse_remote_event(line):
    """从一行日志里取出事件对象；不是事件行就返回 None。"""
    text = str(line or "").strip()
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict) or not payload.get("evt"):
        return None
    return payload


def sync_progress(done, total):
    """数据同步阶段的进度。"""
    if total <= 0:
        return SYNC_PROGRESS_CEILING
    return min(SYNC_PROGRESS_CEILING, int(done / total * SYNC_PROGRESS_CEILING))


def epoch_progress(epoch, epochs):
    """按完成的 epoch 数换算训练阶段进度。"""
    return min(
        TRAIN_PROGRESS_CEILING,
        TRAIN_PROGRESS_FLOOR + int(epoch / max(int(epochs or 1), 1) * (TRAIN_PROGRESS_CEILING - TRAIN_PROGRESS_FLOOR)),
    )


def batch_progress(ni, total_batches):
    """按累计 batch 数换算训练阶段进度。"""
    if total_batches <= 0:
        return TRAIN_PROGRESS_FLOOR
    return min(
        TRAIN_PROGRESS_CEILING,
        TRAIN_PROGRESS_FLOOR + int(ni / total_batches * (TRAIN_PROGRESS_CEILING - TRAIN_PROGRESS_FLOOR)),
    )


def build_remote_job(training_config, training_context, *, data_ref, weights_path, save_dir, device):
    """生成远端训练脚本要读的 job 描述。"""
    context = dict(training_context)
    context["data_ref"] = data_ref
    args = build_training_args(training_config, context, save_dir, device=device)
    return {
        "data": args.pop("data"),
        "weights": weights_path,
        "project": args.pop("project"),
        "name": args.pop("name"),
        "device": args.pop("device"),
        "args": args,
    }


class _RemoteTrainerShim:
    """把远端事件里的原始 losses/metrics 包成运行时适配器认识的对象。"""

    def __init__(self, losses, metrics):
        self.loss_items = losses
        self.metrics = metrics


def epoch_update_from_event(training_mode, event):
    """用现有运行时适配器把远端 epoch 事件换成本地曲线点和进度文案。"""
    adapter = resolve_training_runtime_adapter(training_mode)
    epochs = int(event.get("of") or 0) or 1
    trainer = _RemoteTrainerShim(event.get("losses") or [], event.get("metrics") or {})
    return adapter.build_epoch_update(trainer, int(event.get("epoch") or 0), epochs)


class RemoteTrainingSupervisor:
    """把一个训练任务放到远端 GPU 上跑，并在本地维持任务状态。"""

    def __init__(self, task_id):
        task = load_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        if task.get("type") != TASK_TYPE_TRAINING:
            raise ValueError(f"远端监督进程只处理训练任务：{task_id}（{task.get('type')}）")
        payload = task.get("payload") or {}
        if payload.get("resume_from_task_id") or payload.get("resume_weight"):
            raise ValueError("远端训练暂不支持断点续训：续训权重在服务器上不存在，请改用本机训练续训")
        artifacts = task.get("artifacts") or {}
        self.task_id = task_id
        self.task = task
        self.training_config = payload.get("training_config") or {}
        self.local_output_dir = resolve_storage_path(artifacts.get(ARTIFACT_OUTPUT_DIR)) if artifacts.get(ARTIFACT_OUTPUT_DIR) else artifacts.get(ARTIFACT_OUTPUT_DIR)
        self.local_stop_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
        self.target = compute_service.require_compute_target(payload.get("compute_target_id"))
        self.paths = build_remote_paths(self.target["remote_workspace"], task_id)
        self.training_context = resolve_task_training_runtime_context(task)
        self.training_mode = self.training_context.get("training_mode")
        self.local_dataset_root = resolve_storage_path(task.get("dataset_path")) if task.get("dataset_path") else task.get("dataset_path")
        self.next_line = 1
        self.transferred_entries = 0
        self.finished = None
        self.remote_pid = None
        self.remote_stop_sent_at = None

    def execute(self):
        """跑完整个远端训练流程并把状态写回任务。"""
        if not self.local_output_dir:
            raise RemoteExecutionError("训练任务缺少本地输出目录，产物没地方放")
        mark_worker_started(self.task_id, os.getpid())
        merge_task_artifacts(self.task_id, self._remote_artifacts())
        try:
            self._prepare()
            self._start_remote_training()
            self._follow_remote_log()
            self._collect_results()
        except RemoteExecutionError as exc:
            self._fail(str(exc))
        except Exception as exc:
            self._fail(f"{exc}\n{traceback.format_exc()[-2000:]}")

    # ---------- 准备阶段 ----------

    def _prepare(self):
        """预检、建目录、推数据、上传脚本与权重、写 job 描述。"""
        self._progress(1, f"预检 {self.target['name']}（{self.target['ssh_host']}）...")
        report = compute_service.require_remote_ready(self.target["id"])
        compute_service.remote_mkdir(self.target, self.paths["run_dir"])
        compute_service.remote_mkdir(self.target, self.paths["outputs_dir"])
        compute_service.remote_mkdir(self.target, self.paths["save_dir"])
        self._progress(
            SYNC_PROGRESS_CEILING // 2,
            f"{self.target['name']} 预检通过（{self._gpu_label(report)}），准备同步数据集...",
        )

        if not self.local_dataset_root or not os.path.isdir(self.local_dataset_root):
            raise RemoteExecutionError(f"本地数据集目录不存在，无法同步到远端：{self.task.get('dataset_path')}")
        total_files = count_local_files(self.local_dataset_root)
        self.transferred_entries = 0
        self._progress(1, f"正在同步数据集到 {self.target['name']}（共 {total_files} 个文件）...")
        compute_service.sync_to_remote(
            self.target,
            self.local_dataset_root,
            self.paths["dataset_dir"],
            on_entry=self._note_entry_transferred,
        )
        self._progress(SYNC_PROGRESS_CEILING, f"数据集已同步（传输 {self.transferred_entries} 个文件），准备权重与脚本...")

        compute_service.copy_file_to_remote(self.target, self.training_context["model_path"], self.paths["model_dir"])
        with open(ENTRY_SCRIPT_PATH, "r", encoding="utf-8") as handle:
            compute_service.remote_write_text(self.target, self.paths["entry_path"], handle.read())

        self.remote_data_ref = self._remote_data_ref()
        self.remote_weights = posixpath.join(self.paths["model_dir"], os.path.basename(self.training_context["model_path"]))
        job = build_remote_job(
            self.training_config,
            self.training_context,
            data_ref=self.remote_data_ref,
            weights_path=self.remote_weights,
            save_dir=self.paths["save_dir"],
            device=self.target["device"],
        )
        compute_service.remote_write_text(self.target, self.paths["job_path"], json.dumps(job, ensure_ascii=False, indent=2))

    def _remote_data_ref(self):
        """数据集在远端的入口：分类任务给目录，其余给改写过的 dataset.yaml。"""
        if self.training_context.get("vision_task_type") == VISION_TASK_TYPE_CLASSIFY:
            return self.paths["dataset_dir"]
        local_yaml = self.training_context.get("data_yaml")
        if not local_yaml or not os.path.isfile(local_yaml):
            raise RemoteExecutionError(f"找不到本地 dataset.yaml，无法在远端定位数据：{local_yaml}")
        with open(local_yaml, "r", encoding="utf-8") as handle:
            remote_yaml = build_remote_dataset_yaml(handle.read(), self.local_dataset_root, self.paths["dataset_dir"])
        remote_path = posixpath.join(self.paths["dataset_dir"], REMOTE_DATASET_YAML_NAME)
        compute_service.remote_write_text(self.target, remote_path, remote_yaml)
        return remote_path

    # ---------- 启动与跟随 ----------

    def _start_remote_training(self):
        """在远端后台启动训练并记录进程号。"""
        self.remote_pid = compute_service.remote_start_detached(
            self.target,
            [REMOTE_PYTHON, self.paths["entry_path"], "--job", self.paths["job_path"]],
            cwd=self.paths["run_dir"],
            log_path=self.paths["log_path"],
        )
        merge_task_artifacts(self.task_id, {ARTIFACT_REMOTE_PID: self.remote_pid})
        update_task_status(
            self.task_id,
            status=TASK_STATUS_RUNNING,
            started_at=self.task.get("started_at") or now_iso(),
            message=f"远端训练进程已启动（{self.target['name']}，进程号 {self.remote_pid}），等待首轮 epoch...",
        )

    def _follow_remote_log(self):
        """跟随远端日志直到拿到结论；SSH 断了就从没读到的那一行继续接。"""
        retries = 0
        while not self.finished:
            stream = compute_service.remote_tail(self.target, self.paths["log_path"], from_line=self.next_line)
            self._pump_stream(stream)
            if self.finished:
                return
            if not self.remote_pid or compute_service.remote_pid_alive(self.target, self.remote_pid):
                retries += 1
                if retries > TAIL_RETRY_LIMIT:
                    raise RemoteExecutionError(
                        f"与 {self.target['name']} 的日志通道连续断开 {TAIL_RETRY_LIMIT} 次，"
                        f"远端训练进程仍在跑（进程号 {self.remote_pid}），远端目录：{self.paths['run_dir']}"
                    )
                self._progress(None, f"日志连接断开，正在重连（第 {retries} 次）...")
                time.sleep(TAIL_RETRY_SLEEP_SECONDS)
                continue
            raise RemoteExecutionError(
                f"远端训练进程（进程号 {self.remote_pid}）退出但没有给出结论。\n{self._remote_log_tail()}"
            )

    def _pump_stream(self, stream):
        """读一条 tail 管道：边读边处理事件，同时盯着停止请求。"""
        inbox = queue.Queue()

        def reader():
            try:
                for line in stream.stdout or []:
                    inbox.put(line)
            except Exception as exc:  # 管道读坏了也要让主循环知道，不能永远等下去
                inbox.put(f"__stream_error__ {exc}")
            finally:
                inbox.put(None)

        threading.Thread(target=reader, daemon=True).start()
        while True:
            if self._handle_stop_request():
                break
            try:
                line = inbox.get(timeout=POLL_INTERVAL_SECONDS)
            except queue.Empty:
                continue
            if line is None:
                break
            if str(line).startswith("__stream_error__"):
                raise RemoteExecutionError(f"读取远端日志失败：{str(line)[len('__stream_error__'):].strip()}")
            self._consume_line(line)
        if stream.poll() is None:
            stream.kill()

    def _consume_line(self, line):
        """处理远端日志的一行：事件行写进任务状态，普通行原样转进本地日志。"""
        self.next_line += 1
        text = str(line).rstrip("\n")
        print(text, flush=True)
        event = parse_remote_event(text)
        if not event:
            return
        evt = event.get("evt")
        if evt == "start":
            self._progress(
                None,
                f"远端训练开始（python {event.get('python')} / ultralytics {event.get('ultralytics')}）...",
            )
        elif evt == "batch":
            self._progress(
                batch_progress(int(event.get("ni") or 0), int(event.get("total") or 0)),
                f"远端训练中（{event.get('ni')}/{event.get('total')} 批）...",
            )
        elif evt == "epoch":
            self._record_epoch(event)
        elif evt == "done":
            self.finished = {"status": TASK_STATUS_COMPLETED}
        elif evt == "stopped":
            self.finished = {"status": TASK_STATUS_STOPPED}
        elif evt == "error":
            raise RemoteExecutionError(f"远端训练失败：{event.get('error')}\n{event.get('traceback') or ''}")

    def _record_epoch(self, event):
        """把一个 epoch 事件写成本地曲线点与进度。"""
        update = epoch_update_from_event(self.training_mode, event)
        progress = epoch_progress(int(event.get("epoch") or 0), int(event.get("of") or 0))
        update_task_status(self.task_id, status=TASK_STATUS_RUNNING, progress=progress, message=update["message"])
        write_task_history(self.task_id, **update["history"])

    # ---------- 停止 ----------

    def _handle_stop_request(self):
        """用户点了停止：先让远端自己收尾，超时再升级为终止远端进程。"""
        if not is_stop_requested(self.local_stop_path):
            return False
        if self.remote_stop_sent_at is None:
            compute_service.remote_touch(self.target, self.paths["stop_path"])
            self.remote_stop_sent_at = time.time()
            self._progress(None, "已发送停止请求，等待远端训练在当前 epoch 收尾...")
            return False
        waited = time.time() - self.remote_stop_sent_at
        if waited > REMOTE_STOP_GRACE_SECONDS and self.remote_pid:
            compute_service.remote_kill(self.target, self.remote_pid)
            self.remote_pid = None
            self.finished = {"status": TASK_STATUS_STOPPED}
            return True
        return waited <= REMOTE_STOP_GRACE_SECONDS + REMOTE_KILL_GRACE_SECONDS

    # ---------- 收尾 ----------

    def _collect_results(self):
        """回传产物到本地训练输出目录，并按配置清理远端临时目录。"""
        status = (self.finished or {}).get("status") or TASK_STATUS_STOPPED
        self._progress(None, "正在回传训练产物...")
        compute_service.remote_remove(self.target, self.paths["stop_path"])
        os.makedirs(self.local_output_dir, exist_ok=True)
        compute_service.sync_from_remote(self.target, self.paths["save_dir"], self.local_output_dir)
        if self.target.get("keep_remote_copy"):
            kept_note = f"按设置保留了远端副本：{self.paths['run_dir']}"
        else:
            compute_service.remote_remove(self.target, self.paths["run_dir"])
            kept_note = "远端临时目录已清理"
        weight_artifacts = {**build_training_weight_artifacts(self.local_output_dir), ARTIFACT_REMOTE_PID: None}
        if status == TASK_STATUS_COMPLETED:
            finish_worker_task(
                self.task_id,
                TASK_STATUS_COMPLETED,
                f"训练完成（{kept_note}）",
                progress=100,
                artifacts_patch=weight_artifacts,
                stop_signal_path=self.local_stop_path,
            )
        else:
            finish_worker_task(
                self.task_id,
                TASK_STATUS_STOPPED,
                f"训练已终止（{kept_note}）",
                artifacts_patch=weight_artifacts,
                stop_signal_path=self.local_stop_path,
            )

    def _fail(self, error_text):
        """失败收口：错误原样写进任务，并说清远端留下了什么。"""
        kept = f"远端目录未清理，排查完可手动删除：{self.paths['run_dir']}"
        try:
            if self.remote_pid and compute_service.remote_pid_alive(self.target, self.remote_pid):
                compute_service.remote_kill(self.target, self.remote_pid, force=True)
                kept = f"已强制终止远端进程 {self.remote_pid}；{kept}"
        except Exception as exc:
            kept = f"终止远端进程失败：{exc}；{kept}"
        finish_worker_task(
            self.task_id,
            TASK_STATUS_FAILED,
            "远端训练失败",
            error=f"{error_text}\n\n{kept}",
            stop_signal_path=self.local_stop_path,
        )

    # ---------- 小工具 ----------

    def _note_entry_transferred(self, count):
        """记下 rsync 已传输的条目数，供完成时回报。"""
        self.transferred_entries = count

    def _progress(self, progress, message):
        """更新进度与消息；progress 传 None 只改消息，不推动进度条。"""
        if progress is None:
            update_task_status(self.task_id, status=TASK_STATUS_RUNNING, message=message)
        else:
            update_worker_task_progress(self.task_id, progress, message)

    def _remote_artifacts(self):
        """远端运行时句柄：排错和确认「这次跑在哪个目录」全靠它。"""
        return {
            ARTIFACT_REMOTE_HOST: self.target["ssh_host"],
            ARTIFACT_REMOTE_RUN_DIR: self.paths["run_dir"],
            ARTIFACT_REMOTE_DATA_DIR: self.paths["dataset_dir"],
            ARTIFACT_REMOTE_LOG_PATH: self.paths["log_path"],
        }

    def _remote_log_tail(self):
        """取远端日志尾部，失败时也能看到服务器说了什么。"""
        try:
            _rc, stdout, _stderr = compute_service.remote_run(
                self.target,
                ["tail", "-c", str(REMOTE_LOG_TAIL_BYTES), self.paths["log_path"]],
            )
            return (stdout or "").strip() or "（远端日志为空）"
        except Exception as exc:
            return f"（读取远端日志失败：{exc}）"

    def _gpu_label(self, report):
        """把预检拿到的 GPU 名字压成一行显示。"""
        names = report.get("gpu_names") or []
        return names[0] if names else f"device {report.get('device')}"


def execute_remote_training_task(task_id):
    """执行一个跑在远端 GPU 上的训练任务。"""
    supervisor = RemoteTrainingSupervisor(task_id)
    try:
        supervisor.execute()
    finally:
        mark_worker_exited(task_id)


__all__ = [
    "build_remote_dataset_yaml",
    "build_remote_job",
    "build_remote_paths",
    "batch_progress",
    "epoch_progress",
    "epoch_update_from_event",
    "execute_remote_training_task",
    "parse_remote_event",
    "sync_progress",
]
