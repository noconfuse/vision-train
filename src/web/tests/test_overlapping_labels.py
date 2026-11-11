"""同类重复框与待复核候选框作为图片列表条件的行为。

只扫不删：几何算得出「这两个框重合到什么程度」，算不出「该删哪个」，
所以这里验的是扫得准不准、列表筛得对不对、候选框几何带得全不全，
删哪个框由人进标注页决定。
"""

import json
import os
import shutil
import tempfile
import unittest

from flask import Flask

from contexts.annotation.application.annotation_service import SAME_OBJECT_COVER_THRESH
from contexts.dataset.application.use_cases import (
    list_dataset_images,
    locate_dataset_image,
)
from contexts.dataset.infrastructure.dataset_task_strategy import resolve_dataset_task_strategy
from contexts.dataset.infrastructure.overlapping_labels import (
    count_redundant_boxes,
    find_redundant_lines,
)
from protocols.vision_task_type import (
    VISION_TASK_TYPE_CLASSIFY,
    VISION_TASK_TYPE_DETECT,
    VISION_TASK_TYPE_POSE,
    VISION_TASK_TYPE_SEGMENT,
)

OVERLAP_DATASET = "overlap_dataset"
BIG = "0 0.5 0.5 0.4 0.4"
INSIDE = "0 0.5 0.5 0.2 0.2"
OFFSET = "0 0.35 0.35 0.2 0.2"
# 同一个框平移一点：重叠 0.75（覆盖只有 0.86，套叠判据不够），靠重叠线抓
REBOXED = "0 0.556 0.5 0.4 0.4"
# 重叠过半但没到七成：模型自己 NMS 都不会合并，不算重复
HALF = "0 0.56 0.56 0.36 0.36"
OTHER_CLASS = "1 0.5 0.5 0.2 0.2"
POLYGON = "0 0.4 0.4 0.6 0.4 0.6 0.6 0.4 0.6"


class RedundantLineTests(unittest.TestCase):
    """判据只看几何：同类 + 重叠七成以上或被套住九成才算冗余，重叠不到七成和别类重叠都不算。"""

    def _lines(self, *rows):
        return [f"{row}\n" for row in rows]

    def test_box_covered_by_same_class_keeps_the_bigger_one(self):
        records, stats = find_redundant_lines(self._lines(BIG, INSIDE))
        self.assertEqual(1, len(records))
        self.assertEqual(2, records[0]["line_no"])
        self.assertEqual(1, records[0]["kept_line_no"])
        self.assertGreaterEqual(records[0]["min_cover_ratio"], SAME_OBJECT_COVER_THRESH)
        self.assertEqual(2, stats["boxes"])

    def test_same_object_reboxed_is_a_duplicate(self):
        """整框错位重画：重叠到七成以上就算同一个东西，哪怕没有一个落在另一个里面。"""
        records, _ = find_redundant_lines(self._lines(BIG, REBOXED))
        self.assertEqual(1, len(records))
        self.assertEqual(2, records[0]["line_no"])

    def test_half_overlap_is_left_for_a_human_to_judge(self):
        """重叠过半但不到七成：模型自己 NMS 都留着两个框，程序不许先替它判成重复。"""
        records, _ = find_redundant_lines(self._lines(BIG, HALF))
        self.assertEqual([], records)

    def test_offset_overlap_is_left_for_a_human_to_judge(self):
        records, _ = find_redundant_lines(self._lines(BIG, OFFSET))
        self.assertEqual([], records)

    def test_other_class_covering_the_box_is_not_a_duplicate(self):
        records, _ = find_redundant_lines(self._lines(BIG, OTHER_CLASS))
        self.assertEqual([], records)

    def test_three_nested_boxes_leave_only_the_outermost(self):
        lines = self._lines(
            "0 0.5 0.5 0.6 0.6",
            "0 0.5 0.5 0.3 0.3",
            "0 0.5 0.5 0.1 0.1",
        )
        records, _ = find_redundant_lines(lines)
        self.assertEqual({2, 3}, {record["line_no"] for record in records})
        self.assertTrue(all(record["kept_line_no"] == 1 for record in records))

    def test_excluded_class_is_never_counted(self):
        records, _ = find_redundant_lines(self._lines(BIG, INSIDE), exclude_classes=[0])
        self.assertEqual([], records)

    def test_polygon_and_pose_lines_are_reported_not_counted(self):
        lines = self._lines(BIG, f"{BIG} 0.1 0.1")
        records, stats = find_redundant_lines(lines)
        self.assertEqual([], records)
        self.assertEqual(1, stats["unparsed_lines"])

    def test_zero_area_box_is_counted_as_degenerate(self):
        lines = self._lines(BIG, "0 0.5 0.5 0.0 0.2")
        records, stats = find_redundant_lines(lines)
        self.assertEqual([], records)
        self.assertEqual(1, stats["degenerate_boxes"])


class _DatasetFixture(unittest.TestCase):
    """一个检测数据集：train/a.jpg 有 1 个冗余框，train/b.jpg 干净，val/c.jpg 有 2 个。"""

    def setUp(self):
        # 真实路径建夹具：接口回的是归一后的引用，夹具跟着同一形态才对得上
        self.temp_dir = os.path.realpath(tempfile.mkdtemp(prefix="vt-overlap-"))
        self.project_path = self.temp_dir
        self.dataset_root = os.path.join(self.temp_dir, "training", OVERLAP_DATASET)
        os.makedirs(self.dataset_root)
        with open(os.path.join(self.dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write("path: .\ntrain: train/images\nval: val/images\nnames:\n  0: hat\n  1: vest\n")
        with open(os.path.join(self.dataset_root, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"vision_task_type": "detect", "dataset_id": OVERLAP_DATASET}))
        self._add_image("train", "a.jpg", f"{BIG}\n{INSIDE}\n{OTHER_CLASS}\n")
        self._add_image("train", "b.jpg", f"{BIG}\n{OFFSET}\n")
        self._add_image("val", "c.jpg", f"{BIG}\n{INSIDE}\n{INSIDE}\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _add_image(self, split, name, label_text=None):
        images_dir = os.path.join(self.dataset_root, split, "images")
        labels_dir = os.path.join(self.dataset_root, split, "labels")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)
        image_path = os.path.join(images_dir, name)
        with open(image_path, "wb") as handle:
            handle.write(b"not-a-real-image")
        label_path = os.path.join(labels_dir, os.path.splitext(name)[0] + ".txt")
        if label_text is not None:
            with open(label_path, "w", encoding="utf-8") as handle:
                handle.write(label_text)
        return image_path, label_path

    def _add_candidate(self, split, name, label_text):
        """放一份待确认候选（<数据集>/auto_labels/<split>/）：走查列表读的是它，不是人工标签。"""
        auto_dir = os.path.join(self.dataset_root, "auto_labels", split)
        os.makedirs(auto_dir, exist_ok=True)
        path = os.path.join(auto_dir, os.path.splitext(name)[0] + ".txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(label_text)
        return path

    def _list(self, split="all", **overrides):
        params = {"project_path": self.project_path, "dataset_name": OVERLAP_DATASET, "split": split}
        params.update(overrides)
        return list_dataset_images(**params)


class CountRedundantBoxesTests(_DatasetFixture):
    def test_counts_the_redundant_lines_in_a_label_file(self):
        _, label_path = self._add_image("train", "a.jpg", f"{BIG}\n{INSIDE}\n{OTHER_CLASS}\n")
        self.assertEqual(1, count_redundant_boxes(label_path))

    def test_missing_label_file_counts_zero(self):
        self.assertEqual(0, count_redundant_boxes(os.path.join(self.dataset_root, "train", "labels", "none.txt")))

    def test_count_does_not_write_anything(self):
        _, label_path = self._add_image("train", "z.jpg", f"{BIG}\n{INSIDE}\n")
        with open(label_path, encoding="utf-8") as handle:
            before = handle.read()
        count_redundant_boxes(label_path)
        with open(label_path, encoding="utf-8") as handle:
            self.assertEqual(before, handle.read())
        self.assertEqual(
            sorted(os.listdir(os.path.join(self.dataset_root, "train", "images"))),
            ["a.jpg", "b.jpg", "z.jpg"],
        )
        self.assertEqual(
            sorted(os.listdir(os.path.join(self.dataset_root, "train", "labels"))),
            ["a.txt", "b.txt", "z.txt"],
        )
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "training", ".dataset-store")))


class StrategyCountTests(_DatasetFixture):
    def test_detect_strategy_counts_by_image(self):
        strategy = resolve_dataset_task_strategy(VISION_TASK_TYPE_DETECT)
        self.assertEqual(
            1, strategy.count_overlapping_boxes(self.dataset_root, "train", os.path.join(self.dataset_root, "train", "images", "a.jpg"))
        )
        self.assertEqual(
            0, strategy.count_overlapping_boxes(self.dataset_root, "train", os.path.join(self.dataset_root, "train", "images", "b.jpg"))
        )

    def test_image_without_a_label_file_counts_zero(self):
        image_path, _ = self._add_image("train", "d.jpg")
        strategy = resolve_dataset_task_strategy(VISION_TASK_TYPE_DETECT)
        self.assertEqual(0, strategy.count_overlapping_boxes(self.dataset_root, "train", image_path))

    def test_classify_strategy_counts_zero(self):
        strategy = resolve_dataset_task_strategy(VISION_TASK_TYPE_CLASSIFY)
        self.assertEqual(
            0,
            strategy.count_overlapping_boxes(self.dataset_root, "train", os.path.join(self.dataset_root, "train", "images", "a.jpg")),
        )

    def test_polygon_lines_are_not_read_as_boxes(self):
        image_path, _ = self._add_image("val", "e.jpg", f"{POLYGON}\n{POLYGON}\n")
        for task_type in (VISION_TASK_TYPE_SEGMENT, VISION_TASK_TYPE_POSE):
            strategy = resolve_dataset_task_strategy(task_type)
            self.assertEqual(0, strategy.count_overlapping_boxes(self.dataset_root, "val", image_path), task_type)


class ListFilterTests(_DatasetFixture):
    def test_filter_keeps_only_images_with_overlap_and_reports_the_count(self):
        page = self._list(overlap_dup_raw="true")
        self.assertEqual(2, page["total"])
        self.assertEqual(
            [os.path.join(self.dataset_root, "train", "images", "a.jpg"),
             os.path.join(self.dataset_root, "val", "images", "c.jpg")],
            [item["path"] for item in page["items"]],
        )
        self.assertEqual([1, 2], [item["overlap_boxes"] for item in page["items"]])

    def test_unfiltered_list_has_no_overlap_count(self):
        page = self._list()
        self.assertEqual(3, page["total"])
        self.assertTrue(all("overlap_boxes" not in item for item in page["items"]))

    def test_filter_spans_splits_and_pages(self):
        page = self._list(overlap_dup_raw="true", offset=1, limit=1)
        self.assertEqual(2, page["total"])
        self.assertEqual(
            [os.path.join(self.dataset_root, "val", "images", "c.jpg")],
            [item["path"] for item in page["items"]],
        )

    def test_filter_stacks_with_keyword(self):
        page = self._list(overlap_dup_raw="true", keyword="a")
        self.assertEqual(1, page["total"])
        self.assertEqual(1, page["items"][0]["overlap_boxes"])

    def test_locate_matches_the_filtered_list(self):
        located = locate_dataset_image(
            project_path=self.project_path,
            dataset_name=OVERLAP_DATASET,
            split="all",
            image_path=os.path.join(self.dataset_root, "val", "images", "c.jpg"),
            overlap_dup_raw="true",
        )
        self.assertEqual(1, located["index"])
        self.assertEqual(2, located["total"])

    def test_locate_reports_minus_one_when_the_image_has_no_overlap(self):
        located = locate_dataset_image(
            project_path=self.project_path,
            dataset_name=OVERLAP_DATASET,
            split="all",
            image_path=os.path.join(self.dataset_root, "train", "images", "b.jpg"),
            overlap_dup_raw="true",
        )
        self.assertEqual(-1, located["index"])
        self.assertEqual(2, located["total"])


class ReviewBoxesTests(_DatasetFixture):
    """走查列表：待复核的图把候选框和已标注框几何一起带回来，缩略图上才画得出整体。"""

    def test_boxes_are_attached_only_when_the_list_asks_for_them(self):
        self._add_candidate("train", "a.jpg", f"{BIG}\n")
        plain = self._list(review_boxes_raw=None)
        self.assertTrue(all("pending_boxes" not in item for item in plain["items"]))
        self.assertTrue(all("label_boxes" not in item for item in plain["items"]))

        page = self._list(review_boxes_raw="true")
        self.assertEqual(3, page["total"])
        self.assertTrue(all("pending_boxes" in item for item in page["items"]))
        self.assertTrue(all("label_boxes" in item for item in page["items"]))
        by_name = {item["name"]: item["pending_boxes"] for item in page["items"]}
        self.assertEqual(1, len(by_name["a.jpg"]))
        self.assertEqual([], by_name["b.jpg"])

    def test_label_boxes_are_the_manual_lines_of_that_image(self):
        """已标注框读的是 split/labels：人工标了 3 个框就回 3 个，跟候选互不干扰。"""
        self._add_candidate("train", "a.jpg", f"{POLYGON}\n")
        page = self._list(split="train", keyword="a", review_boxes_raw="true")
        item = page["items"][0]
        self.assertEqual([], item["pending_boxes"])
        self.assertEqual(
            [0, 0, 1],
            sorted(box["class"] for box in item["label_boxes"]),
        )

    def test_image_without_a_label_file_gets_empty_boxes(self):
        """没标过、也没跑过自动标注的图：两个集合都是空，不是缺字段。"""
        self._add_image("train", "h.jpg")
        page = self._list(split="train", keyword="h", review_boxes_raw="true")
        self.assertEqual([], page["items"][0]["label_boxes"])
        self.assertEqual([], page["items"][0]["pending_boxes"])

    def test_geometry_is_class_plus_normalized_xyxy(self):
        self._add_image("train", "d.jpg")
        self._add_candidate("train", "d.jpg", "1 0.5 0.25 0.2 0.1\n")
        page = self._list(split="train", keyword="d", review_boxes_raw="true")
        self.assertEqual(
            [{"class": 1, "x1": 0.4, "y1": 0.2, "x2": 0.6, "y2": 0.3}],
            [{"class": round(box["class"], 6), **{k: round(v, 6) for k, v in box.items() if k != "class"}}
             for box in page["items"][0]["pending_boxes"]],
        )

    def test_only_the_current_page_is_read(self):
        self._add_candidate("train", "a.jpg", f"{BIG}\n")
        self._add_candidate("train", "b.jpg", f"{BIG}\n")
        page = self._list(split="train", limit=1, review_boxes_raw="true")
        self.assertEqual(1, len(page["items"]))
        self.assertEqual(2, page["total"])

    def test_image_without_a_candidate_file_gets_an_empty_list(self):
        page = self._list(split="train", keyword="b", review_boxes_raw="true")
        self.assertEqual([], page["items"][0]["pending_boxes"])

    def test_polygon_candidate_lines_are_not_read_as_boxes(self):
        self._add_image("val", "e.jpg")
        self._add_candidate("val", "e.jpg", f"{POLYGON}\n")
        page = self._list(split="val", keyword="e", review_boxes_raw="true")
        self.assertEqual([], page["items"][0]["pending_boxes"])

    def test_reading_the_list_writes_nothing(self):
        path = self._add_candidate("train", "a.jpg", f"{BIG}\n")
        with open(path, encoding="utf-8") as handle:
            before = handle.read()
        self._list(review_boxes_raw="true", has_auto_label_raw="true")
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(before, handle.read())

    def test_classify_dataset_has_no_box_to_draw(self):
        image_path, _ = self._add_image("train", "f.jpg", "0 0.5 0.5 0.2 0.2\n")
        self._add_candidate("train", "f.jpg", f"{BIG}\n")
        strategy = resolve_dataset_task_strategy(VISION_TASK_TYPE_CLASSIFY)
        self.assertEqual([], strategy.list_pending_boxes(self.dataset_root, "train", image_path))
        self.assertEqual([], strategy.list_label_boxes(self.dataset_root, "train", image_path))

    def test_segment_and_pose_candidates_are_not_read_as_boxes(self):
        """分割/姿态的标签行是多边形和关键点，不是框：列表上只留「待复核」点标，不在缩略图上画。"""
        image_path, _ = self._add_image("train", "g.jpg", f"{POLYGON}\n")
        self._add_candidate("train", "g.jpg", f"{POLYGON}\n")
        for task_type in (VISION_TASK_TYPE_SEGMENT, VISION_TASK_TYPE_POSE):
            strategy = resolve_dataset_task_strategy(task_type)
            self.assertEqual([], strategy.list_pending_boxes(self.dataset_root, "train", image_path), task_type)
            self.assertEqual([], strategy.list_label_boxes(self.dataset_root, "train", image_path), task_type)


class HttpRouteTests(_DatasetFixture):
    """接口层只验装配：参数名、默认值与返回信封；判据和筛选择在上面几组里验。"""

    def setUp(self):
        super().setUp()
        from contexts.dataset.api.blueprint import bp

        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def _get(self, path, **query):
        params = {"project_path": self.project_path, "dataset_name": OVERLAP_DATASET}
        params.update(query)
        response = self.client.get(path, query_string=params)
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertTrue(payload.get("success"), payload.get("error"))
        return payload["data"]

    def test_images_route_reads_the_overlap_filter(self):
        filtered = self._get("/api/dataset/images", split="all", overlap_dup="true")
        self.assertEqual(2, filtered["total"])
        self.assertEqual([1, 2], [item["overlap_boxes"] for item in filtered["items"]])

        unfiltered = self._get("/api/dataset/images", split="all")
        self.assertEqual(3, unfiltered["total"])

    def test_image_index_route_reads_the_overlap_filter(self):
        data = self._get(
            "/api/dataset/image_index",
            split="all",
            overlap_dup="true",
            image_path=os.path.join(self.dataset_root, "val", "images", "c.jpg"),
        )
        self.assertEqual(1, data["index"])
        self.assertEqual(2, data["total"])

    def test_images_route_reads_the_review_boxes_switch(self):
        self._add_candidate("train", "a.jpg", f"{BIG}\n")
        data = self._get("/api/dataset/images", split="train", has_auto_label="true", review_boxes="true")
        self.assertEqual(1, data["total"])
        self.assertEqual([0], [box["class"] for box in data["items"][0]["pending_boxes"]])
        # 这张图人工标签里有 3 行（0、0、1），走查列表一起带回来，缩略图才画得出整体
        self.assertEqual([0, 0, 1], sorted(box["class"] for box in data["items"][0]["label_boxes"]))


if __name__ == "__main__":
    unittest.main()
