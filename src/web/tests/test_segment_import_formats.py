"""分割数据集导入格式的回归测试。"""

import base64
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from contexts.dataset.infrastructure.dataset_format_detector import detect_dataset_format
from contexts.dataset.infrastructure.dataset_import_yolo import ensure_dataset_yaml, normalize_yolo_layout
from contexts.dataset.infrastructure.dataset_import_formats import convert_coco_to_yolo_segment
from contexts.dataset.infrastructure.dataset_schema import find_dataset_config, load_dataset_yaml

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def _make_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PNG_1X1)


class SegmentImportFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vt_segment_import_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_and_convert_coco_segment_dataset(self):
        source_root = self.temp_dir / "coco_segment"
        annotations_dir = source_root / "annotations"
        annotations_dir.mkdir(parents=True, exist_ok=True)
        _make_image(source_root / "train" / "sample.jpg")
        _make_image(source_root / "val" / "sample.jpg")

        annotation = {
            "images": [
                {"id": 1, "file_name": "sample.jpg", "width": 100, "height": 100},
            ],
            "annotations": [
                {
                    "id": 1,
                    "image_id": 1,
                    "category_id": 3,
                    "bbox": [10, 10, 20, 20],
                    "area": 400,
                    "iscrowd": 0,
                    "segmentation": [[10, 10, 30, 10, 30, 30, 10, 30]],
                },
            ],
            "categories": [
                {"id": 3, "name": "fish"},
            ],
        }
        (annotations_dir / "instances_train.json").write_text(json.dumps(annotation), encoding="utf-8")
        (annotations_dir / "instances_val.json").write_text(json.dumps(annotation), encoding="utf-8")

        self.assertEqual(detect_dataset_format(str(source_root), vision_task_type="segment"), "coco")

        output_root = self.temp_dir / "segment_output"
        convert_coco_to_yolo_segment(str(source_root), str(output_root))

        dataset_yaml = load_dataset_yaml(str(output_root))
        self.assertEqual(dataset_yaml.get("train"), "train/images")
        self.assertEqual(dataset_yaml.get("val"), "val/images")
        self.assertEqual(dataset_yaml.get("names"), {0: "fish"})

        label_text = (output_root / "train" / "labels" / "sample.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(
            label_text,
            "0 0.100000 0.100000 0.300000 0.100000 0.300000 0.300000 0.100000 0.300000",
        )

    def test_detect_yolo_segment_dataset_with_custom_yaml_name(self):
        source_root = self.temp_dir / "crack_seg"
        _make_image(source_root / "images" / "train" / "sample.jpg")
        _make_image(source_root / "images" / "val" / "sample.jpg")
        (source_root / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "val").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "train" / "sample.txt").write_text(
            "0 0.100000 0.100000 0.300000 0.100000 0.300000 0.300000 0.100000 0.300000\n",
            encoding="utf-8",
        )
        (source_root / "labels" / "val" / "sample.txt").write_text(
            "0 0.100000 0.100000 0.300000 0.100000 0.300000 0.300000 0.100000 0.300000\n",
            encoding="utf-8",
        )
        (source_root / "crack-seg.yaml").write_text(
            "\n".join(
                [
                    "path: crack_seg",
                    "train: images/train",
                    "val: images/val",
                    "names:",
                    "  0: crack",
                ]
            ),
            encoding="utf-8",
        )

        self.assertEqual(detect_dataset_format(str(source_root), vision_task_type="segment"), "yolo")
        self.assertTrue(str(find_dataset_config(str(source_root))).endswith("crack-seg.yaml"))

        normalize_yolo_layout(str(source_root))
        ensure_dataset_yaml(str(source_root), force=True)

        dataset_yaml = load_dataset_yaml(str(source_root))
        self.assertEqual(dataset_yaml.get("path"), ".")
        self.assertEqual(dataset_yaml.get("train"), "train/images")
        self.assertEqual(dataset_yaml.get("val"), "val/images")
        self.assertEqual(dataset_yaml.get("names"), {0: "crack"})
        self.assertFalse((source_root / "crack-seg.yaml").exists())
        self.assertTrue((source_root / "dataset.yaml").is_file())

    def test_detect_yolo_segment_dataset_with_renamed_import_root(self):
        source_root = self.temp_dir / "renamed_target"
        _make_image(source_root / "images" / "train" / "sample.jpg")
        _make_image(source_root / "images" / "val" / "sample.jpg")
        (source_root / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "val").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "train" / "sample.txt").write_text(
            "0 0.100000 0.100000 0.300000 0.100000 0.300000 0.300000 0.100000 0.300000\n",
            encoding="utf-8",
        )
        (source_root / "labels" / "val" / "sample.txt").write_text(
            "0 0.100000 0.100000 0.300000 0.100000 0.300000 0.300000 0.100000 0.300000\n",
            encoding="utf-8",
        )
        (source_root / "crack-seg.yaml").write_text(
            "\n".join(
                [
                    "path: crack-seg",
                    "train: images/train",
                    "val: images/val",
                    "test: images/test",
                    "names:",
                    "  0: crack",
                ]
            ),
            encoding="utf-8",
        )
        _make_image(source_root / "images" / "test" / "sample.jpg")
        (source_root / "labels" / "test").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "test" / "sample.txt").write_text(
            "0 0.100000 0.100000 0.300000 0.100000 0.300000 0.300000 0.100000 0.300000\n",
            encoding="utf-8",
        )

        self.assertEqual(detect_dataset_format(str(source_root), vision_task_type="segment"), "yolo")

        normalize_yolo_layout(str(source_root))
        ensure_dataset_yaml(str(source_root), force=True)

        dataset_yaml = load_dataset_yaml(str(source_root))
        self.assertEqual(dataset_yaml.get("path"), ".")
        self.assertEqual(dataset_yaml.get("train"), "train/images")
        self.assertEqual(dataset_yaml.get("val"), "val/images")
        self.assertEqual(dataset_yaml.get("test"), "test/images")
        self.assertEqual(dataset_yaml.get("names"), {0: "crack"})


if __name__ == "__main__":
    unittest.main()
