"""数据集删除时关联任务/工作流清理的回归测试。"""

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from contexts.training.infrastructure.workflow_repository import (
    delete_dataset_related_state,
    delete_dataset_training_state,
)


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._items)


class _FakeSession:
    def __init__(self, task_rows=None, workflow_rows=None):
        self.task_rows = task_rows or []
        self.workflow_rows = workflow_rows or []
        self.deleted = []

    def query(self, model):
        model_name = getattr(model, "__name__", "")
        if model_name == "Task":
            return _FakeQuery(self.task_rows)
        if model_name == "WorkflowRecord":
            return _FakeQuery(self.workflow_rows)
        return _FakeQuery([])

    def delete(self, item):
        self.deleted.append(item)


@contextmanager
def _session_scope_factory(session):
    yield session


class DatasetDeleteCleanupTests(unittest.TestCase):
    def test_delete_dataset_training_state_removes_tasks_workflows_and_dataset_artifacts(self):
        task_row = SimpleNamespace(
            id="task_1",
            to_dict=lambda: {"id": "task_1", "status": "completed", "type": "training"},
        )
        workflow_row = SimpleNamespace(id="wf_1")
        session = _FakeSession(task_rows=[task_row], workflow_rows=[workflow_row])
        removed_paths = []
        existing_paths = {
            "/project/training_outputs/dataset_a",
            "/project/training_calibrations/dataset_a",
        }

        with (
            patch(
                "contexts.training.infrastructure.workflow_repository.session_scope",
                return_value=_session_scope_factory(session),
            ),
            patch(
                "contexts.training.infrastructure.workflow_repository.delete_training_task_artifacts",
                return_value=["/project/training_outputs/dataset_a/run_1"],
            ),
            patch(
                "contexts.training.infrastructure.workflow_repository.os.path.exists",
                side_effect=lambda path: path in existing_paths,
            ),
            patch(
                "contexts.training.infrastructure.workflow_repository.remove_tree",
                side_effect=lambda path: removed_paths.append(path),
            ),
        ):
            result = delete_dataset_training_state("/project", "ds_1", dataset_name="dataset_a")

        self.assertEqual(result["removed_task_ids"], ["task_1"])
        self.assertEqual(result["removed_workflow_ids"], ["wf_1"])
        self.assertEqual(
            result["removed_paths"],
            [
                "/project/training_outputs/dataset_a/run_1",
                "/project/training_outputs/dataset_a",
                "/project/training_calibrations/dataset_a",
            ],
        )
        self.assertEqual(session.deleted, [task_row, workflow_row])
        self.assertEqual(
            removed_paths,
            [
                "/project/training_outputs/dataset_a",
                "/project/training_calibrations/dataset_a",
            ],
        )

    def test_delete_dataset_training_state_rejects_active_tasks(self):
        task_row = SimpleNamespace(
            id="task_running",
            to_dict=lambda: {"id": "task_running", "status": "running", "type": "training"},
        )
        session = _FakeSession(task_rows=[task_row])
        with patch(
            "contexts.training.infrastructure.workflow_repository.session_scope",
            return_value=_session_scope_factory(session),
        ):
            with self.assertRaisesRegex(ValueError, "进行中的训练相关任务"):
                delete_dataset_training_state("/project", "ds_1", dataset_name="dataset_a")

    def test_delete_dataset_related_state_removes_snapshot_tasks(self):
        snapshot_task_row = SimpleNamespace(
            id="task_snapshot",
            to_dict=lambda: {"id": "task_snapshot", "status": "completed", "type": "dataset_snapshot"},
        )
        workflow_row = SimpleNamespace(id="wf_any")
        session = _FakeSession(task_rows=[snapshot_task_row], workflow_rows=[workflow_row])

        with (
            patch(
                "contexts.training.infrastructure.workflow_repository.session_scope",
                return_value=_session_scope_factory(session),
            ),
            patch("contexts.training.infrastructure.workflow_repository.os.path.exists", return_value=False),
        ):
            result = delete_dataset_related_state("/project", "ds_1", dataset_name="dataset_a")

        self.assertEqual(result["removed_task_ids"], ["task_snapshot"])
        self.assertEqual(result["removed_workflow_ids"], ["wf_any"])
        self.assertEqual(result["removed_paths"], [])
        self.assertEqual(session.deleted, [snapshot_task_row, workflow_row])

    def test_delete_dataset_related_state_rejects_active_snapshot_tasks(self):
        snapshot_task_row = SimpleNamespace(
            id="task_snapshot",
            to_dict=lambda: {"id": "task_snapshot", "status": "running", "type": "dataset_snapshot"},
        )
        session = _FakeSession(task_rows=[snapshot_task_row])

        with patch(
            "contexts.training.infrastructure.workflow_repository.session_scope",
            return_value=_session_scope_factory(session),
        ):
            with self.assertRaisesRegex(ValueError, "进行中的关联任务"):
                delete_dataset_related_state("/project", "ds_1", dataset_name="dataset_a")


if __name__ == "__main__":
    unittest.main()
