"""训练启动时绑定数据集快照版本的回归测试。"""

import unittest
from unittest.mock import patch

from contexts.training.infrastructure.execution_starters import start_training_task


class TrainingSnapshotBindingTests(unittest.TestCase):
    def test_start_training_task_persists_dataset_identity_and_version(self):
        training_context = {
            "dataset_id": "ds_001",
            "dataset_version_id": "ver_001",
            "dataset_path": "/project/training/.dataset-store/ds_001/versions/ver_001/snapshot",
            "data_yaml": "/project/training/.dataset-store/ds_001/versions/ver_001/snapshot/dataset.yaml",
            "data_ref": "/project/training/.dataset-store/ds_001/versions/ver_001/snapshot/dataset.yaml",
            "vision_task_type": "pose",
            "model_name": "yolo11n-pose.pt",
            "model_path": "/models/yolo11n-pose.pt",
            "training_mode": "yolo_pose",
            "training_profile": {"arg_specs": [], "supports_batch_calibration": True},
        }

        with (
            patch("contexts.training.infrastructure.execution_starters.normalize_training_config", return_value={"epochs": 1, "batch": 2}),
            patch("contexts.training.infrastructure.execution_starters.new_run_token", return_value="run_001"),
            patch("contexts.training.infrastructure.execution_starters.build_training_output_dir", return_value="/outputs/run_001"),
            patch(
                "contexts.training.infrastructure.execution_starters.build_worker_artifacts",
                return_value={"log_path": "/outputs/run_001/training-worker.log"},
            ),
            patch(
                "contexts.training.infrastructure.execution_starters.resolve_training_sources_context",
                return_value=training_context,
            ),
            patch(
                "contexts.training.infrastructure.execution_starters.ensure_training_workflow_record",
                return_value={"id": "wf_001"},
            ) as ensure_workflow,
            patch(
                "contexts.training.infrastructure.execution_starters.start_task",
                return_value={"id": "task_001"},
            ) as start_task_mock,
            patch("contexts.training.infrastructure.execution_starters.update_task_status", return_value={"id": "task_001"}),
            patch("contexts.training.infrastructure.execution_starters.touch_training_workflow_record") as touch_workflow,
            patch("contexts.training.infrastructure.execution_starters.start_worker_task", return_value={"task_id": "task_001", "workflow_id": "wf_001"}),
            patch("contexts.training.infrastructure.execution_starters.save_json_file"),
        ):
            result = start_training_task(
                project_path="/project",
                dataset_name="pose_demo",
                model_name="yolo11n-pose.pt",
                training_config={"epochs": 1, "batch": 2},
                workflow_id="wf_001",
            )

        self.assertEqual(result["workflow_id"], "wf_001")
        ensure_workflow.assert_called_once()
        self.assertEqual(ensure_workflow.call_args.kwargs["dataset_id"], "ds_001")
        self.assertEqual(ensure_workflow.call_args.kwargs["dataset_version_id"], "ver_001")
        start_task_mock.assert_called_once()
        self.assertEqual(start_task_mock.call_args.kwargs["dataset_id"], "ds_001")
        self.assertEqual(start_task_mock.call_args.kwargs["dataset_version_id"], "ver_001")
        self.assertEqual(start_task_mock.call_args.kwargs["dataset_path"], training_context["dataset_path"])
        touch_workflow.assert_called_once()
        self.assertEqual(touch_workflow.call_args.kwargs["dataset_id"], "ds_001")
        self.assertEqual(touch_workflow.call_args.kwargs["dataset_version_id"], "ver_001")


if __name__ == "__main__":
    unittest.main()
