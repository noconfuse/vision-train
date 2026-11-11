"""类别对齐校验：模型类别与数据集类别对不上时，推理结果连候选都进不了。"""

import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from contexts.annotation.domain.class_alignment import (
    class_ids_from_annotation,
    class_ids_from_label_lines,
    normalize_model_names,
    require_auto_classes_writable,
    require_label_classes_writable,
)
from contexts.annotation.infrastructure.annotation_task_strategy import resolve_annotation_task_strategy
from contexts.annotation.infrastructure.auto_annotation_runner import auto_annotate_image
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT


class ClassAlignmentDomainTests(unittest.TestCase):
    def test_out_of_range_class_is_rejected_with_dataset_table(self):
        with self.assertRaises(ValueError) as ctx:
            require_auto_classes_writable(
                {i: name for i, name in enumerate(["person", "bicycle", "car"])},
                ["buffalo", "elephant", "rhino", "zebra"],
                [19],
            )
        message = str(ctx.exception)
        self.assertIn("19", message)
        self.assertIn("buffalo", message)

    def test_same_id_different_meaning_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            require_auto_classes_writable(
                {0: "elephant", 1: "zebra"},
                ["zebra", "elephant"],
                [0],
            )
        self.assertIn("模型叫「elephant」", str(ctx.exception))

    def test_aligned_subset_passes_without_renaming(self):
        require_auto_classes_writable(
            {0: "person", 1: "bicycle", 5: "elephant"},
            ["person", "helmet"],
            [0],
        )

    def test_model_without_names_blocks_instead_of_guessing(self):
        with self.assertRaises(ValueError):
            require_auto_classes_writable({}, ["person"], [0])

    def test_dataset_without_class_table_blocks_inference_write(self):
        with self.assertRaises(ValueError):
            require_auto_classes_writable({0: "person"}, [], [0])

    def test_empty_candidates_need_no_check(self):
        require_auto_classes_writable({}, ["person"], [])

    def test_class_ids_collected_across_task_shapes(self):
        self.assertEqual(
            class_ids_from_annotation(
                {
                    "boxes": [{"class": 2}, {"class": 0}],
                    "polygons": [{"class": 5}],
                    "instances": [{"class": 2}],
                },
                VISION_TASK_TYPE_DETECT,
            ),
            [0, 2, 5],
        )
        self.assertEqual(class_ids_from_annotation({"class_id": 7}, VISION_TASK_TYPE_CLASSIFY), [7])

    def test_class_ids_read_from_label_lines(self):
        self.assertEqual(class_ids_from_label_lines(["19 0.5 0.5 0.2 0.2", "0 0.1 0.1 0.2 0.2", ""]), [0, 19])

    def test_normalize_model_names_accepts_dict_and_list(self):
        self.assertEqual(normalize_model_names({0: "cat", "1": "dog"}), {0: "cat", 1: "dog"})
        self.assertEqual(normalize_model_names(["cat", "dog"]), {0: "cat", 1: "dog"})

    def test_label_gate_skips_when_dataset_declares_no_classes(self):
        require_label_classes_writable([], [19])


class _Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _BoxTensor:
    """模拟 box.xyxy：取 [0] 再 tolist() 才拿到 [x1,y1,x2,y2]。"""

    def __init__(self, values):
        self.values = values

    def __getitem__(self, _index):
        return SimpleNamespace(tolist=lambda: self.values)


class ManualSaveGateTests(unittest.TestCase):
    def test_classify_label_out_of_range_cannot_be_saved(self):
        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_CLASSIFY)
        with self.assertRaises(ValueError):
            strategy.save_manual_annotation({"class_names": ["cat", "dog"]}, {"class_id": 4})


class AutoInferenceGateTests(unittest.TestCase):
    """单张推理的入口检查：类别对不上就整批拦下，既不写标签也不写候选。"""

    def setUp(self):
        self.temp_dir = os.path.realpath(tempfile.mkdtemp(prefix="vt-class-align-"))
        self.dataset_root = os.path.join(self.temp_dir, "training", "align_ds")
        images_dir = os.path.join(self.dataset_root, "train", "images")
        os.makedirs(images_dir, exist_ok=True)
        self.image_path = os.path.join(images_dir, "sample.jpg")
        with open(self.image_path, "wb") as handle:
            handle.write(b"not-a-real-image")
        with open(os.path.join(self.dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write(
                "path: .\ntrain: train/images\nval: val/images\n"
                "names:\n  0: buffalo\n  1: elephant\n  2: rhino\n  3: zebra\n"
            )
        with open(os.path.join(self.dataset_root, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"vision_task_type": "detect", "dataset_id": "align_dataset"}))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _predict_with(self, model_names, class_id):
        box = SimpleNamespace(
            xyxy=_BoxTensor([10.0, 10.0, 50.0, 60.0]),
            cls=_Scalar(float(class_id)),
            conf=_Scalar(0.9),
        )
        prediction = SimpleNamespace(boxes=[box])
        model = SimpleNamespace(names=model_names, predict=lambda *args, **kwargs: [prediction])
        with patch("ultralytics.YOLO", return_value=model):
            return auto_annotate_image(self.temp_dir, self.image_path, model_path="yolo11n.pt")

    def test_out_of_range_class_blocks_the_result_before_it_becomes_a_candidate(self):
        with self.assertRaises(ValueError) as ctx:
            self._predict_with({19: "potted plant"}, 19)

        self.assertIn("19", str(ctx.exception))
        self.assertIn("buffalo", str(ctx.exception))

    def test_same_id_different_meaning_blocks_the_result(self):
        with self.assertRaises(ValueError) as ctx:
            self._predict_with({0: "elephant"}, 0)

        self.assertIn("elephant", str(ctx.exception))

    def test_aligned_class_still_comes_back(self):
        annotation = self._predict_with({0: "buffalo", 1: "elephant"}, 0)

        self.assertEqual(len(annotation["boxes"]), 1)


if __name__ == "__main__":
    unittest.main()
