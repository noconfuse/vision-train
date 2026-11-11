"""复用其他数据集类别表：同名跳过、非法名跳过、已有类别 id 不动。"""

import os
import shutil
import tempfile
import unittest

from contexts.dataset.application.use_cases import (
    add_dataset_label_use_case,
    copy_dataset_labels_use_case,
    create_empty_dataset,
    get_dataset_info,
)
from contexts.dataset.infrastructure.dataset_schema import load_dataset_yaml, save_dataset_names
from contexts.project.application.project_service import get_project_dataset_dir


class CopyDatasetLabelsTests(unittest.TestCase):
    def setUp(self):
        self.project_path = tempfile.mkdtemp(prefix="vt_copy_labels_")
        create_empty_dataset(self.project_path, "source_set", "detect", ["helmet", "vest", "hook"])
        create_empty_dataset(self.project_path, "target_set", "detect")

    def tearDown(self):
        shutil.rmtree(self.project_path, ignore_errors=True)

    def _names(self, dataset_name):
        return get_dataset_info(self.project_path, dataset_name)["names"]

    def test_copy_appends_source_classes_in_source_order(self):
        result = copy_dataset_labels_use_case(
            self.project_path, dataset_name="target_set", source_dataset_name="source_set"
        )

        self.assertEqual(["helmet", "vest", "hook"], result["added_labels"])
        self.assertEqual([], result["skipped_labels"])
        self.assertEqual(["helmet", "vest", "hook"], self._names("target_set"))
        self.assertEqual(3, result["nc"])

    def test_copy_keeps_existing_ids_and_skips_same_name(self):
        add_dataset_label_use_case(self.project_path, "target_set", "person")
        add_dataset_label_use_case(self.project_path, "target_set", "vest")

        result = copy_dataset_labels_use_case(
            self.project_path, dataset_name="target_set", source_dataset_name="source_set"
        )

        self.assertEqual(["helmet", "hook"], result["added_labels"])
        self.assertEqual(["vest"], result["skipped_labels"])
        # 已有的 person/vest 仍在原位，新增类别接在后面
        self.assertEqual(["person", "vest", "helmet", "hook"], self._names("target_set"))

    def test_copy_rejects_unknown_and_self_source(self):
        with self.assertRaises(ValueError):
            copy_dataset_labels_use_case(
                self.project_path, dataset_name="target_set", source_dataset_name="missing_set"
            )
        with self.assertRaises(ValueError):
            copy_dataset_labels_use_case(
                self.project_path, dataset_name="target_set", source_dataset_name="target_set"
            )

    def test_copy_rejects_source_without_classes(self):
        create_empty_dataset(self.project_path, "empty_set", "detect")

        with self.assertRaises(ValueError):
            copy_dataset_labels_use_case(
                self.project_path, dataset_name="target_set", source_dataset_name="empty_set"
            )
        self.assertEqual([], self._names("target_set"))

    def test_copy_skips_names_that_cannot_be_added(self):
        """外部导入的数据集常有带空格的类别名，这类跳过但不能让整批复用失败。"""
        self._set_source_names(["helmet", "traffic light"])

        result = copy_dataset_labels_use_case(
            self.project_path, dataset_name="target_set", source_dataset_name="source_set"
        )

        self.assertEqual(["helmet"], result["added_labels"])
        self.assertEqual(["traffic light"], result["invalid_labels"])
        self.assertEqual(["helmet"], self._names("target_set"))

    def _set_source_names(self, names):
        dataset_root = get_project_dataset_dir(self.project_path, "source_set")
        yaml_path = os.path.join(dataset_root, "dataset.yaml")
        save_dataset_names(yaml_path, load_dataset_yaml(dataset_root), names, original_is_dict=True)


if __name__ == "__main__":
    unittest.main()
