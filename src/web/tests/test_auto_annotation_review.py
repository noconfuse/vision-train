"""保存即审核：候选就是画布上的框，留下的进标签、删掉的随候选文件一起清掉，下一轮重跑照样再提。"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from contexts.annotation.application import use_cases
from contexts.annotation.domain.services import filter_duplicate_boxes
from contexts.annotation.infrastructure.annotation_io import resolve_dataset_image_context
from contexts.annotation.infrastructure.annotation_task_strategy import resolve_annotation_task_strategy
from contexts.dataset.infrastructure.dataset_layout import get_dataset_auto_meta_path
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT, VISION_TASK_TYPE_SEGMENT

REVIEW_DATASET_ID = "review_dataset"
REVIEW_DATASET_NAME = "review_ds"


class _ReviewFixture(unittest.TestCase):
    def setUp(self):
        # macOS 的 /var 是 /private/var 的软链，路径没归一化时图片相对路径会变成一串 ../
        self.temp_dir = os.path.realpath(tempfile.mkdtemp(prefix="vt-auto-review-"))
        self.project_path = self.temp_dir
        self.dataset_name = REVIEW_DATASET_NAME
        self.dataset_root = os.path.join(self.temp_dir, "training", self.dataset_name)
        self.manual_dir = os.path.join(self.dataset_root, "train", "labels")
        self.auto_dir = os.path.join(self.dataset_root, "auto_labels", "train")
        os.makedirs(self.manual_dir, exist_ok=True)
        os.makedirs(self.auto_dir, exist_ok=True)
        with open(os.path.join(self.dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write("path: .\ntrain: train/images\nval: val/images\nnames:\n  0: cat\n  1: dog\n")
        self.image_path = os.path.join(self.dataset_root, "train", "images", "sample.jpg")
        os.makedirs(os.path.dirname(self.image_path), exist_ok=True)
        with open(self.image_path, "wb") as handle:
            handle.write(b"not-a-real-image")
        self._write_dataset_meta(VISION_TASK_TYPE_DETECT)
        self.auto_label_path = os.path.join(self.auto_dir, "sample.txt")
        self.manual_label_path = os.path.join(self.manual_dir, "sample.txt")
        self.strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_DETECT)
        self.source = {"task_id": "auto-1", "engine": "ultralytics", "conf_thresh": 0.25}
        self.boxes = [
            {"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 60, "conf": 0.81},
            {"class": 1, "x1": 20, "y1": 20, "x2": 70, "y2": 90, "conf": 0.33},
            {"class": 0, "x1": 80, "y1": 5, "x2": 96, "y2": 25, "conf": 0.52},
        ]
        self.context = self._context()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_dataset_meta(self, vision_task_type):
        with open(os.path.join(self.dataset_root, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"vision_task_type": vision_task_type, "dataset_id": REVIEW_DATASET_ID}))

    def _context(self, image_path=None):
        return resolve_dataset_image_context(
            self.project_path, self.dataset_name, "train", image_path or self.image_path
        )

    def _with_size(self, fn):
        with patch(
            "contexts.annotation.infrastructure.annotation_task_strategy.get_image_size", return_value=(100, 100)
        ):
            return fn()

    def _write_pending(self, boxes=None, strategy=None, context=None):
        payload = {"boxes": list(self.boxes if boxes is None else boxes)}
        target = strategy or self.strategy
        self._with_size(lambda: target.save_auto_annotation(context or self.context, payload, source=self.source))

    def _save(self, annotation, image_path=None):
        return self._with_size(
            lambda: use_cases.save_manual_annotation(
                self.project_path,
                self.dataset_name,
                "train",
                image_path or self.image_path,
                annotation,
            )
        )

    def _read_lines(self, path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return [line for line in handle.read().splitlines() if line.strip()]

    def _meta_path(self, label_path=None):
        return get_dataset_auto_meta_path(label_path or self.auto_label_path, self.auto_dir)

    def assert_no_review_memory(self):
        """拒掉的框不留任何记录：数据集侧目录里不该多出台账文件。"""
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "training", ".dataset-store")))


class DetectReviewTests(_ReviewFixture):
    def test_keeping_boxes_writes_only_kept_ones_and_clears_the_candidates(self):
        self._write_pending()

        self._save({"boxes": [self.boxes[0], self.boxes[2]]})

        kept = self._read_lines(self.manual_label_path)
        self.assertEqual(len(kept), 2)
        self.assertTrue(kept[0].startswith("0 "))
        self.assertTrue(kept[1].startswith("0 "))
        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertFalse(os.path.exists(self._meta_path()))
        self.assert_no_review_memory()

    def test_saving_an_image_without_candidates_writes_labels_only(self):
        self._save({"boxes": [self.boxes[0]]})

        self.assertEqual(len(self._read_lines(self.manual_label_path)), 1)
        self.assert_no_review_memory()

    def test_deleting_the_whole_batch_leaves_no_record_to_skip_next_time(self):
        self._write_pending()

        self._save({"boxes": []})

        self.assertEqual(self._read_lines(self.manual_label_path), [])
        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assert_no_review_memory()

        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(self.context, {"boxes": [self.boxes[1]]}, iou_thresh=0.5)
        )
        self.assertEqual([item["x1"] for item in refined["boxes"]], [20])

    def test_saving_one_image_leaves_other_images_candidates_alone(self):
        other_image = os.path.join(self.dataset_root, "train", "images", "another.jpg")
        with open(other_image, "wb") as handle:
            handle.write(b"not-a-real-image")
        other_context = self._context(other_image)
        other_auto_path = other_context["auto_label_path"]
        self._write_pending()
        self._write_pending(boxes=[self.boxes[0]], context=other_context)

        self._save({"boxes": []})

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertEqual(len(self._read_lines(other_auto_path)), 1)
        self.assertTrue(os.path.exists(self._meta_path(other_auto_path)))

    def test_candidate_drops_when_it_is_the_same_object_as_a_manual_box(self):
        manual = {"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 50}
        self._with_size(lambda: self.strategy.save_manual_annotation(self.context, {"boxes": [manual]}))

        covered = {"class": 0, "x1": 15, "y1": 15, "x2": 30, "y2": 30, "conf": 0.9}
        wrapping = {"class": 0, "x1": 5, "y1": 5, "x2": 55, "y2": 55, "conf": 0.9}
        reboxed = {"class": 0, "x1": 17, "y1": 17, "x2": 57, "y2": 57, "conf": 0.9}
        other_object = {"class": 0, "x1": 60, "y1": 10, "x2": 100, "y2": 50, "conf": 0.9}
        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(
                self.context, {"boxes": [covered, wrapping, reboxed, other_object]}, iou_thresh=0.5
            )
        )

        # 这里把重叠线显式压到 0.5（比默认更狠）来验旋钮真的传到了判据：小框钻在大框里、
        # 大框套住小框、错位重画（IoU≈0.52）都算重复；跟人工框不相交的才是新目标，留给人审。
        self.assertEqual([item["x1"] for item in refined["boxes"]], [60])

    def test_the_default_line_only_drops_what_the_detector_would_merge_itself(self):
        """默认线 0.7 = 检测模型自己 NMS 用的那条：重叠只到一半的框不许当成重复吞掉。"""
        manual = {"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 50}
        half_shift = {"class": 0, "x1": 17, "y1": 17, "x2": 57, "y2": 57, "conf": 0.9}
        near_same = {"class": 0, "x1": 13, "y1": 13, "x2": 53, "y2": 53, "conf": 0.9}
        covered = {"class": 0, "x1": 15, "y1": 15, "x2": 30, "y2": 30, "conf": 0.9}

        kept = filter_duplicate_boxes([half_shift, near_same, covered], [manual], [])

        # 重叠 0.516 的留着（可能是并排站另一个人），重叠 0.748 和套在里面的丢掉
        self.assertEqual([item["x1"] for item in kept], [17])

    def test_other_class_is_never_treated_as_the_same_object(self):
        manual = {"class": 0, "x1": 10, "y1": 10, "x2": 50, "y2": 50}
        self._with_size(lambda: self.strategy.save_manual_annotation(self.context, {"boxes": [manual]}))

        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(
                self.context, {"boxes": [{"class": 1, "x1": 15, "y1": 15, "x2": 30, "y2": 30, "conf": 0.9}]}, 0.5
            )
        )
        self.assertEqual([item["class"] for item in refined["boxes"]], [1])

    def test_a_second_round_keeps_the_first_rounds_unreviewed_candidates(self):
        """候选没审掉之前不许被覆盖写顶掉：换模型/降置信度再跑一轮，只往后追加。"""
        self._write_pending(boxes=[self.boxes[0]])
        first_line = self._read_lines(self.auto_label_path)[0]

        self.source = {**self.source, "task_id": "auto-2"}
        self._write_pending(boxes=[self.boxes[2]])

        lines = self._read_lines(self.auto_label_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], first_line)
        with open(self._meta_path(), encoding="utf-8") as handle:
            items = json.load(handle)["items"]
        self.assertEqual([item["conf"] for item in items], [0.81, 0.52])
        self.assertEqual([item["task_id"] for item in items], ["auto-1", "auto-2"])

    def test_an_old_candidate_without_meta_keeps_its_place_and_the_new_ones_conf(self):
        """补录元信息之前的历史候选没有 items：占位空着，新候选的置信度不能跟着错位。"""
        with open(self.auto_label_path, "w", encoding="utf-8") as handle:
            handle.write("0 0.3 0.4 0.4 0.5\n")

        self._write_pending(boxes=[self.boxes[2]])

        self.assertEqual(len(self._read_lines(self.auto_label_path)), 2)
        with open(self._meta_path(), encoding="utf-8") as handle:
            items = json.load(handle)["items"]
        self.assertEqual([item.get("conf") for item in items], [None, 0.52])

    def test_the_same_box_is_not_offered_twice_by_a_second_round(self):
        """查重依据就是上一轮的候选本身：同一个框第二次不再提，也就不会写两行。"""
        self._write_pending(boxes=[self.boxes[0]])

        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(self.context, {"boxes": [self.boxes[0]]}, iou_thresh=0.7)
        )

        self.assertEqual([], refined["boxes"])

    def test_two_nested_boxes_from_one_round_leave_only_the_first(self):
        """同轮互查：大框套小框时重叠很低，模型的 NMS 不会合并，两个框会一起交出来。

        盘上人工框和上一轮候选都比过了，只有同一轮里先后两个框没比过——这正是缩略图上
        「同一个目标画了两遍」的来源。留下先到的，置信度跟着框一起走，不能错位。
        """
        wrapping = {"class": 0, "x1": 5, "y1": 5, "x2": 55, "y2": 55, "conf": 0.62}
        covered = {"class": 0, "x1": 15, "y1": 15, "x2": 30, "y2": 30, "conf": 0.41}
        second_person = {"class": 0, "x1": 60, "y1": 10, "x2": 100, "y2": 50, "conf": 0.3}

        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(
                self.context, {"boxes": [wrapping, covered, second_person]}, iou_thresh=0.7
            )
        )

        self.assertEqual([item["x1"] for item in refined["boxes"]], [5, 60])
        self.assertEqual([item["conf"] for item in refined["boxes"]], [0.62, 0.3])

    def test_a_nested_candidate_lands_on_disk_once_with_its_own_confidence(self):
        """判完还要落盘：套叠的框只留一行，元信息不能多出一行跟标签行对不上号。"""
        wrapping = {"class": 0, "x1": 5, "y1": 5, "x2": 55, "y2": 55, "conf": 0.62}
        covered = {"class": 0, "x1": 15, "y1": 15, "x2": 30, "y2": 30, "conf": 0.41}

        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(self.context, {"boxes": [wrapping, covered]}, 0.7)
        )
        self._with_size(lambda: self.strategy.save_auto_annotation(self.context, refined, source=self.source))

        self.assertEqual(len(self._read_lines(self.auto_label_path)), 1)
        with open(self._meta_path(), encoding="utf-8") as handle:
            items = json.load(handle)["items"]
        self.assertEqual([item["conf"] for item in items], [0.62])


class BatchWriteTests(_ReviewFixture):
    """批量写入就是「逐张保存」收成一次点按：候选跟到现有标签后面，判定落在那一下。"""

    def _commit(self, images):
        return use_cases.commit_pending_annotations(self.project_path, self.dataset_name, images=images)

    def _manual_box(self, x1=10, cls=0):
        return {"class": cls, "x1": x1, "y1": 10, "x2": x1 + 40, "y2": 50}

    def test_batch_write_appends_the_candidates_after_the_existing_labels(self):
        """批量写入按「额外收下」处理：原有标签一行都不重写，候选整个跟在后面。"""
        self._save({"boxes": [self._manual_box()]})
        self._write_pending()

        result = self._commit([{"path": self.image_path, "split": "train"}])

        lines = self._read_lines(self.manual_label_path)
        self.assertEqual(len(lines), 4)
        self.assertEqual(result["written_items"], 3)
        self.assertTrue(lines[0].startswith("0 "))
        self.assertFalse(os.path.exists(self.auto_label_path))

    def test_batch_write_skips_images_that_have_nothing_left_to_review(self):
        other_image = os.path.join(self.dataset_root, "train", "images", "another.jpg")
        with open(other_image, "wb") as handle:
            handle.write(b"not-a-real-image")
        self._write_pending()

        result = self._commit(
            [{"path": self.image_path, "split": "train"}, {"path": other_image, "split": "train"}]
        )

        self.assertEqual((result["committed_images"], result["skipped_images"], result["requested"]), (1, 1, 2))

    def test_batch_write_refuses_a_list_that_lost_its_entries(self):
        """名单空着还「成功写入 0 张」是最坏的读数：跨页漏一张就少写一张，得当场说清楚。"""
        with self.assertRaises(ValueError):
            self._commit([])
        with self.assertRaises(ValueError):
            self._commit([{"path": "  ", "split": "train"}])

    def test_batch_write_leaves_other_images_candidates_alone(self):
        other_image = os.path.join(self.dataset_root, "train", "images", "another.jpg")
        with open(other_image, "wb") as handle:
            handle.write(b"not-a-real-image")
        other_context = self._context(other_image)
        self._write_pending()
        self._write_pending(boxes=[self.boxes[0]], context=other_context)

        self._commit([{"path": self.image_path, "split": "train"}])

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertEqual(len(self._read_lines(other_context["auto_label_path"])), 1)


class ClearPendingCandidatesTests(_ReviewFixture):
    """批量清空跟着当前筛出来的名单走：名单外的图一张不动，人工标签不碰。"""

    def setUp(self):
        super().setUp()
        self.other_train_image = os.path.join(self.dataset_root, "train", "images", "another.jpg")
        self.val_image = os.path.join(self.dataset_root, "val", "images", "sample.jpg")
        for path in (self.other_train_image, self.val_image):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(b"not-a-real-image")
        self.other_context = self._context(self.other_train_image)
        self.val_context = resolve_dataset_image_context(self.project_path, self.dataset_name, "val", self.val_image)

    def _clear(self, images=None, classes=None):
        if images is None:
            images = [{"path": self.image_path, "split": "train"}]
        return use_cases.clear_pending_annotations(
            self.project_path, self.dataset_name, images=images, classes=classes
        )

    def test_clearing_the_listed_image_leaves_the_other_images_alone(self):
        """名单外的图即使在同一个 split、即使候选早就废了，也不在这次点按的范围里。"""
        self._save({"boxes": [self.boxes[0]]})
        self._write_pending()
        self._write_pending(boxes=[self.boxes[0]], context=self.other_context)
        self._write_pending(boxes=[self.boxes[0], self.boxes[1]], context=self.val_context)

        stats = self._clear()

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertFalse(os.path.exists(self._meta_path()))
        self.assertEqual(len(self._read_lines(self.other_context["auto_label_path"])), 1)
        self.assertEqual(len(self._read_lines(self.val_context["auto_label_path"])), 2)
        self.assertEqual(len(self._read_lines(self.manual_label_path)), 1)
        self.assertEqual((stats["cleared_images"], stats["dropped_items"], stats["requested"]), (1, 3, 1))

    def test_clearing_a_list_that_spans_splits_clears_both(self):
        """搜索是跨 split 的，名单里带着各自的 split，清空就按各自的位置删。"""
        self._write_pending()
        self._write_pending(boxes=[self.boxes[0]], context=self.val_context)

        stats = self._clear(
            images=[
                {"path": self.image_path, "split": "train"},
                {"path": self.val_image, "split": "val"},
            ]
        )

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertFalse(os.path.exists(self.val_context["auto_label_path"]))
        self.assertEqual((stats["cleared_images"], stats["dropped_items"]), (2, 4))

    def test_clearing_one_class_only_removes_that_classs_lines(self):
        """低置信度跑出来的废框通常只属于探测的那一类：整份删会把别的类还没审的一起带走。"""
        self._write_pending()

        stats = self._clear(classes=[1])

        self.assertEqual([line.split()[0] for line in self._read_lines(self.auto_label_path)], ["0", "0"])
        with open(self._meta_path(), encoding="utf-8") as handle:
            items = json.load(handle)["items"]
        self.assertEqual([item["conf"] for item in items], [0.81, 0.52])
        self.assertEqual((stats["dropped_items"], stats["kept_items"], stats["cleared_images"]), (1, 2, 0))

    def test_clearing_every_class_that_is_left_removes_the_file(self):
        self._write_pending(boxes=[self.boxes[1]])

        stats = self._clear(classes=[1])

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertFalse(os.path.exists(self._meta_path()))
        self.assertEqual(stats["cleared_images"], 1)

    def test_clearing_refuses_a_list_that_lost_its_entries(self):
        """名单空着还回「清掉 0 张」是最坏的读数：跨页漏一张就少清一张，得当场说清楚。"""
        with self.assertRaises(ValueError):
            self._clear(images=[])
        with self.assertRaises(ValueError):
            self._clear(images=[{"path": "  ", "split": "train"}])


class SegmentReviewTests(_ReviewFixture):
    def setUp(self):
        super().setUp()
        self._write_dataset_meta(VISION_TASK_TYPE_SEGMENT)
        self.strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_SEGMENT)
        self.context = self._context()
        self.polygon = {
            "class": 2,
            "points": [{"x": 10, "y": 20}, {"x": 30, "y": 20}, {"x": 30, "y": 60}, {"x": 10, "y": 60}],
            "conf": 0.44,
        }

    def test_deleting_a_candidate_polygon_clears_the_file_and_keeps_no_record(self):
        self._with_size(
            lambda: self.strategy.save_auto_annotation(
                self.context, {"polygons": [self.polygon]}, source=self.source
            )
        )

        self._save({"polygons": []})

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertFalse(os.path.exists(self._meta_path()))
        self.assert_no_review_memory()

        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(
                self.context, {"polygons": [dict(self.polygon, conf=0.6)]}, iou_thresh=0.5
            )
        )
        self.assertEqual(len(refined["polygons"]), 1)

    def test_a_second_round_appends_the_new_polygon_instead_of_replacing_the_file(self):
        self._with_size(
            lambda: self.strategy.save_auto_annotation(self.context, {"polygons": [self.polygon]}, source=self.source)
        )

        second = {**self.polygon, "class": 1}
        self._with_size(
            lambda: self.strategy.save_auto_annotation(
                self.context, {"polygons": [second]}, source={**self.source, "task_id": "auto-2"}
            )
        )

        self.assertEqual(2, len(self._read_lines(self.auto_label_path)))


class ClassifyReviewTests(_ReviewFixture):
    def setUp(self):
        super().setUp()
        self._write_dataset_meta(VISION_TASK_TYPE_CLASSIFY)
        self.strategy = resolve_annotation_task_strategy(VISION_TASK_TYPE_CLASSIFY)
        unlabeled_dir = os.path.join(self.dataset_root, "unlabeled", "train")
        os.makedirs(unlabeled_dir, exist_ok=True)
        os.remove(self.image_path)
        self.image_path = os.path.join(unlabeled_dir, "sample.jpg")
        with open(self.image_path, "wb") as handle:
            handle.write(b"not-a-real-image")
        self.auto_label_path = os.path.join(self.auto_dir, "unlabeled", "sample.txt")
        self.context = self._context()

    def _write_candidate(self, class_id=1, conf=0.77):
        self._with_size(
            lambda: self.strategy.save_auto_annotation(
                self.context, {"class_id": class_id, "conf": conf}, source=self.source
            )
        )

    def test_judging_the_image_unlabeled_clears_the_candidate_with_no_record(self):
        self._write_candidate()

        self._save({})

        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertTrue(os.path.isfile(self.image_path))
        self.assert_no_review_memory()

        refined = self._with_size(
            lambda: self.strategy.refine_auto_annotation(self.context, {"class_id": 1, "conf": 0.77}, 0.5)
        )
        self.assertEqual(refined["class_id"], 1)

    def test_choosing_the_candidate_class_moves_the_image_and_clears_the_candidate(self):
        self._write_candidate()

        self._save({"class_id": 1})

        moved = os.path.join(self.dataset_root, "train", "dog", "sample.jpg")
        self.assertFalse(os.path.exists(self.auto_label_path))
        self.assertTrue(os.path.isfile(moved))
        self.assert_no_review_memory()

    def test_batch_write_refuses_classification_and_says_why(self):
        """分类候选是一个类别答案，不是一批标签行：按行搬进标签文件会造出没人认得的标签。"""
        self._write_candidate()

        with self.assertRaises(NotImplementedError) as raised:
            use_cases.commit_pending_annotations(
                self.project_path, self.dataset_name, images=[{"path": self.image_path, "split": "train"}]
            )
        self.assertIn("逐张保存", str(raised.exception))
        self.assertTrue(os.path.exists(self.auto_label_path))

    def test_a_second_round_replaces_the_answer_instead_of_adding_a_second_one(self):
        """分类候选是一张图一个答案，只有这一类是覆盖写：追加会变成两个答案。"""
        self._write_candidate(class_id=1, conf=0.77)

        self._write_candidate(class_id=0, conf=0.61)

        self.assertEqual(1, len(self._read_lines(self.auto_label_path)))
        self.assertEqual(1, len(self._read_lines(self.auto_label_path)[0].split()))
        with open(self._meta_path(), encoding="utf-8") as handle:
            items = json.load(handle)["items"]
        self.assertEqual([0.61], [item["conf"] for item in items])


class SelectAutoClassesTests(unittest.TestCase):
    """漏标探测一轮只看一个类：候选在落盘前就按选定类别筛掉，不靠人从一堆里挑。"""

    def setUp(self):
        self.detect = resolve_annotation_task_strategy(VISION_TASK_TYPE_DETECT)
        self.classify = resolve_annotation_task_strategy(VISION_TASK_TYPE_CLASSIFY)
        self.boxes = [
            {"class": 0, "x1": 1, "y1": 1, "x2": 5, "y2": 5, "conf": 0.9},
            {"class": 1, "x1": 2, "y1": 2, "x2": 6, "y2": 6, "conf": 0.8},
        ]

    def test_only_the_selected_class_survives(self):
        pruned = self.detect.select_auto_annotation_classes({"boxes": list(self.boxes)}, {1})
        self.assertEqual([1], [box["class"] for box in pruned["boxes"]])

    def test_no_selection_keeps_everything(self):
        payload = {"boxes": list(self.boxes)}
        self.assertEqual(payload, self.detect.select_auto_annotation_classes(payload, None))
        self.assertEqual(payload, self.detect.select_auto_annotation_classes(payload, set()))

    def test_classification_payload_off_class_has_no_content(self):
        self.assertEqual({}, self.classify.select_auto_annotation_classes({"class_id": 1, "conf": 0.7}, {0}))
        self.assertEqual(
            {"class_id": 1, "conf": 0.7},
            self.classify.select_auto_annotation_classes({"class_id": 1, "conf": 0.7}, {1}),
        )


if __name__ == "__main__":
    unittest.main()
