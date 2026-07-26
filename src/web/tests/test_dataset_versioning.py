"""数据集稳定身份、版本快照与恢复流程的回归测试。"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_identity_meta, save_dataset_vision_task_type
from contexts.dataset.infrastructure.dataset_versioning import (
    create_dataset_version_snapshot,
    ensure_dataset_version_state,
    list_dataset_version_records,
    restore_dataset_version_snapshot,
)
from contexts.project.infrastructure.project_paths import get_project_dataset_dir
from contexts.training.infrastructure.execution_context import resolve_training_sources_context


class DatasetVersioningTests(unittest.TestCase):
    def setUp(self):
        self.project_path = tempfile.mkdtemp(prefix="vt_dataset_versioning_")
        self.dataset_name = "pose_demo"
        self.dataset_root = get_project_dataset_dir(self.project_path, self.dataset_name)
        os.makedirs(os.path.join(self.dataset_root, "train", "images"), exist_ok=True)
        os.makedirs(os.path.join(self.dataset_root, "train", "labels"), exist_ok=True)
        with open(os.path.join(self.dataset_root, "train", "images", "sample.txt"), "w", encoding="utf-8") as handle:
            handle.write("v1-image")
        save_standard_dataset_yaml(self.dataset_root, ["person"], vision_task_type="pose", include_test=False)
        save_dataset_vision_task_type(self.dataset_root, "pose")

    def tearDown(self):
        shutil.rmtree(self.project_path, ignore_errors=True)

    def test_publish_and_restore_dataset_versions(self):
        first_version = create_dataset_version_snapshot(self.project_path, self.dataset_root, dataset_name=self.dataset_name, reason="import")
        identity = load_dataset_identity_meta(self.dataset_root)

        self.assertEqual(identity["dataset_id"], first_version["dataset_id"])
        self.assertEqual(identity["current_version_id"], first_version["version_id"])
        self.assertTrue(os.path.isdir(first_version["snapshot_path"]))

        with open(os.path.join(self.dataset_root, "train", "images", "sample.txt"), "w", encoding="utf-8") as handle:
            handle.write("v2-image")
        second_version = create_dataset_version_snapshot(self.project_path, self.dataset_root, dataset_name=self.dataset_name, reason="manual_publish")

        versions = list_dataset_version_records(self.project_path, identity["dataset_id"])
        self.assertEqual([item["version_id"] for item in versions], [second_version["version_id"], first_version["version_id"]])

        restore_result = restore_dataset_version_snapshot(
            self.project_path,
            self.dataset_root,
            first_version["version_id"],
            dataset_name=self.dataset_name,
        )
        with open(os.path.join(self.dataset_root, "train", "images", "sample.txt"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "v1-image")
        restored_current_version = restore_result["current_version"]
        self.assertNotEqual(restored_current_version["version_id"], first_version["version_id"])
        self.assertEqual(restored_current_version["source_version_id"], first_version["version_id"])

    def test_training_sources_context_uses_snapshot_instead_of_live_dataset(self):
        version = create_dataset_version_snapshot(self.project_path, self.dataset_root, dataset_name=self.dataset_name, reason="import")
        live_marker = os.path.join(self.dataset_root, "train", "images", "sample.txt")
        with open(live_marker, "w", encoding="utf-8") as handle:
            handle.write("mutated-after-snapshot")

        with (
            patch(
                "contexts.training.infrastructure.execution_context.resolve_training_capability_context",
                return_value={
                    "vision_task_type": "pose",
                    "dataset_capabilities": {},
                    "training_mode": "yolo_pose",
                    "training_profile": {"supports_batch_calibration": True, "arg_specs": []},
                },
            ),
            patch(
                "contexts.training.infrastructure.execution_context.resolve_training_model_context",
                return_value={
                    "model_name": "yolo11n-pose.pt",
                    "model_path": os.path.join(self.project_path, "dummy-model.pt"),
                    "model_vision_task_type": "pose",
                    "model_capabilities": {},
                },
            ),
        ):
            context = resolve_training_sources_context(self.project_path, self.dataset_name, "yolo11n-pose.pt", None)

        self.assertEqual(context["dataset_id"], version["dataset_id"])
        self.assertEqual(context["dataset_version_id"], version["version_id"])
        self.assertEqual(os.path.realpath(context["source_dataset_path"]), os.path.realpath(self.dataset_root))
        self.assertEqual(os.path.realpath(context["dataset_path"]), os.path.realpath(version["snapshot_path"]))
        self.assertTrue(context["data_yaml"].startswith(version["snapshot_path"]))
        with open(os.path.join(context["dataset_path"], "train", "images", "sample.txt"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "v1-image")

    def test_old_dataset_without_current_version_is_bootstrapped_on_access(self):
        identity = load_dataset_identity_meta(self.dataset_root)
        self.assertIsNone(identity["current_version_id"])

        state = ensure_dataset_version_state(self.project_path, self.dataset_root, dataset_name=self.dataset_name)
        refreshed = load_dataset_identity_meta(self.dataset_root)

        self.assertEqual(refreshed["dataset_id"], state["dataset_id"])
        self.assertEqual(refreshed["current_version_id"], state["dataset_version_id"])
        self.assertTrue(os.path.isdir(state["snapshot_path"]))

    def test_loading_dataset_identity_meta_does_not_rewrite_complete_meta(self):
        original = load_dataset_identity_meta(self.dataset_root)

        with patch("contexts.dataset.infrastructure.dataset_task_type.save_dataset_task_meta") as mocked_save:
            loaded = load_dataset_identity_meta(self.dataset_root)

        self.assertEqual(loaded["dataset_id"], original["dataset_id"])
        self.assertEqual(loaded["vision_task_type"], original["vision_task_type"])
        mocked_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
