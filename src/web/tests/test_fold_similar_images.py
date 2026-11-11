"""走查列表的相似帧折叠：像的折成一组只留第一张，不像的一张都不许并进去。

折叠只改显示——组员各开各的标注弹窗，判定不跨帧复制，所以这里验的是列表数得对、
指纹缓存跟得上图片改动，以及整个过程一行标签都不写。

只在临时目录造图，不碰任何真实数据集。
"""

import json
import os
import shutil
import tempfile
import unittest

from PIL import Image

from flask import Flask

from contexts.dataset.application.use_cases import list_dataset_images, locate_dataset_image
from contexts.dataset.infrastructure.image_fingerprint import DATASET_FINGERPRINT_FILENAME

FOLD_DATASET = "fold_dataset"
SAME_FRAME = 0
OTHER_FRAME = 9


def _frame(tilt):
    image = Image.new("L", (160, 120))
    pixels = image.load()
    for x in range(160):
        for y in range(120):
            pixels[x, y] = (x * 4 + y * (2 + tilt)) % 256
    return image.convert("RGB")


class _FoldFixture(unittest.TestCase):
    """train 里 a/b 同一画面、c 另一画面；val 里 d 又和 a 同一画面。"""

    def setUp(self):
        # 真实路径建夹具：接口回的是归一后的引用，夹具跟着同一形态才对得上
        self.temp_dir = os.path.realpath(tempfile.mkdtemp(prefix="vt-fold-"))
        self.project_path = self.temp_dir
        self.dataset_root = os.path.join(self.temp_dir, "training", FOLD_DATASET)
        os.makedirs(self.dataset_root)
        with open(os.path.join(self.dataset_root, "dataset.yaml"), "w", encoding="utf-8") as handle:
            handle.write("path: .\ntrain: train/images\nval: val/images\nnames:\n  0: hat\n  1: vest\n")
        with open(os.path.join(self.dataset_root, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"vision_task_type": "detect", "dataset_id": FOLD_DATASET}))
        self._add_image("train", "a.jpg", SAME_FRAME)
        self._add_image("train", "b.jpg", SAME_FRAME)
        self._add_image("train", "c.jpg", OTHER_FRAME)
        self._add_image("val", "d.jpg", SAME_FRAME)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _add_image(self, split, name, tilt, label_text="0 0.5 0.5 0.2 0.2\n"):
        images_dir = os.path.join(self.dataset_root, split, "images")
        labels_dir = os.path.join(self.dataset_root, split, "labels")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)
        image_path = os.path.join(images_dir, name)
        _frame(tilt).save(image_path, quality=92)
        with open(os.path.join(labels_dir, os.path.splitext(name)[0] + ".txt"), "w", encoding="utf-8") as handle:
            handle.write(label_text)
        return image_path

    def _image_path(self, split, name):
        return os.path.join(self.dataset_root, split, "images", name)

    def _add_pending(self, split, name, text="0 0.4 0.4 0.2 0.2\n"):
        auto_dir = os.path.join(self.dataset_root, "auto_labels", split)
        os.makedirs(auto_dir, exist_ok=True)
        with open(os.path.join(auto_dir, os.path.splitext(name)[0] + ".txt"), "w", encoding="utf-8") as handle:
            handle.write(text)

    def _list(self, split="train", **overrides):
        params = {"project_path": self.project_path, "dataset_name": FOLD_DATASET, "split": split}
        params.update(overrides)
        return list_dataset_images(**params)

    def _folded(self, split="train"):
        return self._list(split=split, fold_dup_raw="true")

    @property
    def cache_path(self):
        return os.path.join(self.temp_dir, "training", ".dataset-store", DATASET_FINGERPRINT_FILENAME)

    def _cache(self):
        with open(self.cache_path, encoding="utf-8") as handle:
            return json.load(handle)[FOLD_DATASET]


class FoldDisplayTests(_FoldFixture):
    def test_the_first_frame_of_a_group_stays_and_the_rest_hang_on_it(self):
        page = self._folded()
        self.assertEqual(2, page["total"])
        self.assertEqual(3, page["raw_total"])
        first, second = page["items"]
        self.assertEqual("a.jpg", first["name"])
        self.assertEqual(2, first["dup_group_size"])
        self.assertEqual(["b.jpg"], [member["name"] for member in first["dup_members"]])
        self.assertEqual("c.jpg", second["name"])
        self.assertEqual(1, second["dup_group_size"])
        self.assertEqual([], second["dup_members"])

    def test_a_member_keeps_the_fields_the_thumbnail_needs(self):
        member = self._folded()["items"][0]["dup_members"][0]
        self.assertEqual(self._image_path("train", "b.jpg"), member["path"])
        self.assertEqual("b.jpg", member["name"])
        self.assertEqual("train", member["split"])
        self.assertIn("/api/file?path=", member["url"])

    def test_pending_total_counts_only_images_that_still_have_candidates(self):
        """批量按钮的张数必须是「还有候选的图」，不是筛选出来的全部图。"""
        self._add_pending("train", "b.jpg")
        page = self._list()
        self.assertEqual(3, page["total"])
        self.assertEqual(1, page["pending_total"])

    def test_pending_total_counts_folded_members_too(self):
        self._add_pending("train", "b.jpg")
        page = self._folded()
        self.assertEqual(2, page["total"])
        self.assertEqual(1, page["pending_total"])

    def test_an_empty_candidate_file_is_not_pending(self):
        self._add_pending("train", "b.jpg", text="")
        self.assertEqual(0, self._list()["pending_total"])

    def test_pending_total_is_zero_when_no_candidate_file_is_left(self):
        self.assertEqual(0, self._list()["pending_total"])
        self.assertEqual(0, self._folded()["pending_total"])

    def test_paging_counts_groups_not_images(self):
        page = self._list(fold_dup_raw="true", offset=1, limit=1)
        self.assertEqual(2, page["total"])
        self.assertEqual(3, page["raw_total"])
        self.assertEqual(["c.jpg"], [item["name"] for item in page["items"]])

    def test_a_cross_split_queue_groups_by_picture_not_by_split(self):
        page = self._folded("all")
        self.assertEqual(2, page["total"])
        self.assertEqual(4, page["raw_total"])
        # val/d 和 train/a 是同一画面，折进 train/a 那组，组里记住它自己的 split
        self.assertEqual(
            [("train", ["train", "val"]), ("train", [])],
            [(item["split"], [member["split"] for member in item["dup_members"]]) for item in page["items"]],
        )

    def test_an_unreadable_image_stays_alone(self):
        path = self._image_path("val", "broken.jpg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("not a real image")
        page = self._folded("all")
        broken = [item for item in page["items"] if item["name"] == "broken.jpg"]
        self.assertEqual(1, len(broken))
        self.assertEqual(1, broken[0]["dup_group_size"])

    def test_unfolded_list_keeps_every_image_and_adds_no_group_fields(self):
        page = self._list()
        self.assertEqual(3, page["total"])
        self.assertNotIn("raw_total", page)
        self.assertTrue(all("dup_group_size" not in item for item in page["items"]))

    def test_locate_points_at_the_group_that_holds_the_image(self):
        folded = locate_dataset_image(
            project_path=self.project_path,
            dataset_name=FOLD_DATASET,
            split="train",
            image_path=self._image_path("train", "b.jpg"),
            fold_dup_raw="true",
        )
        self.assertEqual(0, folded["index"])
        self.assertEqual(2, folded["total"])

        plain = locate_dataset_image(
            project_path=self.project_path,
            dataset_name=FOLD_DATASET,
            split="train",
            image_path=self._image_path("train", "b.jpg"),
        )
        self.assertEqual(1, plain["index"])
        self.assertEqual(3, plain["total"])

    def test_group_members_get_their_own_review_boxes(self):
        auto_dir = os.path.join(self.dataset_root, "auto_labels", "train")
        os.makedirs(auto_dir, exist_ok=True)
        for stem, row in (("a", "0 0.5 0.5 0.2 0.2"), ("b", "1 0.25 0.25 0.1 0.1")):
            with open(os.path.join(auto_dir, f"{stem}.txt"), "w", encoding="utf-8") as handle:
                handle.write(row + "\n")
        page = self._list(fold_dup_raw="true", review_boxes_raw="true")
        first = page["items"][0]
        self.assertEqual([0], [box["class"] for box in first["pending_boxes"]])
        self.assertEqual([1], [box["class"] for box in first["dup_members"][0]["pending_boxes"]])
        # 折叠出来的组员也各带自己的已标注框，否则组员缩略图上是空的
        self.assertTrue(all("label_boxes" in item for item in [first] + first["dup_members"]))
        self.assertEqual(
            sorted(box["class"] for box in page["items"][0]["label_boxes"]),
            sorted(box["class"] for box in first["dup_members"][0]["label_boxes"]),
        )

    def test_folding_writes_no_labels_and_no_images(self):
        label_path = os.path.join(self.dataset_root, "train", "labels", "a.txt")
        with open(label_path, encoding="utf-8") as handle:
            before_label = handle.read()
        with open(self._image_path("train", "a.jpg"), "rb") as handle:
            before_bytes = handle.read()
        self._folded("all")
        with open(label_path, encoding="utf-8") as handle:
            self.assertEqual(before_label, handle.read())
        with open(self._image_path("train", "a.jpg"), "rb") as handle:
            self.assertEqual(before_bytes, handle.read())


class FingerprintCacheTests(_FoldFixture):
    def test_the_cache_holds_one_bucket_per_split(self):
        self._folded("all")
        cache = self._cache()
        self.assertEqual({"train", "val"}, set(cache))
        self.assertEqual({"a.jpg", "b.jpg", "c.jpg"}, {os.path.basename(key) for key in cache["train"]})

    def test_folding_one_split_leaves_the_other_buckets_alone(self):
        self._folded("all")
        val_keys = set(self._cache()["val"])
        self._folded("train")
        self.assertEqual(val_keys, set(self._cache()["val"]))

    def test_a_rewritten_image_forces_a_recompute(self):
        """把缓存里的指纹全改成同一个值，只有被改过的图会重算，其余照用缓存。

        这一步同时验两件事：缓存真的被读（三张都并成一组），mtime/size 变了就失效
        （换过的 c.jpg 重算后不再并进那一组）。
        """
        self._folded()
        all_ones = (1 << 64) - 1
        cache_map = {}
        with open(self.cache_path, encoding="utf-8") as handle:
            cache_map = json.load(handle)
        for record in cache_map[FOLD_DATASET]["train"].values():
            record["h"] = all_ones
        with open(self.cache_path, "w", encoding="utf-8") as handle:
            json.dump(cache_map, handle)

        merged = self._folded()
        self.assertEqual(1, merged["total"])
        self.assertEqual(3, merged["items"][0]["dup_group_size"])

        self._add_image("train", "c.jpg", OTHER_FRAME + 3)
        page = self._folded()
        self.assertEqual(2, page["total"])
        self.assertEqual(["a.jpg", "c.jpg"], [item["name"] for item in page["items"]])
        self.assertEqual(2, page["items"][0]["dup_group_size"])

    def test_a_deleted_image_is_pruned_from_the_cache(self):
        self._folded()
        os.remove(self._image_path("train", "b.jpg"))
        os.remove(os.path.join(self.dataset_root, "train", "labels", "b.txt"))
        page = self._folded()
        self.assertEqual(2, page["total"])
        self.assertEqual(1, page["items"][0]["dup_group_size"])
        self.assertNotIn(self._image_path("train", "b.jpg"), self._cache()["train"])


class HttpFoldRouteTests(_FoldFixture):
    """接口层只验装配：``fold_dup`` 这个名字有没有接到用例上。"""

    def setUp(self):
        super().setUp()
        from contexts.dataset.api.blueprint import bp

        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def _get(self, path, **query):
        params = {"project_path": self.project_path, "dataset_name": FOLD_DATASET}
        params.update(query)
        response = self.client.get(path, query_string=params)
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertTrue(payload.get("success"), payload.get("error"))
        return payload["data"]

    def test_images_route_reads_the_fold_switch(self):
        self.assertEqual(3, self._get("/api/dataset/images", split="train")["total"])
        folded = self._get("/api/dataset/images", split="train", fold_dup="true")
        self.assertEqual(2, folded["total"])
        self.assertEqual(3, folded["raw_total"])

    def test_image_index_route_reads_the_fold_switch(self):
        data = self._get(
            "/api/dataset/image_index",
            split="train",
            fold_dup="true",
            image_path=self._image_path("train", "b.jpg"),
        )
        self.assertEqual(0, data["index"])
        self.assertEqual(2, data["total"])


if __name__ == "__main__":
    unittest.main()
