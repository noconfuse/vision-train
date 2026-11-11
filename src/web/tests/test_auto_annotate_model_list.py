"""自动标注的候选模型列表：自己训出来的权重必须能被选到，已归档的不能。"""

import os
import shutil
import tempfile
import unittest

from contexts.model.infrastructure.model_gateway import scan_models
from protocols.task_type import TASK_TYPE_TRAINING
from db import session_scope
from db.models import Task, WorkflowRecord
from db.session import init_db


class AutoAnnotateModelListTests(unittest.TestCase):
    def setUp(self):
        init_db()
        # 真实路径建夹具：接口回的是归一后的引用，夹具跟着同一形态才对得上
        self.workspace = os.path.realpath(tempfile.mkdtemp(prefix="vt_model_list_"))
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.addCleanup(self._purge_rows)
        self.project_path = os.path.join(self.workspace, "alpha")
        weight = os.path.join(self.project_path, "training_outputs", "ds_a", "run_1", "weights", "best.pt")
        os.makedirs(os.path.dirname(weight), exist_ok=True)
        with open(weight, "wb") as handle:
            handle.write(b"fake-weights")
        self.weight_path = weight
        with session_scope() as session:
            session.add(
                WorkflowRecord(
                    id="wf_a1",
                    type="training",
                    project_path=self.project_path,
                    project_name="alpha",
                    dataset_name="ds_a",
                    dataset_id="ds_a_id",
                    vision_task_type="detect",
                )
            )
            session.add(
                Task(
                    id="tk_a1",
                    type=TASK_TYPE_TRAINING,
                    workflow_id="wf_a1",
                    project_path=self.project_path,
                    project_name="alpha",
                    dataset_name="ds_a",
                    dataset_id="ds_a_id",
                    vision_task_type="detect",
                    status="completed",
                    artifacts={"best_weight_path": weight},
                )
            )

    def _purge_rows(self):
        with session_scope() as session:
            for model in (Task, WorkflowRecord):
                row = session.get(model, "tk_a1" if model is Task else "wf_a1")
                if row:
                    session.delete(row)

    def _trained_paths(self):
        models = scan_models(self.project_path, usage="auto_annotate")
        return {item["path"] for item in models if item.get("type") == "trained"}

    def test_trained_weight_from_project_workflows_is_selectable(self):
        self.assertIn(self.weight_path, self._trained_paths())

    def test_archived_workflow_weight_is_not_offered(self):
        with session_scope() as session:
            session.get(WorkflowRecord, "wf_a1").archived_at = "2026-11-02T14:12:08"
        self.assertNotIn(self.weight_path, self._trained_paths())


if __name__ == "__main__":
    unittest.main()
