"""项目训练目录清点：只暴露合法数据集，解析失败或无协议的目录不展示。"""

import os
import shutil
import tempfile
import unittest

from contexts.dataset.application.use_cases import (
    create_empty_dataset,
    list_project_dataset_inventory,
    list_project_datasets,
)
from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml
from contexts.project.application.project_service import get_project_dataset_dir


class DatasetInventoryTests(unittest.TestCase):
    def setUp(self):
        self.project_path = tempfile.mkdtemp(prefix="vt_inventory_")

    def tearDown(self):
        shutil.rmtree(self.project_path, ignore_errors=True)

    def _make_broken_dataset(self, name):
        """造出只有 dataset.yaml、没有身份元数据的目录（旧抽帧导入留下的形态）。"""
        dataset_root = get_project_dataset_dir(self.project_path, name)
        os.makedirs(os.path.join(dataset_root, "train", "images"), exist_ok=True)
        save_standard_dataset_yaml(dataset_root, [], include_val=True, include_test=True)
        return dataset_root

    def test_broken_dir_is_skipped(self):
        create_empty_dataset(self.project_path, "good_set", "detect")
        self._make_broken_dataset("broken_set")
        # 完全没有 yaml 的目录不属于数据集协议，同样不出现
        os.makedirs(get_project_dataset_dir(self.project_path, "notes_only"), exist_ok=True)

        self.assertEqual(
            ["good_set"],
            [item["name"] for item in list_project_dataset_inventory(self.project_path)],
        )
        self.assertEqual(
            ["good_set"],
            [item["name"] for item in list_project_datasets(self.project_path)],
        )

    def test_clean_project_lists_its_dataset(self):
        create_empty_dataset(self.project_path, "only_set", "detect")
        self.assertEqual(
            ["only_set"],
            [item["name"] for item in list_project_dataset_inventory(self.project_path)],
        )


if __name__ == "__main__":
    unittest.main()
