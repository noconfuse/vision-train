"""启动回收只该收自己那一份：别的实例正在跑的活动任务，多开一个后端不能把它判死。"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from db import session_scope
from db.models import Task
from protocols.task_status import TASK_STATUS_INTERRUPTED, TASK_STATUS_PENDING, TASK_STATUS_RUNNING
from contexts.task.infrastructure.task_repository import create_task, get_task_record, mark_orphan_tasks_interrupted


def _task(status=TASK_STATUS_RUNNING):
    task = create_task(
        project_path="/tmp/vt_orphan_probe",
        project_name="orphan-probe",
        type_="training",
        dataset_name="demo",
        message="已就绪",
    )
    with session_scope() as session:
        session.get(Task, task["id"]).status = status
    return task


def _backdate(task_id, seconds_ago):
    """把 updated_at 推到过去：安静期认的是这个字段，update_task 会顺手改回当前时间，只能直接写。"""
    with session_scope() as session:
        session.get(Task, task_id).updated_at = (datetime.now() - timedelta(seconds=seconds_ago)).isoformat()


def sweep(alive_task_id=None):
    """活 worker 的判定要打桩：真探活会受跑测试这台机器的进程影响。"""

    def fake_alive(task_dict):
        return True if task_dict["id"] == alive_task_id else None

    with patch("contexts.task.infrastructure.task_runtime.is_worker_alive", side_effect=fake_alive):
        return mark_orphan_tasks_interrupted()[0]


class OrphanReclaimTests(unittest.TestCase):
    def test_live_worker_owns_its_task_and_survives_the_sweep(self):
        alive = _task()
        _backdate(alive["id"], 3600)
        sweep(alive_task_id=alive["id"])
        self.assertEqual(TASK_STATUS_RUNNING, get_task_record(alive["id"])["status"])

    def test_task_touched_a_moment_ago_waits_for_the_next_sweep(self):
        quiet = _task(status=TASK_STATUS_PENDING)
        sweep()
        self.assertEqual(TASK_STATUS_PENDING, get_task_record(quiet["id"])["status"])

    def test_stale_task_with_no_worker_is_interrupted(self):
        stale = _task()
        _backdate(stale["id"], 3600)
        self.assertGreaterEqual(sweep(), 1)
        after = get_task_record(stale["id"])
        self.assertEqual(TASK_STATUS_INTERRUPTED, after["status"])
        self.assertTrue(str(after["message"]).endswith("[后端重启中断]"))

    def test_timestamp_that_does_not_parse_is_treated_as_stale(self):
        task = _task()
        with session_scope() as session:
            session.get(Task, task["id"]).updated_at = "不像时间"
        sweep()
        self.assertEqual(TASK_STATUS_INTERRUPTED, get_task_record(task["id"])["status"])


if __name__ == "__main__":
    unittest.main()
