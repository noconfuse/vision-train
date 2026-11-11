"""近似重复判据（dHash）本身：相似的要成一组，无关的和读不出来的不许混进来。

只在临时目录造图，不碰任何真实数据集。
"""

import os
import shutil
import tempfile
import unittest

from PIL import Image

from shared.utils.image_hash import (
    NEAR_DUPLICATE_THRESHOLD,
    group_by_distance,
    hamming_distance,
    image_dhash,
)


def _gradient(width, height, tilt=0):
    image = Image.new("L", (width, height))
    pixels = image.load()
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (x * 4 + y * (2 + tilt)) % 256
    return image


class DHashTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.realpath(tempfile.mkdtemp(prefix="vt-dhash-"))
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        os.makedirs(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _save(self, name, image, quality=None):
        path = os.path.join(self.temp_dir, name)
        if quality is None:
            image.save(path)
        else:
            image.save(path, quality=quality)
        return path

    def test_the_same_picture_hashes_to_the_same_value(self):
        path = self._save("a.png", _gradient(64, 64))
        self.assertEqual(image_dhash(path), image_dhash(path))
        self.assertEqual(0, hamming_distance(image_dhash(path), image_dhash(path)))

    def test_a_recompressed_copy_is_near_the_original(self):
        original = _gradient(128, 128)
        base = self._save("base.png", original)
        again = self._save("again.jpg", original.convert("RGB"), quality=70)
        resized = self._save("resized.jpg", original.resize((640, 640)).convert("RGB"), quality=80)
        base_hash = image_dhash(base)
        self.assertLessEqual(hamming_distance(base_hash, image_dhash(again)), NEAR_DUPLICATE_THRESHOLD)
        self.assertLessEqual(hamming_distance(base_hash, image_dhash(resized)), NEAR_DUPLICATE_THRESHOLD)

    def test_a_different_picture_is_far(self):
        base = self._save("base.png", _gradient(64, 64))
        other = self._save("other.png", _gradient(64, 64, tilt=9))
        self.assertGreater(hamming_distance(image_dhash(base), image_dhash(other)), NEAR_DUPLICATE_THRESHOLD)

    def test_unreadable_image_has_no_hash(self):
        path = os.path.join(self.temp_dir, "broken.jpg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("not a real image")
        self.assertIsNone(image_dhash(path))


class GroupingTests(unittest.TestCase):
    def test_identical_values_share_a_group_and_distant_ones_stay_alone(self):
        groups = group_by_distance([0, 0, (1 << 64) - 1])
        self.assertEqual([0, 0, 1], groups)

    def test_missing_hashes_never_join_a_group(self):
        groups = group_by_distance([None, 0, 0, None])
        self.assertEqual([0, 1, 1, 2], groups)

    def test_chained_near_duplicates_collapse_into_one_group(self):
        """连拍帧是一条链：A~B、B~C，但 A 与 C 可能已超过阈值——按并查集仍然算一组。

        这正是列表折叠想要的（同一镜头不必反复看），也说明组会随镜头长度变长，
        所以折叠只折显示，判定各判各的。
        """
        chain = [0, (1 << 6) - 1, (1 << 12) - 1]
        self.assertEqual(6, hamming_distance(chain[0], chain[1]))
        self.assertEqual(6, hamming_distance(chain[1], chain[2]))
        self.assertGreater(hamming_distance(chain[0], chain[2]), NEAR_DUPLICATE_THRESHOLD)
        self.assertEqual([0, 0, 0], group_by_distance(chain))

    def test_an_empty_list_groups_to_nothing(self):
        self.assertEqual([], group_by_distance([]))


if __name__ == "__main__":
    unittest.main()
