"""姿态任务自动标注能力的回归测试。"""

import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from contexts.annotation.infrastructure.annotation_io import decode_pose_file
from contexts.annotation.infrastructure.annotation_task_strategy import resolve_annotation_task_strategy
from contexts.dataset.domain.capabilities import build_dataset_capabilities
from protocols.vision_task_type import VISION_TASK_TYPE_POSE


class _Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _TensorList:
    def __init__(self, value):
        self.value = value

    def tolist(self):
        return self.value


class PoseSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="vt_pose_support_")
        self.image_dir = os.path.join(self.temp_dir, "train", "images")
        self.manual_dir = os.path.join(self.temp_dir, "train", "labels")
        self.auto_dir = os.path.join(self.temp_dir, "auto_labels", "train")
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.manual_dir, exist_ok=True)
        os.makedirs(self.auto_dir, exist_ok=True)
        with open(os.path.join(self.temp_dir, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write(
                "\n".join(
                    [
                        "path: .",
                        "train: train/images",
                        "val: val/images",
                        "names:",
                        "  0: person",
                        "kpt_shape: [3, 3]",
                        "flip_idx: [0, 1, 2]",
                        "kpt_names:",
                        "  0: [nose, shoulder, hip]",
                    ]
                )
            )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pose_capabilities_enable_auto_annotation(self):
        dataset_capabilities = build_dataset_capabilities(VISION_TASK_TYPE_POSE)

        self.assertEqual(dataset_capabilities["annotation_mode"], "pose_keypoints")
        self.assertEqual(dataset_capabilities["training_mode"], "yolo_pose")
        self.assertEqual(dataset_capabilities["auto_annotation_mode"], "pose_keypoints")
        self.assertTrue(dataset_capabilities["operations"]["manual_annotation"])
        self.assertTrue(dataset_capabilities["operations"]["auto_annotate"])

    def test_pose_strategy_extracts_auto_instances(self):
        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_POSE)
        prediction = SimpleNamespace(
            boxes=[
                SimpleNamespace(
                    xyxy=_TensorList([[10, 20, 50, 80]]),
                    cls=_Scalar(1),
                )
            ],
            keypoints=SimpleNamespace(
                data=_TensorList(
                    [
                        [
                            [12, 24, 0.9],
                            [18, 36, 0.5],
                            [0, 0, 0.0],
                        ]
                    ]
                )
            ),
        )

        result = strategy.extract_auto_annotation(prediction)

        self.assertEqual(len(result["instances"]), 1)
        instance = result["instances"][0]
        self.assertEqual(instance["class"], 1)
        self.assertEqual((instance["x1"], instance["y1"], instance["x2"], instance["y2"]), (10.0, 20.0, 50.0, 80.0))
        self.assertEqual([point["visible"] for point in instance["keypoints"]], [2, 2, 0])

    def test_pose_strategy_saves_commits_and_filters_auto_instances(self):
        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_POSE)
        image_path = os.path.join(self.image_dir, "sample.jpg")
        manual_label_path = os.path.join(self.manual_dir, "sample.txt")
        auto_label_path = os.path.join(self.auto_dir, "sample.txt")
        with open(image_path, "wb") as handle:
            handle.write(b"not-a-real-image")

        context = {
            "image_path": image_path,
            "manual_label_path": manual_label_path,
            "auto_label_path": auto_label_path,
            "dataset_root": self.temp_dir,
            "split": "train",
            "relative_noext": "sample",
            "class_names": ["person"],
        }
        manual_instance = {
            "class": 0,
            "x1": 10,
            "y1": 10,
            "x2": 30,
            "y2": 30,
            "keypoints": [
                {"x": 12, "y": 12, "visible": 2},
                {"x": 20, "y": 20, "visible": 2},
                {"x": 28, "y": 28, "visible": 1},
            ],
        }
        candidate_instance = {
            "class": 0,
            "x1": 60,
            "y1": 60,
            "x2": 95,
            "y2": 95,
            "keypoints": [
                {"x": 62, "y": 62, "visible": 2},
                {"x": 82, "y": 82, "visible": 2},
                {"x": 120, "y": 120, "visible": 1},
            ],
        }

        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            strategy.save_manual_annotation(context, {"instances": [manual_instance]})
            refined = strategy.refine_auto_annotation(
                context,
                {"instances": [manual_instance, candidate_instance]},
                iou_thresh=0.5,
            )

            self.assertEqual(len(refined["instances"]), 1)
            self.assertEqual(refined["instances"][0]["x2"], 95.0)
            self.assertEqual(refined["instances"][0]["keypoints"][2]["x"], 100.0)
            self.assertEqual(refined["instances"][0]["keypoints"][2]["visible"], 1)

            strategy.save_auto_annotation(context, refined)
            pending = strategy.list_pending_auto_annotations(self.temp_dir, "train")
            self.assertEqual(len(pending["items"]), 1)
            payload = strategy.get_annotation_payload(context)
            self.assertEqual(len(payload["manual_annotation"]["instances"]), 1)
            self.assertEqual(len(payload["auto_annotation"]["instances"]), 1)

            strategy.commit_auto_annotation(context)
            merged = decode_pose_file(manual_label_path, 100, 100, kpt_shape=[3, 3])
            self.assertEqual(len(merged), 2)
            self.assertFalse(os.path.exists(auto_label_path))


if __name__ == "__main__":
    unittest.main()
