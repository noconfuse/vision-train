"""回归：VISION_TRAIN_PROJECTS_DIR 带符号链接时，标注上下文仍拼出干净的相对路径。

macOS 上 /tmp 是 /private/tmp 的链接；目录扫描走 realpath、图片引用走 abspath，
两者相减会长出一串 ../，标签与候选被静默读成空，保存还会写到图片旁边。
"""

import os
import shutil
import tempfile
import unittest

from app.config import PROJECTS_DIR
from contexts.annotation.infrastructure.annotation_io import build_dataset_image_context
from shared.utils.path_utils import resolve_storage_path, storage_path_ref

PROJECT_NAME = "linkproj"
DATASET_NAME = "linkds"
IMAGE_NAME = "a.jpg"


def _write_fixture(root):
    dataset_root = os.path.join(root, PROJECT_NAME, "training", DATASET_NAME)
    images_dir = os.path.join(dataset_root, "train", "images")
    os.makedirs(images_dir)
    os.makedirs(os.path.join(dataset_root, "train", "labels"))
    os.makedirs(os.path.join(dataset_root, "auto_labels", "train"))
    with open(os.path.join(images_dir, IMAGE_NAME), "wb") as handle:
        handle.write(b"not-a-real-image")
    with open(os.path.join(dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
        handle.write("train: train/images\nval: train/images\nnc: 1\nnames:\n  0: person\n")
    with open(os.path.join(dataset_root, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
        handle.write('{"vision_task_type": "detect", "dataset_id": "vtlink000001"}')
    with open(os.path.join(dataset_root, "auto_labels", "train", "a.txt"), "w", encoding="utf-8") as handle:
        handle.write("0 0.5 0.5 0.2 0.2\n")
    return dataset_root, images_dir


class LinkResolvedPathTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = os.path.realpath(tempfile.mkdtemp(prefix="vt-path-link-"))
        self.dataset_root, self.images_dir = _write_fixture(self.temp_root)
        # 同一个目录的两种写法：带链接的那条是用户在 .env 里可能填的路径
        self.alias_root = os.path.join(os.path.dirname(self.temp_root), "vt-path-link-alias")
        if os.path.lexists(self.alias_root):
            os.unlink(self.alias_root)
        os.symlink(self.temp_root, self.alias_root)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        if os.path.islink(self.alias_root):
            os.unlink(self.alias_root)
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def _relpath_under(self, base):
        """把图片绝对路径换成指定根目录下的引用（可能是带链接的形态）。"""
        return os.path.join(base, PROJECT_NAME, "training", DATASET_NAME, "train", "images", IMAGE_NAME)

    def test_resolve_storage_path_returns_one_form(self):
        from_symlink = resolve_storage_path(self._relpath_under(self.alias_root))
        from_real = resolve_storage_path(self._relpath_under(self.temp_root))
        self.assertEqual(os.path.realpath(from_symlink), os.path.realpath(from_real))
        self.assertEqual(from_symlink, from_real)

    def test_projects_dir_is_canonical(self):
        self.assertEqual(PROJECTS_DIR, os.path.realpath(PROJECTS_DIR))

    def test_one_file_has_one_identity(self):
        """三种写法（引用 / 带链接绝对 / 真实绝对）必须归一到同一个回传引用。"""
        ref = f"projects/{PROJECT_NAME}/training/{DATASET_NAME}/train/images/{IMAGE_NAME}"
        self.assertEqual(storage_path_ref(ref), ref)
        from_symlink = storage_path_ref(self._relpath_under(self.alias_root))
        from_real = storage_path_ref(self._relpath_under(self.temp_root))
        self.assertEqual(from_symlink, from_real)
        self.assertEqual(from_symlink, os.path.realpath(self._relpath_under(self.temp_root)))

    def test_context_paths_stay_inside_the_dataset(self):
        for base in (self.alias_root, self.temp_root):
            image_path = self._relpath_under(base)
            context = build_dataset_image_context(self.dataset_root, "train", image_path, project_path=PROJECT_NAME)
            for key in ("relative_path", "relative_noext"):
                self.assertNotIn("..", context[key], f"{key} 逃出数据集: {context[key]}")
            self.assertEqual(
                context["manual_label_path"],
                os.path.join(self.dataset_root, "train", "labels", "a.txt"),
            )
            self.assertEqual(
                context["auto_label_path"],
                os.path.join(self.dataset_root, "auto_labels", "train", "a.txt"),
            )
            self.assertTrue(os.path.exists(context["auto_label_path"]), "候选文件存在却读不到路径")


if __name__ == "__main__":
    unittest.main()
