import os
import tempfile
import unittest

from contexts.annotation.infrastructure.annotation_io import decode_segment_file, encode_segment_lines


class SegmentAnnotationIOTests(unittest.TestCase):
    def test_encode_and_decode_segment_polygons(self):
        width = 100
        height = 80
        labels = [
            {
                "class": 2,
                "points": [
                    {"x": 10, "y": 8},
                    {"x": 30, "y": 8},
                    {"x": 30, "y": 24},
                    {"x": 10, "y": 24},
                ],
            }
        ]
        lines = encode_segment_lines(labels, width, height)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("2 "))

        fd, path = tempfile.mkstemp(prefix="vt_seg_lbl_", suffix=".txt")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(lines[0] + "\n")
            decoded = decode_segment_file(path, width, height)
            self.assertEqual(len(decoded), 1)
            self.assertEqual(decoded[0]["class"], 2)
            self.assertEqual(len(decoded[0]["points"]), 4)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()

