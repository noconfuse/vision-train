"""待确认自动标注的逐框置信度与出处：标签文件与元信息文件必须成对存在、成对消失。"""

import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from contexts.annotation.infrastructure.annotation_task_strategy import (
    _sanitize_pose_instance,
    resolve_annotation_task_strategy,
)
from contexts.annotation.infrastructure.auto_annotation_store import (
    describe_auto_items,
    drop_auto_annotation,
)
from contexts.annotation.infrastructure.batch_helpers import extract_prediction_boxes
from contexts.dataset.infrastructure.dataset_layout import get_dataset_auto_meta_path
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT, VISION_TASK_TYPE_POSE, VISION_TASK_TYPE_SEGMENT


class _Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _TensorList:
    def __init__(self, value):
        self.value = value

    def __iter__(self):
        return iter(self.value)

    def __getitem__(self, index):
        return self.value[index]

    def __len__(self):
        return len(self.value)

    def tolist(self):
        return self.value


class _BoxTensor:
    """模拟 box.xyxy：取 [0] 再 tolist() 才拿到 [x1,y1,x2,y2]。"""

    def __init__(self, values):
        self.values = values

    def __getitem__(self, _index):
        return SimpleNamespace(tolist=lambda: self.values)


class DetectAutoAnnotationMetaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="vt-auto-meta-")
        self.image_path = os.path.join(self.temp_dir, "train", "images", "sample.jpg")
        self.manual_dir = os.path.join(self.temp_dir, "train", "labels")
        self.auto_dir = os.path.join(self.temp_dir, "auto_labels", "train")
        os.makedirs(os.path.dirname(self.image_path), exist_ok=True)
        os.makedirs(self.manual_dir, exist_ok=True)
        os.makedirs(self.auto_dir, exist_ok=True)
        with open(self.image_path, "wb") as handle:
            handle.write(b"not-a-real-image")
        with open(os.path.join(self.temp_dir, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
            handle.write('{"vision_task_type": "detect", "dataset_id": "auto_meta"}')
        self.auto_label_path = os.path.join(self.auto_dir, "sample.txt")
        self.context = {
            "dataset_root": self.temp_dir,
            "project_path": self.temp_dir,
            "split": "train",
            "image_path": self.image_path,
            "relative_noext": "sample",
            "manual_dir": self.manual_dir,
            "auto_dir": self.auto_dir,
            "manual_label_path": os.path.join(self.manual_dir, "sample.txt"),
            "auto_label_path": self.auto_label_path,
        }
        self.strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_DETECT)
        self.source = {"task_id": "auto-1", "model_name": "best.pt", "conf_thresh": 0.25, "engine": "ultralytics"}

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _meta_path(self):
        return get_dataset_auto_meta_path(self.auto_label_path, self.auto_dir)

    def test_save_writes_label_and_meta_paired_by_index(self):
        annotation = {"boxes": [
            {"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 60, "conf": 0.8123456},
            {"class": 1, "x1": 20, "y1": 20, "x2": 70, "y2": 90, "conf": 0.33},
        ]}
        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            self.strategy.save_auto_annotation(self.context, annotation, source=self.source)

            with open(self._meta_path(), encoding="utf-8") as handle:
                meta = json.load(handle)
            with open(self.auto_label_path, encoding="utf-8") as handle:
                label_lines = handle.read().strip().splitlines()

        self.assertEqual(len(label_lines), 2)
        self.assertEqual(meta["source"]["task_id"], "auto-1")
        self.assertEqual(meta["source"]["model_name"], "best.pt")
        self.assertEqual([item["conf"] for item in meta["items"]], [0.812346, 0.33])

    def test_payload_exposes_conf_and_source(self):
        annotation = {"boxes": [{"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 60, "conf": 0.62}]}
        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            self.strategy.save_auto_annotation(self.context, annotation, source=self.source)
            payload = self.strategy.get_annotation_payload(self.context)

        self.assertEqual(len(payload["auto_annotation"]["boxes"]), 1)
        self.assertAlmostEqual(payload["auto_annotation"]["boxes"][0]["conf"], 0.62, places=6)
        self.assertEqual(payload["auto_annotation"]["source"]["task_id"], "auto-1")
        self.assertEqual(payload["manual_annotation"]["boxes"], [])

    def test_missing_meta_is_reported_as_no_confidence_not_zero(self):
        # 补录前的历史批次只有标签文件：置信度必须照实为空，不能伪装成 0
        with open(self.auto_label_path, "w", encoding="utf-8") as handle:
            handle.write("0 0.3 0.3 0.4 0.4")
        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            payload = self.strategy.get_annotation_payload(self.context)

        self.assertIsNone(payload["auto_annotation"]["boxes"][0]["conf"])
        self.assertEqual(payload["auto_annotation"]["source"], {})

    def test_candidate_files_always_disappear_together(self):
        annotation = {"boxes": [{"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 60, "conf": 0.62}]}
        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            self.strategy.save_auto_annotation(self.context, annotation, source=self.source)

        drop_auto_annotation(self.context)

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertFalse(os.path.exists(self._meta_path()))

    def test_manual_save_at_strategy_level_leaves_the_candidates_for_the_review(self):
        # 「保存即审核」是用例层的事：策略层只写人工标签，不替人判定候选
        annotation = {"boxes": [{"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 60, "conf": 0.62}]}
        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            self.strategy.save_auto_annotation(self.context, annotation, source=self.source)
            self.strategy.save_manual_annotation(self.context, {"boxes": []})
            self.assertTrue(os.path.exists(self._meta_path()))
            self.assertTrue(os.path.exists(self.auto_label_path))
            payload = self.strategy.get_annotation_payload(self.context)
            self.assertEqual(len(payload["auto_annotation"]["boxes"]), 1)
            self.assertEqual(payload["manual_annotation"]["boxes"], [])


class OtherTaskTypeMetaTests(unittest.TestCase):
    def test_describe_auto_items_covers_every_payload_shape(self):
        self.assertEqual(
            describe_auto_items({"boxes": [{"conf": 0.5}, {"conf": None}]}),
            [{"conf": 0.5}, {"conf": None}],
        )
        self.assertEqual(
            describe_auto_items({"polygons": [{"class": 0, "points": [], "conf": 0.4}]}),
            [{"conf": 0.4}],
        )
        self.assertEqual(
            describe_auto_items({"instances": [{"class": 0, "keypoints": [], "conf": 0.9}]}),
            [{"conf": 0.9}],
        )
        self.assertEqual(describe_auto_items({"class_id": 2, "conf": 0.7}), [{"conf": 0.7}])
        self.assertEqual(describe_auto_items({}), [])
        self.assertEqual(describe_auto_items({"class_id": 2}), [{"conf": None}])

    def test_classify_payload_keeps_top1_confidence(self):
        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_CLASSIFY)
        prediction = SimpleNamespace(probs=SimpleNamespace(top1=1, top1conf=_Scalar(0.7654321)))
        self.assertEqual(strategy.extract_auto_annotation(prediction), {"class_id": 1, "conf": 0.765432})

    def test_pose_extract_keeps_box_confidence(self):
        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_POSE)
        prediction = SimpleNamespace(
            boxes=[
                SimpleNamespace(
                    xyxy=_TensorList([[10, 20, 50, 80]]),
                    cls=_Scalar(0),
                    conf=_Scalar(0.55),
                )
            ],
            keypoints=SimpleNamespace(
                data=_TensorList([[[12, 24, 0.9], [18, 36, 0.5], [30, 60, 0.7]]])
            ),
        )
        instances = strategy.extract_auto_annotation(prediction)["instances"]
        self.assertEqual(len(instances), 1)
        self.assertAlmostEqual(instances[0]["conf"], 0.55, places=6)

        cleaned = _sanitize_pose_instance(instances[0], 100, 100, 3)
        self.assertAlmostEqual(cleaned["conf"], 0.55, places=6)


class ExtractPredictionBoxesTests(unittest.TestCase):
    def test_confidence_survives_extraction(self):
        prediction = SimpleNamespace(
            boxes=[
                SimpleNamespace(
                    xyxy=_BoxTensor([1, 2, 30, 40]),
                    cls=_Scalar(2),
                    conf=_Scalar(0.4123456),
                )
            ]
        )
        boxes = extract_prediction_boxes(prediction)
        self.assertEqual(boxes[0]["class"], 2)
        self.assertAlmostEqual(boxes[0]["conf"], 0.412346, places=6)

    def test_box_without_confidence_stays_visible_as_unknown(self):
        prediction = SimpleNamespace(boxes=[SimpleNamespace(xyxy=_BoxTensor([1, 2, 30, 40]), cls=_Scalar(0))])
        boxes = extract_prediction_boxes(prediction)
        self.assertIsNone(boxes[0]["conf"])


if __name__ == "__main__":
    unittest.main()
