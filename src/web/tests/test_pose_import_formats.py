"""姿态数据集导入格式的回归测试。"""

import base64
import shutil
import tempfile
import unittest
from pathlib import Path

from contexts.dataset.infrastructure.dataset_import_strategy import resolve_dataset_import_strategy
from contexts.dataset.infrastructure.dataset_import_yolo import (
    build_pose_dataset_yaml_fields,
    ensure_dataset_yaml,
    normalize_external_yolo_source_layout,
    normalize_yolo_layout,
)
from contexts.dataset.infrastructure.dataset_schema import find_dataset_config, load_dataset_yaml

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def _make_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PNG_1X1)


def _build_pose_line(keypoint_count=17, dims=3, visibility_values=None):
    parts = ["0", "0.5", "0.5", "0.4", "0.4"]
    for index in range(keypoint_count):
        x = 0.1 + index * 0.01
        y = 0.2 + index * 0.01
        parts.extend([f"{x:.6f}", f"{y:.6f}"])
        if dims == 3:
            visible = visibility_values[index] if visibility_values and index < len(visibility_values) else 2
            parts.append(str(visible))
    return " ".join(parts) + "\n"


class PoseImportFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vt_pose_import_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_yolo_pose_without_yaml_via_strategy_and_generate_pose_yaml(self):
        source_root = self.temp_dir / "pose_without_yaml"
        _make_image(source_root / "images" / "train" / "sample.jpg")
        _make_image(source_root / "images" / "val" / "sample.jpg")
        (source_root / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "val").mkdir(parents=True, exist_ok=True)
        pose_line = _build_pose_line()
        (source_root / "labels" / "train" / "sample.txt").write_text(pose_line, encoding="utf-8")
        (source_root / "labels" / "val" / "sample.txt").write_text(pose_line, encoding="utf-8")

        strategy = resolve_dataset_import_strategy("pose")
        self.assertEqual(strategy.detect_source_format(str(source_root)), "yolo")

        normalize_external_yolo_source_layout(str(source_root))
        ensure_dataset_yaml(
            str(source_root),
            force=True,
            extra_yaml_builder=lambda config, dataset_root, split_pairs, normalized_names: build_pose_dataset_yaml_fields(
                config,
                dataset_root,
                split_pairs,
                normalized_names,
            ),
        )

        dataset_yaml = load_dataset_yaml(str(source_root))
        self.assertEqual(dataset_yaml.get("path"), ".")
        self.assertEqual(dataset_yaml.get("train"), "train/images")
        self.assertEqual(dataset_yaml.get("val"), "val/images")
        self.assertEqual(dataset_yaml.get("kpt_shape"), [17, 3])
        self.assertEqual(dataset_yaml.get("flip_idx"), list(range(17)))
        self.assertEqual(dataset_yaml.get("names"), {0: "class_0"})
        self.assertEqual(
            dataset_yaml.get("kpt_names"),
            {0: [f"kpt_{index}" for index in range(17)]},
        )

    def test_strategy_can_import_yolo_pose_source_without_name_error(self):
        source_root = self.temp_dir / "pose_strategy_import"
        dest_root = self.temp_dir / "pose_strategy_import_out"
        _make_image(source_root / "images" / "train" / "sample.jpg")
        _make_image(source_root / "images" / "val" / "sample.jpg")
        (source_root / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "val").mkdir(parents=True, exist_ok=True)
        pose_line = _build_pose_line()
        (source_root / "labels" / "train" / "sample.txt").write_text(pose_line, encoding="utf-8")
        (source_root / "labels" / "val" / "sample.txt").write_text(pose_line, encoding="utf-8")

        strategy = resolve_dataset_import_strategy("pose")
        strategy.import_detected_format(
            "yolo",
            str(source_root),
            str(dest_root),
            {"id": "job_pose_import_test"},
            progress_lock=None,
        )

        dataset_yaml = load_dataset_yaml(str(dest_root))
        self.assertEqual(dataset_yaml.get("kpt_shape"), [17, 3])
        self.assertTrue((dest_root / "train" / "images" / "sample.jpg").is_file())

    def test_preserve_pose_metadata_from_custom_yaml_name(self):
        source_root = self.temp_dir / "pose_with_yaml"
        _make_image(source_root / "images" / "train" / "sample.jpg")
        _make_image(source_root / "images" / "val" / "sample.jpg")
        (source_root / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (source_root / "labels" / "val").mkdir(parents=True, exist_ok=True)
        pose_line = _build_pose_line()
        (source_root / "labels" / "train" / "sample.txt").write_text(pose_line, encoding="utf-8")
        (source_root / "labels" / "val" / "sample.txt").write_text(pose_line, encoding="utf-8")
        (source_root / "coco8-pose.yaml").write_text(
            "\n".join(
                [
                    "path: coco8-pose",
                    "train: images/train",
                    "val: images/val",
                    "kpt_shape: [17, 3]",
                    "flip_idx: [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]",
                    "skeleton:",
                    "  - [16, 14]",
                    "  - [14, 12]",
                    "  - [17, 15]",
                    "  - [15, 13]",
                    "names:",
                    "  0: person",
                    "kpt_names:",
                    "  0:",
                    "    - nose",
                    "    - left_eye",
                    "    - right_eye",
                    "    - left_ear",
                    "    - right_ear",
                    "    - left_shoulder",
                    "    - right_shoulder",
                    "    - left_elbow",
                    "    - right_elbow",
                    "    - left_wrist",
                    "    - right_wrist",
                    "    - left_hip",
                    "    - right_hip",
                    "    - left_knee",
                    "    - right_knee",
                    "    - left_ankle",
                    "    - right_ankle",
                ]
            ),
            encoding="utf-8",
        )

        strategy = resolve_dataset_import_strategy("pose")
        self.assertEqual(strategy.detect_source_format(str(source_root)), "yolo")
        self.assertTrue(str(find_dataset_config(str(source_root))).endswith("coco8-pose.yaml"))

        normalize_yolo_layout(str(source_root))
        ensure_dataset_yaml(
            str(source_root),
            force=True,
            extra_yaml_builder=lambda config, dataset_root, split_pairs, normalized_names: build_pose_dataset_yaml_fields(
                config,
                dataset_root,
                split_pairs,
                normalized_names,
            ),
        )

        dataset_yaml = load_dataset_yaml(str(source_root))
        self.assertEqual(dataset_yaml.get("path"), ".")
        self.assertEqual(dataset_yaml.get("train"), "train/images")
        self.assertEqual(dataset_yaml.get("val"), "val/images")
        self.assertEqual(dataset_yaml.get("names"), {0: "person"})
        self.assertEqual(dataset_yaml.get("kpt_shape"), [17, 3])
        self.assertEqual(dataset_yaml.get("flip_idx"), [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15])
        self.assertEqual(dataset_yaml.get("skeleton"), [[15, 13], [13, 11], [16, 14], [14, 12]])
        self.assertEqual(
            dataset_yaml.get("kpt_names"),
            {
                0: [
                    "nose",
                    "left_eye",
                    "right_eye",
                    "left_ear",
                    "right_ear",
                    "left_shoulder",
                    "right_shoulder",
                    "left_elbow",
                    "right_elbow",
                    "left_wrist",
                    "right_wrist",
                    "left_hip",
                    "right_hip",
                    "left_knee",
                    "right_knee",
                    "left_ankle",
                    "right_ankle",
                ]
            },
        )
        self.assertFalse((source_root / "coco8-pose.yaml").exists())
        self.assertTrue((source_root / "dataset.yaml").is_file())

if __name__ == "__main__":
    unittest.main()
