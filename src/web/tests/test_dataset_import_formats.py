"""分类原始数据集导入格式的回归测试。"""

import base64
import shutil
import tempfile
import unittest
from pathlib import Path

from contexts.dataset.infrastructure.dataset_format_detector import detect_dataset_format
from contexts.dataset.infrastructure.dataset_import_formats import (
    convert_classification_imagefolder_to_yolo,
)
from contexts.dataset.infrastructure.dataset_schema import load_dataset_yaml

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def _make_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PNG_1X1)


class ClassificationImportFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vt_import_test_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_and_convert_imagefolder_dataset(self):
        source_root = self.temp_dir / "flower_photos"
        _make_image(source_root / "roses" / "rose_a.jpg")
        _make_image(source_root / "daisy" / "daisy_a.jpg")

        self.assertEqual(detect_dataset_format(str(source_root), vision_task_type="classify"), "classification_imagefolder")

        output_root = self.temp_dir / "flower_output"
        convert_classification_imagefolder_to_yolo(str(source_root), str(output_root))

        dataset_yaml = load_dataset_yaml(str(output_root))
        self.assertEqual(dataset_yaml.get("train"), "train")
        self.assertEqual(dataset_yaml.get("val"), "train")
        self.assertEqual(dataset_yaml.get("names"), {0: "daisy", 1: "roses"})
        self.assertTrue((output_root / "train" / "roses" / "rose_a.jpg").is_file())

    def test_detect_and_convert_imagefolder_split_dataset(self):
        source_root = self.temp_dir / "imagenette_like"
        _make_image(source_root / "train" / "tench" / "tench_a.jpg")
        _make_image(source_root / "train" / "cassette_player" / "cassette_player_a.jpg")
        _make_image(source_root / "val" / "tench" / "tench_b.jpg")
        _make_image(source_root / "val" / "cassette_player" / "cassette_player_b.jpg")

        self.assertEqual(detect_dataset_format(str(source_root), vision_task_type="classify"), "classification_imagefolder")

        output_root = self.temp_dir / "imagenette_output"
        convert_classification_imagefolder_to_yolo(str(source_root), str(output_root))

        dataset_yaml = load_dataset_yaml(str(output_root))
        self.assertEqual(dataset_yaml.get("train"), "train")
        self.assertEqual(dataset_yaml.get("val"), "val")
        self.assertEqual(dataset_yaml.get("names"), {0: "cassette_player", 1: "tench"})
        self.assertTrue((output_root / "val" / "tench" / "tench_b.jpg").is_file())

    def test_detect_imagefolder_dataset_with_avif_images(self):
        source_root = self.temp_dir / "avif_dataset"
        _make_image(source_root / "cat" / "cat_a.avif")
        _make_image(source_root / "dog" / "dog_a.avif")

        self.assertEqual(
            detect_dataset_format(str(source_root), vision_task_type="classify"),
            "classification_imagefolder",
        )

if __name__ == "__main__":
    unittest.main()
