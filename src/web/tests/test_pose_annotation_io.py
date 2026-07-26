"""姿态标注协议编解码的回归测试。"""

import shutil
import tempfile
import unittest
from pathlib import Path

from contexts.annotation.infrastructure.annotation_io import decode_pose_file, encode_pose_lines, load_pose_annotation_meta


class PoseAnnotationIoTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vt_pose_anno_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_encode_and_decode_pose_lines_roundtrip(self):
        label_path = self.temp_dir / "sample.txt"
        lines = encode_pose_lines(
            [
                {
                    "class": 0,
                    "keypoints": [
                        {"x": 10, "y": 20, "visible": 2},
                        {"x": 30, "y": 40, "visible": 1},
                        {"x": 0, "y": 0, "visible": 0},
                    ],
                }
            ],
            100,
            100,
            kpt_shape=[3, 3],
        )
        label_path.write_text("\n".join(lines), encoding="utf-8")

        decoded = decode_pose_file(str(label_path), 100, 100, kpt_shape=[3, 3])
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0]["class"], 0)
        self.assertEqual(decoded[0]["keypoints"][0]["visible"], 2)
        self.assertEqual(decoded[0]["keypoints"][1]["visible"], 1)
        self.assertEqual(decoded[0]["keypoints"][2]["visible"], 0)
        self.assertAlmostEqual(decoded[0]["keypoints"][0]["x"], 10.0, places=3)
        self.assertAlmostEqual(decoded[0]["keypoints"][1]["y"], 40.0, places=3)

    def test_skip_instances_without_visible_keypoints(self):
        lines = encode_pose_lines(
            [
                {
                    "class": 0,
                    "keypoints": [
                        {"x": 0, "y": 0, "visible": 0},
                        {"x": 0, "y": 0, "visible": 0},
                    ],
                }
            ],
            100,
            100,
            kpt_shape=[2, 3],
        )
        self.assertEqual(lines, [])

    def test_load_pose_annotation_meta_normalizes_skeleton(self):
        dataset_root = self.temp_dir / "pose_dataset"
        dataset_root.mkdir(parents=True, exist_ok=True)
        (dataset_root / "dataset.yaml").write_text(
            "\n".join(
                [
                    "path: .",
                    "train: train/images",
                    "val: val/images",
                    "names:",
                    "  0: hand",
                    "kpt_shape: [3, 3]",
                    "flip_idx: [0, 1, 2]",
                    "skeleton:",
                    "  - [1, 2]",
                    "  - [2, 3]",
                    "kpt_names:",
                    "  0: [wrist, thumb, index]",
                ]
            ),
            encoding="utf-8",
        )

        meta = load_pose_annotation_meta(str(dataset_root), ["hand"])
        self.assertEqual(meta["kpt_shape"], [3, 3])
        self.assertEqual(meta["skeleton"], [[0, 1], [1, 2]])
        self.assertEqual(meta["kpt_names"][0], ["wrist", "thumb", "index"])


if __name__ == "__main__":
    unittest.main()
