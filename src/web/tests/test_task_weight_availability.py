"""任务列表/详情里补的权重可用性：训练没跑完，只要 best.pt 已经写出，后续评估与导出就该放行。"""

import os
import tempfile
import unittest

from contexts.task.infrastructure.task_runtime import attach_training_weight_info
from protocols.task_artifact_keys import ARTIFACT_BEST_WEIGHT_PATH, ARTIFACT_LAST_WEIGHT_PATH
from protocols.task_status import TASK_STATUS_INTERRUPTED
from protocols.task_type import TASK_TYPE_EVALUATE, TASK_TYPE_TRAINING


def _training_task(weight_files):
    root = tempfile.mkdtemp(prefix="vt-weight-")
    artifacts = {}
    for name in ("best.pt", "last.pt"):
        key = ARTIFACT_BEST_WEIGHT_PATH if name == "best.pt" else ARTIFACT_LAST_WEIGHT_PATH
        path = os.path.join(root, "weights", name)
        if name in weight_files:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(b"0")
        artifacts[key] = path
    return {
        "id": "t1",
        "type": TASK_TYPE_TRAINING,
        "status": TASK_STATUS_INTERRUPTED,
        "artifacts": artifacts,
    }


class AttachTrainingWeightInfoTests(unittest.TestCase):
    def test_interrupted_run_with_best_weight_is_usable_downstream(self):
        enriched = attach_training_weight_info(_training_task(("best.pt", "last.pt")))
        self.assertTrue(enriched["best_weight_ready"])
        self.assertTrue(enriched["resume_available"])
        self.assertEqual("last.pt", enriched["resume_weight"])

    def test_run_with_only_last_weight_still_can_resume_but_not_evaluate(self):
        enriched = attach_training_weight_info(_training_task(("last.pt",)))
        self.assertFalse(enriched["best_weight_ready"])
        self.assertTrue(enriched["resume_available"])

    def test_run_without_any_weight_reports_both_closed(self):
        enriched = attach_training_weight_info(_training_task(()))
        self.assertFalse(enriched["best_weight_ready"])
        self.assertFalse(enriched["resume_available"])

    def test_non_training_task_gets_no_weight_fields(self):
        task = {"id": "e1", "type": TASK_TYPE_EVALUATE, "artifacts": {}}
        self.assertIs(task, attach_training_weight_info(task))


if __name__ == "__main__":
    unittest.main()
