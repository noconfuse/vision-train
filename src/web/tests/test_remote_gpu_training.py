"""远端 GPU 训练的网关、预检与监督进程回归测试。

全部打桩 remote_shell 的 run / popen 两个原语：不连网络、不碰真实数据集，
只验证「命令怎么拼、远端报错怎么带回来、进度和曲线怎么换算」这三件事。
"""

import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

import yaml

from protocols.capabilities.training_profile import get_training_profile
from contexts.compute.domain import target_rules
from contexts.compute.domain.errors import RemoteExecutionError
from contexts.compute.infrastructure import preflight, remote_shell
from contexts.training.infrastructure import remote_execution


class FakeRun:
    """按远端命令片段回放预设结果，并记下本机真正执行过的命令行。"""

    def __init__(self, matches=None, default_returncode=0):
        self.matches = list(matches or [])
        self.default_returncode = default_returncode
        self.calls = []

    def __call__(self, argv, *, timeout=None, input_text=None):
        tokens = [str(item) for item in argv]
        remote = tokens[-1] if tokens and tokens[0] == "ssh" else ""
        self.calls.append({"argv": tokens, "remote": remote, "input": input_text})
        for needle, reply in self.matches:
            if needle in remote:
                return _completed(reply)
        return _completed({"returncode": self.default_returncode})

    def remote_commands(self):
        return [call["remote"] for call in self.calls]


def _completed(reply):
    reply = reply or {}
    return SimpleNamespace(
        returncode=int(reply.get("returncode", 0)),
        stdout=reply.get("stdout", ""),
        stderr=reply.get("stderr", ""),
    )


class FakePopen:
    """把一段固定文本伪装成可逐行读的管道。"""

    def __init__(self, lines, returncode=0):
        self.returncode = returncode
        self.killed = False
        self.stdout = iter(list(lines))

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True


def _target(**overrides):
    target = {
        "id": "abc123def456",
        "name": "训练机",
        "ssh_host": "gpu-server",
        "remote_workspace": "/dev/shm/vision-train",
        "device": "0",
        "keep_remote_copy": False,
    }
    target.update(overrides)
    return target


class TargetRuleTests(unittest.TestCase):
    def test_blank_fields_fall_back_to_memory_disk_workspace(self):
        fields = target_rules.normalize_target_fields(name=" 训练机 ", ssh_host=" user@host ", remote_workspace="", device="")
        self.assertEqual(fields["name"], "训练机")
        self.assertEqual(fields["ssh_host"], "user@host")
        self.assertEqual(fields["remote_workspace"], target_rules.DEFAULT_REMOTE_WORKSPACE)
        self.assertEqual(fields["device"], target_rules.DEFAULT_DEVICE)

    def test_shell_metacharacters_in_host_are_rejected(self):
        for bad in ("host; rm -rf /", "host `id`", "host | cat", "two hosts"):
            with self.assertRaises(Exception):
                target_rules.normalize_ssh_host(bad)

    def test_device_only_accepts_card_numbers(self):
        self.assertEqual(target_rules.normalize_device("0,1"), "0,1")
        for bad in ("mps", "cpu", "0,", "-1"):
            with self.assertRaises(Exception):
                target_rules.normalize_device(bad)

    def test_relative_workspace_is_rejected(self):
        with self.assertRaises(target_rules.RemoteWorkspaceNotAbsolute):
            target_rules.normalize_workspace("data/remote")

    def test_only_submitted_keys_are_returned(self):
        self.assertEqual(target_rules.normalize_target_fields(name="a"), {"name": "a"})


class CommandBuildingTests(unittest.TestCase):
    def test_ssh_argv_keeps_the_command_as_one_quoted_token(self):
        argv = remote_shell.build_ssh_argv("gpu-server", ["sh", "-c", "echo 'a b'"])
        self.assertEqual(argv[0], "ssh")
        self.assertIn("BatchMode=yes", argv)
        self.assertEqual(argv[-2], "gpu-server")
        self.assertEqual(argv[-1], """sh -c 'echo '"'"'a b'"'"''""")

    def test_detached_script_logs_and_echoes_pid(self):
        script = remote_shell.build_detached_script(
            ["python3", "/dev/shm/vision-train/t1/remote_train_entry.py", "--job", "/dev/shm/vision-train/t1/job.json"],
            "/dev/shm/vision-train/t1",
            "/dev/shm/vision-train/t1/train.log",
        )
        self.assertEqual(
            script,
            "cd /dev/shm/vision-train/t1 && nohup python3 /dev/shm/vision-train/t1/remote_train_entry.py "
            "--job /dev/shm/vision-train/t1/job.json > /dev/shm/vision-train/t1/train.log 2>&1 & echo $!",
        )

    def test_detached_script_quotes_paths_with_spaces(self):
        script = remote_shell.build_detached_script(["python3", "/data/my run/train.py"], "/data/my run", "/data/my run/t.log")
        self.assertTrue(script.startswith("cd '/data/my run' && nohup python3 '/data/my run/train.py' "))
        self.assertIn("> '/data/my run/t.log' 2>&1 & echo $!", script)

    def test_rsync_points_at_directory_contents(self):
        to_remote = remote_shell.build_rsync_to_argv("gpu-server", "/data/dataset/", "/dev/shm/vision-train/t1/dataset")
        self.assertEqual(to_remote[-2], "/data/dataset/")
        self.assertEqual(to_remote[-1], "gpu-server:/dev/shm/vision-train/t1/dataset/")
        self.assertIn("BatchMode=yes", to_remote[to_remote.index("-e") + 1])
        from_remote = remote_shell.build_rsync_from_argv("gpu-server", "/remote/run", "/local/out")
        self.assertEqual(from_remote[-2:], ["gpu-server:/remote/run/", "/local/out/"])


class RemoteCallTests(unittest.TestCase):
    def setUp(self):
        self._real_run = remote_shell.run
        self._real_popen = remote_shell.popen

    def tearDown(self):
        remote_shell.run = self._real_run
        remote_shell.popen = self._real_popen

    def test_remote_check_returns_remote_stderr_verbatim(self):
        remote_shell.run = FakeRun([("", {"returncode": 1, "stderr": "mkdir: /dev/shm: Read-only file system"})])
        with self.assertRaises(RemoteExecutionError) as ctx:
            remote_shell.remote_mkdir(_target(), "/dev/shm/vision-train/t1")
        message = str(ctx.exception)
        self.assertIn("创建远端目录", message)
        self.assertIn("gpu-server 上退出码 1", message)
        self.assertIn("Read-only file system", message)

    def test_start_detached_reads_the_last_pid_line(self):
        remote_shell.run = FakeRun([("", {"stdout": "bash: warning: no job control\n31337\n"})])
        self.assertEqual(
            remote_shell.remote_start_detached(
                _target(), ["python3", "entry.py", "--job", "job.json"], cwd="/run", log_path="/run/train.log"
            ),
            31337,
        )

    def test_start_detached_fails_loudly_without_a_pid(self):
        remote_shell.run = FakeRun([("", {"stdout": "nohup: can't detach"})])
        with self.assertRaises(RemoteExecutionError) as ctx:
            remote_shell.remote_start_detached(_target(), ["python3", "entry.py"], cwd="/run", log_path="/run/train.log")
        self.assertIn("拿不到进程号", str(ctx.exception))

    def test_sync_counts_files_and_reports_each_one(self):
        seen = []
        remote_shell.run = FakeRun()
        remote_shell.popen = lambda argv: FakePopen(["images/", "images/a.jpg", "images/b.jpg", "\n"])
        count = remote_shell.sync_to_remote(_target(), "/local", "/remote", on_entry=seen.append)
        self.assertEqual(count, 2)
        self.assertEqual(seen, [1, 2])

    def test_sync_failure_keeps_rsync_output(self):
        remote_shell.run = FakeRun()
        remote_shell.popen = lambda argv: FakePopen(["rsync: connection unexpectedly closed"], returncode=255)
        with self.assertRaises(RemoteExecutionError) as ctx:
            remote_shell.sync_to_remote(_target(), "/local", "/remote")
        self.assertIn("推送数据集 失败：退出码 255", str(ctx.exception))
        self.assertIn("connection unexpectedly closed", str(ctx.exception))

    def test_write_text_streams_content_over_stdin(self):
        recorder = FakeRun()
        remote_shell.run = recorder
        remote_shell.remote_write_text(_target(), "/remote/run/job.json", '{"epochs": 2}')
        self.assertEqual(recorder.calls[0]["input"], '{"epochs": 2}')
        self.assertEqual(recorder.calls[0]["remote"], "sh -c 'mkdir -p /remote/run && cat > /remote/run/job.json'")

    def test_write_text_rejects_a_failed_remote_write(self):
        remote_shell.run = FakeRun([("", {"returncode": 1, "stderr": "bash: line 0: /dev/shm: Permission denied"})])
        with self.assertRaises(RemoteExecutionError) as ctx:
            remote_shell.remote_write_text(_target(), "/dev/shm/job.json", "x")
        self.assertIn("写入远端文件 /dev/shm/job.json 失败", str(ctx.exception))
        self.assertIn("Permission denied", str(ctx.exception))


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self._real_run = remote_shell.run

    def tearDown(self):
        remote_shell.run = self._real_run

    def test_unreachable_host_short_circuits_the_rest(self):
        recorder = FakeRun([("true", {"returncode": 255, "stderr": "ssh: connect to host port 22: Connection refused"})])
        remote_shell.run = recorder
        report = preflight.run_preflight(_target())
        self.assertFalse(report["ok"])
        self.assertEqual(len(recorder.calls), 1)
        self.assertIn("SSH 连不上", report["problems"][0])
        self.assertIn("Connection refused", report["problems"][0])

    def test_every_problem_is_listed_at_once(self):
        probe = {
            "python": "3.11.9",
            "torch": "2.4.0",
            "cuda_available": False,
            "gpu_names": [],
            "ultralytics_error": "ModuleNotFoundError(\"No module named 'ultralytics'\")",
        }
        remote_shell.run = FakeRun(
            [
                ("true", {}),
                ("df -Pk", {"stdout": "Filesystem 1024-blocks Used Available Capacity Mounted on\ntmpfs 400000 100 399900 1% /dev/shm\n"}),
                ("python3 -c", {"stdout": json.dumps(probe)}),
            ]
        )
        report = preflight.run_preflight(_target())
        self.assertFalse(report["ok"])
        self.assertTrue(any("ultralytics" in item for item in report["problems"]))
        self.assertTrue(any("cuda" in item for item in report["problems"]))
        self.assertEqual(report["free_bytes"], 399900 * 1024)
        self.assertEqual(report["python"], "3.11.9")

    def test_require_preflight_passed_raises_with_all_reasons(self):
        remote_shell.run = FakeRun(
            [
                ("df -Pk", {"stdout": "bad df"}),
                ("python3 -c", {"returncode": 127, "stderr": "sh: python3: not found"}),
            ]
        )
        with self.assertRaises(RemoteExecutionError) as ctx:
            preflight.require_preflight_passed(_target())
        message = str(ctx.exception)
        self.assertIn("预检未通过", message)
        self.assertIn("python3", message)

    def test_green_host_passes(self):
        probe = {"python": "3.11.9", "torch": "2.4.0", "cuda_available": True, "gpu_names": ["NVIDIA RTX 4090"], "ultralytics": "8.3.0"}
        remote_shell.run = FakeRun(
            [
                ("df -Pk", {"stdout": "Filesystem 1024-blocks Used Available Capacity Mounted on\ntmpfs 40000000 100 39000000 1% /dev/shm\n"}),
                ("python3 -c", {"stdout": f"UserWarning: something\n{json.dumps(probe)}"}),
            ]
        )
        report = preflight.require_preflight_passed(_target())
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["gpu_names"], ["NVIDIA RTX 4090"])


class RemoteLayoutTests(unittest.TestCase):
    def test_paths_live_under_the_task_id(self):
        paths = remote_execution.build_remote_paths("/dev/shm/vision-train/", "t1234567890")
        self.assertEqual(paths["run_dir"], "/dev/shm/vision-train/t1234567890")
        self.assertEqual(paths["dataset_dir"], "/dev/shm/vision-train/t1234567890/dataset")
        self.assertEqual(paths["save_dir"], "/dev/shm/vision-train/t1234567890/outputs/run")
        self.assertEqual(paths["stop_path"], "/dev/shm/vision-train/t1234567890/outputs/run/.stop-request")

    def test_dataset_yaml_is_rewritten_to_remote_paths(self):
        root = tempfile.mkdtemp()
        try:
            text = "\n".join(
                [
                    f"path: {root}",
                    f"train: {root}/images/train",
                    f"val: {root}/images/val",
                    "test:",
                    "names:",
                    "  0: person",
                    "  1: harness",
                    "nc: 2",
                ]
            )
            parsed = yaml.safe_load(remote_execution.build_remote_dataset_yaml(text, root, "/remote/ds"))
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(parsed["path"], "/remote/ds")
        self.assertEqual(parsed["train"], "/remote/ds/images/train")
        self.assertEqual(parsed["val"], "/remote/ds/images/val")
        self.assertEqual(parsed["names"], {0: "person", 1: "harness"})
        self.assertEqual(parsed["nc"], 2)
        self.assertNotIn("test", parsed)

    def test_relative_split_paths_are_left_alone(self):
        parsed = yaml.safe_load(remote_execution.build_remote_dataset_yaml("train: images/train\nval: images/val", "/local/ds", "/remote/ds"))
        self.assertEqual(parsed["train"], "images/train")

    def test_paths_outside_the_dataset_root_fail_instead_of_guessing(self):
        with self.assertRaises(RemoteExecutionError) as ctx:
            remote_execution.build_remote_dataset_yaml("train: /local/other/images\nval: /local/ds/images/val", "/local/ds", "/remote/ds")
        self.assertIn("目录之外", str(ctx.exception))

    def test_dataset_yaml_without_splits_fails(self):
        with self.assertRaises(RemoteExecutionError) as ctx:
            remote_execution.build_remote_dataset_yaml("names: {0: person}", "/local/ds", "/remote/ds")
        self.assertIn("train/val", str(ctx.exception))

    def test_entry_script_exists_where_the_supervisor_looks(self):
        self.assertTrue(os.path.isfile(remote_execution.ENTRY_SCRIPT_PATH))


class EventAndProgressTests(unittest.TestCase):
    def test_only_json_event_lines_are_parsed(self):
        self.assertEqual(remote_execution.parse_remote_event('{"evt": "done"}'), {"evt": "done"})
        self.assertIsNone(remote_execution.parse_remote_event("Epoch    GPU_mem   box_loss"))
        self.assertIsNone(remote_execution.parse_remote_event('{"not_an_event": 1}'))
        self.assertIsNone(remote_execution.parse_remote_event("{broken"))

    def test_progress_stays_inside_its_band(self):
        self.assertEqual(remote_execution.sync_progress(0, 0), remote_execution.SYNC_PROGRESS_CEILING)
        self.assertEqual(remote_execution.epoch_progress(1, 50), remote_execution.TRAIN_PROGRESS_FLOOR + 1)
        self.assertEqual(remote_execution.epoch_progress(50, 50), remote_execution.TRAIN_PROGRESS_CEILING)
        self.assertEqual(remote_execution.batch_progress(0, 0), remote_execution.TRAIN_PROGRESS_FLOOR)
        self.assertLessEqual(remote_execution.batch_progress(10 ** 9, 3000), remote_execution.TRAIN_PROGRESS_CEILING)

    def test_epoch_event_becomes_a_local_curve_point(self):
        update = remote_execution.epoch_update_from_event(
            "yolo_detect",
            {
                "epoch": 3,
                "of": 50,
                "losses": [1.25, 0.5, 0.2],
                "metrics": {"metrics/mAP50(B)": 0.31, "metrics/mAP50-95(B)": 0.18},
            },
        )
        self.assertIn("Epoch 3/50", update["message"])
        self.assertEqual(update["history"]["box_loss"], 1.25)
        self.assertEqual(update["history"]["cls_loss"], 0.5)
        self.assertEqual(update["history"]["map50"], 0.31)

    def test_epoch_event_for_classify_uses_top1(self):
        update = remote_execution.epoch_update_from_event(
            "yolo_classify",
            {"epoch": 1, "of": 2, "losses": [0.9], "metrics": {"metrics/accuracy_top1": 0.72}},
        )
        self.assertEqual(update["history"]["extra"]["top1"], 0.72)

    def test_job_description_carries_remote_paths_and_device(self):
        job = remote_execution.build_remote_job(
            {"epochs": 2, "batch": 4, "imgsz": 640},
            {
                "vision_task_type": "detect",
                "training_profile": get_training_profile("yolo_detect"),
                "data_ref": "/local/ds/images/train",
            },
            data_ref="/remote/ds/dataset.remote.yaml",
            weights_path="/remote/model/yolov8n.pt",
            save_dir="/remote/run/outputs/run",
            device="0,1",
        )
        self.assertEqual(job["data"], "/remote/ds/dataset.remote.yaml")
        self.assertEqual(job["weights"], "/remote/model/yolov8n.pt")
        self.assertEqual(job["device"], "0,1")
        self.assertEqual(job["project"], "/remote/run/outputs")
        self.assertEqual(job["name"], "run")
        self.assertEqual(job["args"]["epochs"], 2)
        self.assertNotIn("device", job["args"])


class WorkerChoiceTests(unittest.TestCase):
    def test_local_by_default_and_remote_only_for_a_known_server(self):
        from contexts.training.infrastructure import execution_starters

        self.assertEqual(execution_starters.LOCAL_WORKER_MODULE, "task_worker")
        self.assertEqual(execution_starters.REMOTE_WORKER_MODULE, "remote_task_worker")
        self.assertEqual(execution_starters.resolve_training_worker_module(None), "task_worker")
        self.assertEqual(execution_starters.resolve_training_worker_module(""), "task_worker")

        original = execution_starters.require_compute_target
        try:
            def _missing(target_id):
                raise ValueError(f"GPU 服务器不存在（id={target_id}）")

            execution_starters.require_compute_target = _missing
            with self.assertRaises(ValueError):
                execution_starters.resolve_training_worker_module("missing1")
            execution_starters.require_compute_target = lambda target_id: _target(id=target_id)
            self.assertEqual(execution_starters.resolve_training_worker_module("abc123def456"), "remote_task_worker")
        finally:
            execution_starters.require_compute_target = original


class SupervisorGuardTests(unittest.TestCase):
    def _with_task(self, task):
        original = remote_execution.load_task
        try:
            remote_execution.load_task = lambda task_id: dict(task, id=task_id)
            return remote_execution.RemoteTrainingSupervisor(task.get("id") or "t1")
        finally:
            remote_execution.load_task = original

    def test_resume_is_refused_because_the_server_has_no_previous_weights(self):
        with self.assertRaises(ValueError) as ctx:
            self._with_task(
                {
                    "type": "training",
                    "payload": {"resume_weight": "/local/last.pt", "training_config": {}},
                    "artifacts": {},
                }
            )
        self.assertIn("断点续训", str(ctx.exception))

    def test_non_training_tasks_are_refused(self):
        with self.assertRaises(ValueError) as ctx:
            self._with_task({"type": "evaluate", "payload": {}, "artifacts": {}})
        self.assertIn("只处理训练任务", str(ctx.exception))

    def test_stop_signal_is_written_on_the_remote_and_kills_after_the_grace_window(self):
        calls = []
        supervisor = self._stop_stub(calls)
        original_requested = remote_execution.is_stop_requested
        remote_execution.is_stop_requested = lambda path: True
        try:
            # 第一次只留下停止文件，让远端在当前 epoch 结束时自己收尾
            self.assertFalse(supervisor._handle_stop_request())
            self.assertEqual(calls[-1], ("touch", "abc123def456", "/dev/shm/vision-train/t1/outputs/run/.stop-request"))
            supervisor.remote_stop_sent_at = supervisor.remote_stop_sent_at - (remote_execution.REMOTE_STOP_GRACE_SECONDS + 1)
            self.assertTrue(supervisor._handle_stop_request())
            self.assertEqual(calls[-1], ("kill", "abc123def456", 31337, False))
            self.assertIsNone(supervisor.remote_pid)
            self.assertEqual(supervisor.finished, {"status": "stopped"})
        finally:
            remote_execution.is_stop_requested = original_requested

    def _stop_stub(self, calls):
        target = _target()
        supervisor = remote_execution.RemoteTrainingSupervisor.__new__(remote_execution.RemoteTrainingSupervisor)
        supervisor.task_id = "t1"
        supervisor.target = target
        supervisor.paths = remote_execution.build_remote_paths(target["remote_workspace"], "t1")
        supervisor.local_stop_path = "/local/t1/.stop-request"
        supervisor.remote_pid = 31337
        supervisor.remote_stop_sent_at = None
        supervisor._progress = lambda progress, message: None
        original_touch = remote_execution.compute_service.remote_touch
        original_kill = remote_execution.compute_service.remote_kill
        self.addCleanup(setattr, remote_execution.compute_service, "remote_touch", original_touch)
        self.addCleanup(setattr, remote_execution.compute_service, "remote_kill", original_kill)
        remote_execution.compute_service.remote_touch = lambda target, path: calls.append(("touch", target["id"], path))
        remote_execution.compute_service.remote_kill = lambda target, pid, *, force=False: calls.append(
            ("kill", target["id"], pid, force)
        )
        return supervisor


if __name__ == "__main__":
    unittest.main()
