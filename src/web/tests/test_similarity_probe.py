"""样本相似探测：拿一个框当样本，命中要落进 auto_labels 当候选，且不顶掉上一轮没审完的。

编码器（torchvision 骨干 + 权重）在这里全部打桩——这一份验的是接线：
样本校验、跳过样本自己、跟已标好的框不重复提、候选合并、出处写没写下来。
真检索准不准是另一件事，脚本已经量过（scripts/hook_probe_similarity.py）。
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from contexts.annotation.infrastructure import similarity_probe_runner as runner
from protocols.vision_task_type import VISION_TASK_TYPE_DETECT

PROBE_DATASET = "probe_ds"
HIT_BOX = {"x1": 0.5, "y1": 0.5, "x2": 0.7, "y2": 0.7}
# 归一化 0.5..0.7 的框编码成 YOLO 行就是这个数
HIT_LINE = "0 0.600000 0.600000 0.200000 0.200000"


def _hit(score=0.6, box=None):
    return {"score": score, "box": dict(box or HIT_BOX), "stride": 8, "scale": 1.0}


def _apart(index):
    """互不重叠的窗口，用来把「每张图留几个」这条限逼到眼前。"""
    x = 0.05 * index
    return {"x1": x, "y1": x, "x2": x + 0.04, "y2": x + 0.04}


class _ProbeFixture(unittest.TestCase):
    def setUp(self):
        # 真实路径建夹具：接口回的是归一后的引用，夹具跟着同一形态才对得上
        self.temp_dir = os.path.realpath(tempfile.mkdtemp(prefix="vt-probe-"))
        self.project_path = self.temp_dir
        self.dataset_root = os.path.join(self.temp_dir, "training", PROBE_DATASET)
        os.makedirs(self.dataset_root)
        with open(os.path.join(self.dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write("path: .\ntrain: train/images\nval: val/images\nnames:\n  0: hat\n  1: vest\n")
        with open(os.path.join(self.dataset_root, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"vision_task_type": VISION_TASK_TYPE_DETECT, "dataset_id": PROBE_DATASET}))
        self.sample_image = self._add_image("train", "seed.jpg", "0 0.2 0.2 0.2 0.2\n")
        self.other_image = self._add_image("train", "other.jpg")
        self.auto_dir = os.path.join(self.dataset_root, "auto_labels", "train")
        self.calls = []
        self.hits = [_hit()]
        self.patches = [
            patch.object(runner, "ProbeEncoder", lambda *a, **kw: object()),
            patch.object(runner, "image_maps", lambda enc, path: {}),
            patch.object(runner, "build_sample_plan", lambda enc, path, box: [{"stride": 8, "scale": 1.0, "vec": 1}]),
            patch.object(runner, "collect_image_hits", self._fake_hits),
            patch.object(runner, "_spawn", lambda target: target()),
            patch.object(runner, "start_task", self._fake_create_task),
            patch.object(runner, "update_task_status", self._fake_update),
            patch.object(runner, "ensure_dataset_task_identity", lambda root: {"dataset_id": PROBE_DATASET}),
        ]
        for handle in self.patches:
            handle.start()

    def tearDown(self):
        for handle in self.patches:
            handle.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _add_image(self, split, name, label_text=None):
        images_dir = os.path.join(self.dataset_root, split, "images")
        labels_dir = os.path.join(self.dataset_root, split, "labels")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)
        image_path = os.path.join(images_dir, name)
        # 探针对每张图都要真的解码一次，假字节会在解码那一步就失败掉，测不到落盘这一段
        Image.new("RGB", (100, 100), (120, 60, 200)).save(image_path, quality=80)
        if label_text is not None:
            with open(os.path.join(labels_dir, os.path.splitext(name)[0] + ".txt"), "w", encoding="utf-8") as handle:
                handle.write(label_text)
        return image_path

    def _fake_hits(self, plan, maps, sample_box, score_thresh):
        self.calls.append(score_thresh)
        return list(self.hits)

    def _fake_create_task(self, **kwargs):
        self.task_kwargs = kwargs
        return {"id": "probe-task", "payload": kwargs.get("payload") or {}}

    def _fake_update(self, task_id, **patch_fields):
        self.calls.append(patch_fields)

    def _start(self, **overrides):
        kwargs = {
            "project_path": self.project_path,
            "dataset_name": PROBE_DATASET,
            "split": "train",
            "image_ref": self.sample_image,
            "class_id": 0,
            "sample_box": [10, 10, 30, 30],
        }
        kwargs.update(overrides)
        return runner.start_similarity_probe(**kwargs)

    def _candidate_lines(self, name):
        path = os.path.join(self.auto_dir, os.path.splitext(name)[0] + ".txt")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return [line for line in handle.read().splitlines() if line.strip()]

    def _candidate_meta(self, name):
        path = os.path.join(self.auto_dir, "meta", os.path.splitext(name)[0] + ".json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)


class CandidateWriteTests(_ProbeFixture):
    def test_a_hit_becomes_a_candidate_on_that_image(self):
        self._start()
        self.assertEqual([HIT_LINE], self._candidate_lines("other.jpg"))

    def test_the_sample_image_is_not_scanned_as_its_own_hit(self):
        self._start()
        self.assertEqual([], self._candidate_lines("seed.jpg"))

    def test_the_candidate_carries_where_it_came_from(self):
        """审核时要能当场回答「这个框是谁给的」：出处跟着候选一起落盘。"""
        self._start()
        meta = self._candidate_meta("other.jpg")
        source = meta.get("source") or {}
        self.assertEqual("sample_similarity", source.get("engine"))
        self.assertEqual("hat", source.get("class_name"))
        self.assertEqual(os.path.basename(self.sample_image), os.path.basename(str(source.get("sample_image"))))
        self.assertEqual([0.6], [round(item["conf"], 4) for item in meta["items"]])

    def test_a_hit_on_an_already_labeled_object_is_not_proposed_again(self):
        """跟这张图已经标好的是同一个东西就不再提第二遍——判据就是产品里那把尺子。"""
        self._add_image("train", "other.jpg", HIT_LINE + "\n")
        self._start()
        self.assertEqual([], self._candidate_lines("other.jpg"))

    def test_a_second_round_keeps_the_unreviewed_candidates_from_the_first(self):
        """上一轮还没审完的候选不许被这一轮顶掉。"""
        os.makedirs(self.auto_dir, exist_ok=True)
        with open(os.path.join(self.auto_dir, "other.txt"), "w", encoding="utf-8") as handle:
            handle.write("0 0.100000 0.100000 0.050000 0.050000\n")
        self._start()
        self.assertEqual(2, len(self._candidate_lines("other.jpg")))

    def test_max_per_image_caps_the_boxes_written_on_one_image(self):
        self.hits = [_hit(0.9 - i * 0.1, _apart(i)) for i in range(4)]
        self._start(max_per_image=2)
        self.assertEqual(2, len(self._candidate_lines("other.jpg")))

    def test_no_hit_writes_no_candidate_file(self):
        self.hits = []
        self._start()
        self.assertEqual([], self._candidate_lines("other.jpg"))
        self.assertIsNone(self._candidate_meta("other.jpg"))


class SampleGuardTests(_ProbeFixture):
    def test_class_number_out_of_the_dataset_table_stops_before_any_write(self):
        with self.assertRaises(ValueError) as caught:
            self._start(class_id=7)
        self.assertIn("类别号 7", str(caught.exception))
        self.assertEqual([], self._candidate_lines("other.jpg"))

    def test_a_box_without_area_stops_before_any_write(self):
        with self.assertRaises(ValueError) as caught:
            self._start(sample_box=[10, 10, 10, 40])
        self.assertIn("没有面积", str(caught.exception))

    def test_a_dataset_without_class_table_stops_before_any_write(self):
        with open(os.path.join(self.dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write("path: .\ntrain: train/images\n")
        with self.assertRaises(ValueError) as caught:
            self._start()
        self.assertIn("类别表", str(caught.exception))


class TaskRecordTests(_ProbeFixture):
    def test_the_task_records_the_sample_and_the_threshold(self):
        result = self._start(score_thresh=0.5)
        self.assertEqual({"task_id": "probe-task"}, result)
        payload = self.task_kwargs["payload"]
        self.assertEqual("probe_ds", self.task_kwargs["dataset_id"])
        self.assertEqual("similar_probe", self.task_kwargs["type_"])
        self.assertEqual(0.5, payload["score_thresh"])
        self.assertEqual("hat", payload["class_name"])
        self.assertEqual([0.1, 0.1, 0.3, 0.3], payload["sample_box"])

    def test_the_task_finishes_completed_with_the_count_written(self):
        self._start()
        final = self.calls[-1]
        self.assertEqual("completed", final["status"])
        self.assertEqual(100, final["progress"])
        self.assertEqual(1, final["artifacts"]["added"])
        self.assertEqual(1, final["artifacts"]["pending"])


class RulerTests(unittest.TestCase):
    """窗口合并用的是产品里同一把尺子，不是探针自己另配的一条线。"""

    def test_two_windows_on_the_same_object_collapse_to_one(self):
        kept = runner.nms_hits([_hit(0.9), _hit(0.85)], max_per_image=3)
        self.assertEqual(1, len(kept))

    def test_windows_far_apart_are_two_candidates(self):
        far = {"score": 0.5, "box": {"x1": 0.0, "y1": 0.0, "x2": 0.15, "y2": 0.15}, "stride": 8, "scale": 1.0}
        kept = runner.nms_hits([_hit(0.9), far], max_per_image=3)
        self.assertEqual(2, len(kept))


if __name__ == "__main__":
    unittest.main()
