"""分割任务基础能力接入的回归测试。"""

import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from contexts.annotation.infrastructure.annotation_io import decode_segment_file
from contexts.annotation.infrastructure.annotation_task_strategy import resolve_annotation_task_strategy
from contexts.dataset.domain.capabilities import build_dataset_capabilities
from contexts.dataset.infrastructure.dataset_import_strategy import resolve_dataset_import_strategy
from contexts.dataset.infrastructure.dataset_mutation_strategy import resolve_dataset_mutation_strategy
from contexts.dataset.infrastructure.dataset_scan_strategy import resolve_dataset_scan_strategy
from contexts.dataset.infrastructure.dataset_task_strategy import resolve_dataset_task_strategy
from contexts.model.domain.capabilities import (
    MODEL_TRAINING_MODE_YOLO_SEGMENT,
    build_model_capabilities,
)
from contexts.training.domain.export_profile import get_training_export_profile
from contexts.training.domain.result_profile import get_training_result_profile
from contexts.training.domain.training_profile import get_training_profile
from contexts.training.infrastructure.training_runtime_adapter import resolve_training_runtime_adapter
from protocols.vision_task_type import VISION_TASK_TYPE_SEGMENT


class SegmentSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="vt_segment_support_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_segment_capabilities_are_enabled_for_training_flow(self):
        dataset_capabilities = build_dataset_capabilities(VISION_TASK_TYPE_SEGMENT)
        model_capabilities = build_model_capabilities(VISION_TASK_TYPE_SEGMENT)

        self.assertEqual(dataset_capabilities["training_mode"], "yolo_segment")
        self.assertEqual(dataset_capabilities["auto_annotation_mode"], "segment_polygons")
        self.assertEqual(model_capabilities["training_mode"], MODEL_TRAINING_MODE_YOLO_SEGMENT)
        self.assertTrue(dataset_capabilities["operations"]["upload_images"])
        self.assertTrue(dataset_capabilities["operations"]["create_subset"])
        self.assertTrue(dataset_capabilities["operations"]["split_dataset"])
        self.assertTrue(dataset_capabilities["operations"]["train"])
        self.assertTrue(dataset_capabilities["operations"]["merge_datasets"])
        self.assertTrue(dataset_capabilities["operations"]["manual_annotation"])
        self.assertTrue(dataset_capabilities["operations"]["auto_annotate"])

    def test_segment_profiles_are_not_fallback_profiles(self):
        training_profile = get_training_profile(MODEL_TRAINING_MODE_YOLO_SEGMENT)
        result_profile = get_training_result_profile(VISION_TASK_TYPE_SEGMENT)
        export_profile = get_training_export_profile(VISION_TASK_TYPE_SEGMENT)

        self.assertEqual(training_profile["history_metric"]["key"], "seg_map50")
        self.assertGreater(len(training_profile["basic_fields"]), 0)
        self.assertGreater(len(result_profile["evaluate_metric_cards"]), 0)
        self.assertGreater(len(export_profile["formats"]), 0)

    def test_segment_runtime_adapter_reads_box_and_mask_metrics(self):
        adapter = resolve_training_runtime_adapter(MODEL_TRAINING_MODE_YOLO_SEGMENT)
        metrics = SimpleNamespace(
            box=SimpleNamespace(mp=0.71, mr=0.68, map50=0.82, map=0.57),
            seg=SimpleNamespace(mp=0.69, mr=0.65, map50=0.77, map=0.49),
        )

        results = adapter.build_evaluate_results(metrics, "test")

        self.assertEqual(results["split"], "test")
        self.assertAlmostEqual(results["box_map50"], 0.82)
        self.assertAlmostEqual(results["box_map50_95"], 0.57)
        self.assertAlmostEqual(results["seg_map50"], 0.77)
        self.assertAlmostEqual(results["seg_map50_95"], 0.49)

    def test_segment_epoch_history_uses_extra_for_segment_specific_fields(self):
        adapter = resolve_training_runtime_adapter(MODEL_TRAINING_MODE_YOLO_SEGMENT)
        trainer = SimpleNamespace(
            metrics={
                "metrics/mAP50(B)": 0.82,
                "metrics/mAP50-95(B)": 0.57,
                "metrics/mAP50(M)": 0.77,
                "metrics/mAP50-95(M)": 0.49,
            },
            loss_items=[1.2, 2.3, 3.4, 4.5],
        )

        update = adapter.build_epoch_update(trainer, 1, 10)

        self.assertAlmostEqual(update["history"]["box_loss"], 1.2)
        self.assertAlmostEqual(update["history"]["cls_loss"], 3.4)
        self.assertAlmostEqual(update["history"]["dfl_loss"], 4.5)
        self.assertAlmostEqual(update["history"]["map50"], 0.77)
        self.assertAlmostEqual(update["history"]["map50_95"], 0.49)
        self.assertAlmostEqual(update["history"]["extra"]["seg_loss"], 2.3)
        self.assertAlmostEqual(update["history"]["extra"]["box_map50"], 0.82)
        self.assertAlmostEqual(update["history"]["extra"]["box_map50_95"], 0.57)
        self.assertAlmostEqual(update["history"]["extra"]["seg_map50"], 0.77)
        self.assertAlmostEqual(update["history"]["extra"]["seg_map50_95"], 0.49)

    def test_segment_strategies_are_registered(self):
        self.assertEqual(resolve_dataset_task_strategy(VISION_TASK_TYPE_SEGMENT).vision_task_type, VISION_TASK_TYPE_SEGMENT)
        self.assertEqual(resolve_dataset_scan_strategy(VISION_TASK_TYPE_SEGMENT).vision_task_type, VISION_TASK_TYPE_SEGMENT)
        self.assertEqual(resolve_dataset_mutation_strategy(VISION_TASK_TYPE_SEGMENT).vision_task_type, VISION_TASK_TYPE_SEGMENT)
        self.assertEqual(resolve_dataset_import_strategy(VISION_TASK_TYPE_SEGMENT).vision_task_type, VISION_TASK_TYPE_SEGMENT)

    def test_segment_strategy_extracts_auto_polygons(self):
        class _Scalar:
            def __init__(self, value):
                self.value = value

            def item(self):
                return self.value

        class _SegmentArray:
            def __init__(self, points):
                self.points = points

            def tolist(self):
                return self.points

        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_SEGMENT)
        prediction = SimpleNamespace(
            masks=SimpleNamespace(xy=[_SegmentArray([[10, 10], [30, 10], [30, 30], [10, 30]])]),
            boxes=[SimpleNamespace(cls=_Scalar(2))],
        )

        result = strategy.extract_auto_annotation(prediction)

        self.assertEqual(len(result["polygons"]), 1)
        self.assertEqual(result["polygons"][0]["class"], 2)
        self.assertEqual(len(result["polygons"][0]["points"]), 4)

    def test_segment_strategy_saves_commits_and_filters_auto_polygons(self):
        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_SEGMENT)
        image_path = os.path.join(self.temp_dir, "sample.jpg")
        manual_label_path = os.path.join(self.temp_dir, "labels", "sample.txt")
        auto_label_path = os.path.join(self.temp_dir, "auto_labels", "sample.txt")
        os.makedirs(os.path.dirname(manual_label_path), exist_ok=True)
        os.makedirs(os.path.dirname(auto_label_path), exist_ok=True)
        with open(image_path, "wb") as handle:
            handle.write(b"not-a-real-image")

        context = {
            "image_path": image_path,
            "manual_label_path": manual_label_path,
            "auto_label_path": auto_label_path,
            "dataset_root": self.temp_dir,
            "split": "train",
            "relative_noext": "sample",
        }
        manual_polygon = {
            "class": 0,
            "points": [{"x": 10, "y": 10}, {"x": 30, "y": 10}, {"x": 30, "y": 30}, {"x": 10, "y": 30}],
        }
        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            strategy.save_manual_annotation(context, {"polygons": [manual_polygon]})

            refined = strategy.refine_auto_annotation(
                context,
                {
                    "polygons": [
                        manual_polygon,
                        {"class": 0, "points": [{"x": 50, "y": 50}, {"x": 70, "y": 50}, {"x": 70, "y": 70}, {"x": 50, "y": 70}]},
                        {"class": 0, "points": [{"x": 80, "y": 80}, {"x": 81, "y": 80}, {"x": 81, "y": 81}]},
                    ]
                },
                iou_thresh=0.5,
            )

            self.assertEqual(len(refined["polygons"]), 1)
            strategy.save_auto_annotation(context, refined)
            pending = strategy.list_pending_auto_annotations(self.temp_dir, "train")
            self.assertEqual(len(pending["items"]), 1)
            payload = strategy.get_annotation_payload(context)
            self.assertEqual(len(payload["manual_annotation"]["polygons"]), 1)
            self.assertEqual(len(payload["auto_annotation"]["polygons"]), 1)

            strategy.commit_auto_annotation(context)
            merged = decode_segment_file(manual_label_path, 100, 100)
            self.assertEqual(len(merged), 2)
            self.assertFalse(os.path.exists(auto_label_path))

    def test_segment_strategy_filters_candidate_when_mostly_covered_by_manual_polygon(self):
        strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_SEGMENT)
        image_path = os.path.join(self.temp_dir, "covered.jpg")
        manual_label_path = os.path.join(self.temp_dir, "labels", "covered.txt")
        auto_label_path = os.path.join(self.temp_dir, "auto_labels", "covered.txt")
        os.makedirs(os.path.dirname(manual_label_path), exist_ok=True)
        os.makedirs(os.path.dirname(auto_label_path), exist_ok=True)
        with open(image_path, "wb") as handle:
            handle.write(b"not-a-real-image")

        context = {
            "image_path": image_path,
            "manual_label_path": manual_label_path,
            "auto_label_path": auto_label_path,
            "dataset_root": self.temp_dir,
            "split": "train",
            "relative_noext": "covered",
        }
        manual_polygon = {
            "class": 0,
            "points": [{"x": 10, "y": 10}, {"x": 40, "y": 10}, {"x": 40, "y": 40}, {"x": 10, "y": 40}],
        }
        candidate_polygon = {
            "class": 0,
            "points": [{"x": 12, "y": 12}, {"x": 26, "y": 12}, {"x": 26, "y": 38}, {"x": 12, "y": 38}],
        }

        with patch("contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)):
            strategy.save_manual_annotation(context, {"polygons": [manual_polygon]})
            refined = strategy.refine_auto_annotation(
                context,
                {"polygons": [candidate_polygon]},
                iou_thresh=0.95,
            )

        self.assertEqual(refined["polygons"], [])


if __name__ == "__main__":
    unittest.main()
