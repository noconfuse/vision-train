"""数据集稳定身份、版本快照与恢复流程的回归测试。

DVC 改造后：所有快照通过 DVC 内容寻址存储；测试通过 mock DVC 子进程，
验证元数据 / 恢复时 DVC checkout 是否被正确触发，以及工作区是否被回滚。
"""

import os
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from contexts.dataset.infrastructure import dvc_backend
from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml
from contexts.dataset.domain.capabilities import DATASET_OPERATION_SPLIT_DATASET, build_dataset_capabilities
from contexts.dataset.application.use_cases import create_subset, list_project_datasets, list_dataset_versions, split_dataset_use_case
from contexts.dataset.infrastructure.dataset_repository import analyze_dataset
from contexts.dataset.infrastructure.dataset_task_type import (
    load_dataset_identity_meta,
    save_dataset_vision_task_type,
)
from contexts.dataset.infrastructure.dataset_versioning import (
    create_dataset_version_snapshot,
    ensure_dataset_version_state,
    list_dataset_version_records,
    mark_dataset_initial_version_pending,
    restore_dataset_version_snapshot,
)
from contexts.dataset.infrastructure import dataset_versioning as versioning_mod
from contexts.project.infrastructure.project_paths import get_project_dataset_dir


def _fake_dvc_run(*args, **kwargs):
    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    return _Result()


def _fake_dvc_run_with_progress(*args, **kwargs):
    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    return _Result()


def _make_dvc_pointer(dataset_dir: str, fake_rev: str = "deadbeef"):
    dvc_file = f"{dataset_dir.rstrip(os.sep)}.dvc"
    payload = {"outs": [{"md5": fake_rev, "path": os.path.basename(dataset_dir.rstrip('/'))}]}
    import json
    with open(dvc_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return dvc_file


def _patch_dvc():
    stack = ExitStack()
    stack.enter_context(patch.object(dvc_backend, "_run_dvc", side_effect=_fake_dvc_run))
    stack.enter_context(patch.object(dvc_backend, "_run_dvc_with_progress", side_effect=_fake_dvc_run_with_progress))
    stack.enter_context(patch.object(dvc_backend, "_find_dvc_bin", return_value="/usr/bin/dvc"))
    return stack


class DatasetVersioningTests(unittest.TestCase):
    def setUp(self):
        self.project_path = tempfile.mkdtemp(prefix="vt_dataset_versioning_")
        self.dataset_name = "pose_demo"
        self.dataset_root = get_project_dataset_dir(self.project_path, self.dataset_name)
        os.makedirs(os.path.join(self.dataset_root, "train", "images"), exist_ok=True)
        os.makedirs(os.path.join(self.dataset_root, "train", "labels"), exist_ok=True)
        self.sample_image_path = os.path.join(self.dataset_root, "train", "images", "sample.jpg")
        with open(self.sample_image_path, "w", encoding="utf-8") as handle:
            handle.write("fake-image")
        self.sample_label_path = os.path.join(self.dataset_root, "train", "labels", "sample.txt")
        with open(self.sample_label_path, "w", encoding="utf-8") as handle:
            handle.write("0 0.5 0.5 0.25 0.25")
        self.image_marker = os.path.join(self.dataset_root, "train", "images", "sample.txt")
        with open(self.image_marker, "w", encoding="utf-8") as handle:
            handle.write("v1-image")
        save_standard_dataset_yaml(self.dataset_root, ["person"], vision_task_type="pose", include_test=False)
        save_dataset_vision_task_type(self.dataset_root, "pose")

    def tearDown(self):
        shutil.rmtree(self.project_path, ignore_errors=True)

    def test_publish_and_restore_dataset_versions(self):
        with _patch_dvc():
            with patch.object(versioning_mod, "dvc_get_current_rev", return_value="rev_v1"):
                first_version = create_dataset_version_snapshot(
                    self.project_path,
                    self.dataset_root,
                    dataset_name=self.dataset_name,
                    reason="import",
                    mode="add",
                )
        _make_dvc_pointer(self.dataset_root, fake_rev="rev_v1")

        identity = load_dataset_identity_meta(self.dataset_root)
        self.assertEqual(identity["dataset_id"], first_version["dataset_id"])
        self.assertEqual(identity["current_version_id"], first_version["version_id"])
        self.assertEqual(identity["versioning_status"], "ready")
        self.assertEqual(os.path.realpath(first_version["snapshot_path"]), os.path.realpath(self.dataset_root))
        self.assertEqual(first_version["dvc_rev"], "rev_v1")

        with open(self.image_marker, "w", encoding="utf-8") as handle:
            handle.write("v2-image")
        with _patch_dvc():
            with patch.object(versioning_mod, "dvc_get_current_rev", return_value="rev_v2"):
                second_version = create_dataset_version_snapshot(
                    self.project_path,
                    self.dataset_root,
                    dataset_name=self.dataset_name,
                    reason="manual_publish",
                    mode="commit",
                )
        _make_dvc_pointer(self.dataset_root, fake_rev="rev_v2")

        versions = list_dataset_version_records(self.project_path, identity["dataset_id"])
        self.assertEqual([item["version_id"] for item in versions], [second_version["version_id"], first_version["version_id"]])

        def _fake_checkout(project_path, dataset_root, rev):
            with open(self.image_marker, "w", encoding="utf-8") as handle:
                handle.write("v1-image")

        with _patch_dvc():
            with patch.object(versioning_mod, "dvc_checkout_dataset", side_effect=_fake_checkout):
                with patch.object(versioning_mod, "dvc_get_current_rev", return_value="rev_v1_reborn"):
                    restore_result = restore_dataset_version_snapshot(
                        self.project_path,
                        self.dataset_root,
                        first_version["version_id"],
                        dataset_name=self.dataset_name,
                    )
        _make_dvc_pointer(self.dataset_root, fake_rev="rev_v1_reborn")

        with open(self.image_marker, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "v1-image")
        restored_current = restore_result["current_version"]
        self.assertNotEqual(restored_current["version_id"], first_version["version_id"])
        self.assertEqual(restored_current["source_version_id"], first_version["version_id"])

    def test_snapshot_path_points_to_workspace_directory(self):
        with _patch_dvc():
            with patch.object(versioning_mod, "dvc_get_current_rev", return_value="rev_001"):
                version = create_dataset_version_snapshot(
                    self.project_path,
                    self.dataset_root,
                    dataset_name=self.dataset_name,
                    reason="import",
                    mode="add",
                )
        self.assertTrue(os.path.isdir(version["snapshot_path"]))
        self.assertEqual(os.path.realpath(version["snapshot_path"]), os.path.realpath(self.dataset_root))

    def test_old_dataset_without_current_version_is_bootstrapped_on_access(self):
        identity = load_dataset_identity_meta(self.dataset_root)
        self.assertIsNone(identity["current_version_id"])

        with _patch_dvc():
            with patch.object(versioning_mod, "dvc_get_current_rev", return_value="rev_bootstrap"):
                state = ensure_dataset_version_state(
                    self.project_path,
                    self.dataset_root,
                    dataset_name=self.dataset_name,
                )

        refreshed = load_dataset_identity_meta(self.dataset_root)
        self.assertEqual(refreshed["dataset_id"], state["dataset_id"])
        self.assertEqual(refreshed["current_version_id"], state["dataset_version_id"])
        self.assertEqual(refreshed["versioning_status"], "ready")
        self.assertEqual(os.path.realpath(state["snapshot_path"]), os.path.realpath(self.dataset_root))

    def test_loading_dataset_identity_meta_does_not_rewrite_complete_meta(self):
        original = load_dataset_identity_meta(self.dataset_root)

        with patch("contexts.dataset.infrastructure.dataset_task_type.save_dataset_task_meta") as mocked_save:
            loaded = load_dataset_identity_meta(self.dataset_root)

        self.assertEqual(loaded["dataset_id"], original["dataset_id"])
        self.assertEqual(loaded["vision_task_type"], original["vision_task_type"])
        mocked_save.assert_not_called()

    def test_pending_initial_snapshot_does_not_set_current_version_id(self):
        pending = mark_dataset_initial_version_pending(self.dataset_root)

        self.assertIsNone(pending["current_version_id"])
        self.assertEqual(pending["versioning_status"], "pending")

        result = list_dataset_versions(self.project_path, self.dataset_name)
        self.assertIsNone(result["current_version_id"])
        self.assertEqual(result["versioning_status"], "pending")
        self.assertEqual(result["versions"], [])

    def test_pending_initial_snapshot_blocks_bootstrap(self):
        mark_dataset_initial_version_pending(self.dataset_root)

        with self.assertRaisesRegex(ValueError, "首个版本仍在入库中"):
            ensure_dataset_version_state(
                self.project_path,
                self.dataset_root,
                dataset_name=self.dataset_name,
            )

    def test_pending_initial_snapshot_disables_capabilities_snapshot(self):
        metadata = mark_dataset_initial_version_pending(self.dataset_root)

        capabilities = build_dataset_capabilities("pose", dataset_metadata=metadata)

        self.assertFalse(capabilities["operations"][DATASET_OPERATION_SPLIT_DATASET])
        self.assertEqual(
            capabilities["operation_disabled_reasons"][DATASET_OPERATION_SPLIT_DATASET],
            "首个版本入库中，请等待快照完成",
        )
        analyzed = analyze_dataset(self.dataset_root)
        self.assertFalse(analyzed["capabilities"]["operations"]["train"])
        self.assertEqual(
            analyzed["capabilities"]["operation_disabled_reasons"]["train"],
            "首个版本入库中，请等待快照完成",
        )

    def test_pending_initial_snapshot_blocks_dataset_use_case_via_unified_capabilities(self):
        mark_dataset_initial_version_pending(self.dataset_root)

        with self.assertRaisesRegex(ValueError, "首个版本入库中，请等待快照完成"):
            split_dataset_use_case(self.project_path, self.dataset_name, val_ratio=0.1, test_ratio=0.0)

    def test_create_subset_enqueues_initial_snapshot_task(self):
        new_dataset_name = "pose_subset"

        def _fake_start_snapshot_job(project_path, dataset_root, **kwargs):
            del project_path, kwargs
            mark_dataset_initial_version_pending(dataset_root)
            return "task_subset_snapshot"

        with patch("contexts.dataset.application.use_cases.start_snapshot_job", side_effect=_fake_start_snapshot_job):
            result = create_subset(
                self.project_path,
                source_dataset=self.dataset_name,
                new_dataset_name=new_dataset_name,
                image_paths=[self.sample_image_path],
            )

        self.assertEqual(result["snapshot_task_id"], "task_subset_snapshot")
        self.assertEqual(result["versioning_status"], "pending")
        subset_root = get_project_dataset_dir(self.project_path, new_dataset_name)
        subset_identity = load_dataset_identity_meta(subset_root)
        self.assertIsNone(subset_identity["current_version_id"])
        self.assertEqual(subset_identity["versioning_status"], "pending")
        datasets = list_project_datasets(self.project_path)
        subset_summary = next(item for item in datasets if item["name"] == new_dataset_name)
        self.assertEqual(subset_summary["versioning_status"], "pending")


if __name__ == "__main__":
    unittest.main()
