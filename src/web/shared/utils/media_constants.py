"""集中声明媒体文件与数据集分片常量。"""

IMAGE_FILE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
VIDEO_FILE_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".webm")
VIDEO_FILE_EXTENSION_SET = frozenset(VIDEO_FILE_EXTENSIONS)
DATASET_SPLITS = ("train", "val", "test")
EVAL_SPLITS = ("val", "test")
ROBOFLOW_CONFIG_FILENAMES = ("data.yaml", "data.yml")
