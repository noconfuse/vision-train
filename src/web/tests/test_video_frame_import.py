"""抽帧图片导入数据集时的注册与首版快照回归测试。"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from contexts.dataset.application.use_cases import list_project_datasets
from contexts.dataset.infrastructure.dataset_task_type import DATASET_TASK_META_FILENAME
from contexts.project.application.project_service import get_project_dataset_dir, get_project_task_images_dir
from contexts.video.infrastructure.video_task_gateway import import_task_images


class VideoFrameImportTests(unittest.TestCase):
    def setUp(self):
        self.project_path = tempfile.mkdtemp(prefix="vt_frame_import_")
        self.task_id = "frame_task_1"
        self.images_dir = get_project_task_images_dir(self.project_path, self.task_id)
        os.makedirs(self.images_dir, exist_ok=True)
        for name in ("frame_1.jpg", "frame_2.jpg"):
            with open(os.path.join(self.images_dir, name), "w", encoding="utf-8") as handle:
                handle.write("frame")
        self.snapshot_calls = []

    def tearDown(self):
        shutil.rmtree(self.project_path, ignore_errors=True)

    def _fake_snapshot(self, project_path, dataset_root, **kwargs):
        self.snapshot_calls.append((dataset_root, kwargs.get("reason")))
        return "snapshot_task_1"

    def _import(self, dataset_name, **kwargs):
        with patch("contexts.video.infrastructure.video_task_gateway.load_task", return_value=None), \
                patch("contexts.dataset.application.use_cases.start_snapshot_job", side_effect=self._fake_snapshot):
            return import_task_images(self.project_path, self.task_id, dataset_name, **kwargs)

    def test_new_dataset_is_registered_and_visible(self):
        result = self._import("frames_01", vision_task_type="detect")

        self.assertEqual(2, result["imported_count"])
        self.assertEqual("snapshot_task_1", result["snapshot_task_id"])
        self.assertTrue(result["dataset_id"])
        self.assertEqual(1, len(self.snapshot_calls))
        self.assertEqual("frame_import", self.snapshot_calls[0][1])
        self.assertIn("frames_01", [item["name"] for item in list_project_datasets(self.project_path)])

        dataset_root = get_project_dataset_dir(self.project_path, "frames_01")
        meta_path = os.path.join(dataset_root, DATASET_TASK_META_FILENAME)
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual("detect", meta["vision_task_type"])
        self.assertEqual(
            {"frame_1.jpg", "frame_2.jpg"},
            set(os.listdir(os.path.join(dataset_root, "train", "images"))),
        )

    def test_existing_dataset_import_keeps_single_registration(self):
        created = self._import("frames_02", vision_task_type="detect")
        appended = self._import("frames_02")

        self.assertEqual(2, appended["imported_count"])
        self.assertEqual(created["dataset_id"], appended["dataset_id"])
        self.assertNotIn("snapshot_task_id", appended)
        self.assertEqual(1, len(self.snapshot_calls))

    def test_missing_dataset_without_task_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不存在"):
            self._import("frames_03")
        self.assertFalse(os.path.exists(get_project_dataset_dir(self.project_path, "frames_03")))
        self.assertEqual([], self.snapshot_calls)

    def test_half_registered_dataset_is_rejected(self):
        dataset_root = get_project_dataset_dir(self.project_path, "frames_04")
        os.makedirs(os.path.join(dataset_root, "train", "images"), exist_ok=True)
        with open(os.path.join(dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write("path: .\ntrain: train/images\nnames: []\n")

        with self.assertRaisesRegex(ValueError, "未完成注册"):
            self._import("frames_04")
        self.assertEqual([], os.listdir(os.path.join(dataset_root, "train", "images")))

    def test_unknown_task_type_does_not_leave_a_dataset(self):
        with self.assertRaises(ValueError):
            self._import("frames_05", vision_task_type="unknown")
        self.assertFalse(os.path.exists(get_project_dataset_dir(self.project_path, "frames_05")))


if __name__ == "__main__":
    unittest.main()
