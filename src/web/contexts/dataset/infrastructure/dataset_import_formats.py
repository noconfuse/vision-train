"""识别外部数据集格式并转换为项目标准 YOLO 布局。"""

import glob
import os
import shutil
import xml.etree.ElementTree as ET

from contexts.dataset.infrastructure.dataset_layout import (
    DATASET_SPLIT_TEST,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    strip_dataset_images_ref,
)
from contexts.dataset.infrastructure.dataset_schema import (
    find_dataset_config,
    save_standard_dataset_yaml,
)
from shared.utils.media_constants import DATASET_SPLITS, IMAGE_FILE_EXTENSIONS, ROBOFLOW_CONFIG_FILENAMES
from shared.utils.json_utils import load_json_file
from shared.utils.value_utils import first_non_empty_text
from shared.utils.yaml_utils import load_yaml_file


def _has_glob(root, pattern):
    """判断目录下是否存在匹配 glob 的文件。"""
    return len(glob.glob(os.path.join(root, pattern))) > 0


def _list_meaningful_entries(root):
    """列出目录下可参与导入协议判断的可见条目。"""
    if not os.path.isdir(root):
        return []
    return [
        entry
        for entry in sorted(os.listdir(root))
        if not entry.startswith("__MACOSX") and not entry.startswith(".")
    ]


def resolve_import_archive_root(extracted_dir):
    """按显式“单层包装目录”规则解析压缩包数据集根目录。"""
    current_dir = extracted_dir
    while True:
        entries = _list_meaningful_entries(current_dir)
        if len(entries) != 1:
            return current_dir
        only_entry_path = os.path.join(current_dir, entries[0])
        if not os.path.isdir(only_entry_path):
            return current_dir
        current_dir = only_entry_path


def detect_dataset_format(root):
    """按导入根目录下的显式标准结构识别数据集格式。"""
    if not os.path.isdir(root):
        return "unknown"
    if find_dataset_config(root) is not None:
        return "yolo"
    for rf_name in ROBOFLOW_CONFIG_FILENAMES:
        if os.path.isfile(os.path.join(root, rf_name)):
            return "roboflow"
    if os.path.isdir(os.path.join(root, "annotations")) and _has_glob(root, "annotations/instances_*.json"):
        return "coco"
    if os.path.isdir(os.path.join(root, "Annotations")) and os.path.isdir(os.path.join(root, "JPEGImages")) and _has_glob(root, "Annotations/*.xml"):
        return "voc"
    return "unknown"


def convert_coco_to_yolo(coco_root, yolo_root, progress_cb=None):
    """把 COCO 标注和图片转换为标准 YOLO 数据集。"""
    ann_dir_candidates = [os.path.join(coco_root, "annotations"), coco_root]
    ann_dir = None
    for candidate in ann_dir_candidates:
        if _has_glob(candidate, "instances_*.json"):
            ann_dir = candidate
            break
    if ann_dir is None:
        raise ValueError("COCO 数据集未找到 annotations/instances_*.json")

    split_map = {}
    for json_path in glob.glob(os.path.join(ann_dir, "instances_*.json")):
        name = os.path.splitext(os.path.basename(json_path))[0]
        tail = name[len("instances_"):] if name.startswith("instances_") else "train"
        split = "".join(ch for ch in tail if not ch.isdigit())
        candidates = [
            os.path.join(coco_root, tail),
            os.path.join(coco_root, tail.replace("2017", "")),
            os.path.join(coco_root, split),
            os.path.join(coco_root, f"{split}2017"),
        ]
        img_dir = next((path for path in candidates if os.path.isdir(path)), None)
        split_map[split] = (json_path, img_dir)
    if not split_map:
        raise ValueError("COCO 数据集无有效 split")

    first_split = next(iter(split_map))
    first_ann = load_json_file(split_map[first_split][0], default={}) or {}
    if "categories" not in first_ann:
        raise ValueError("COCO JSON 缺 categories 字段")
    categories = sorted(first_ann["categories"], key=lambda category: category.get("id", 0))
    cat_id_to_yolo = {category["id"]: idx for idx, category in enumerate(categories)}
    names = [category["name"] for category in categories]

    os.makedirs(yolo_root, exist_ok=True)
    split_dirs = {}
    for split in split_map:
        os.makedirs(get_dataset_images_dir(yolo_root, split), exist_ok=True)
        os.makedirs(get_dataset_labels_dir(yolo_root, split), exist_ok=True)
        split_dirs[split] = (get_dataset_images_dir(yolo_root, split), get_dataset_labels_dir(yolo_root, split))

    save_standard_dataset_yaml(
        yolo_root,
        {idx: name for idx, name in enumerate(names)},
        include_val=True,
        include_test=DATASET_SPLIT_TEST in split_map,
    )

    n_splits = max(1, len(split_map))
    for s_idx, (split, (json_path, img_dir)) in enumerate(split_map.items()):
        ann = load_json_file(json_path, default={}) or {}
        images_by_id = {img["id"]: img for img in ann.get("images", [])}
        by_image = {}
        for annotation in ann.get("annotations", []):
            by_image.setdefault(annotation["image_id"], []).append(annotation)

        yolo_img_dir, yolo_lbl_dir = split_dirs[split]
        n_imgs = max(1, len(images_by_id))
        for i_idx, (img_id, img) in enumerate(images_by_id.items()):
            src_img = os.path.join(img_dir, img["file_name"]) if img_dir else None
            if src_img and os.path.isfile(src_img):
                dst_img = os.path.join(yolo_img_dir, os.path.basename(src_img))
                if not os.path.exists(dst_img):
                    shutil.copyfile(src_img, dst_img)

            anns = by_image.get(img_id, [])
            lines = []
            iw, ih = img.get("width", 0), img.get("height", 0)
            if iw > 0 and ih > 0:
                for annotation in anns:
                    cat_id = annotation.get("category_id")
                    if cat_id not in cat_id_to_yolo:
                        continue
                    yolo_class_id = cat_id_to_yolo[cat_id]
                    bx, by, bw, bh = annotation["bbox"]
                    xc = (bx + bw / 2.0) / iw
                    yc = (by + bh / 2.0) / ih
                    nw = bw / iw
                    nh = bh / ih
                    lines.append(f"{yolo_class_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

            label_path = os.path.join(yolo_lbl_dir, os.path.splitext(os.path.basename(src_img or f"{img_id}.jpg"))[0] + ".txt")
            with open(label_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            if progress_cb and (i_idx % 50 == 0 or i_idx == n_imgs - 1):
                progress_cb(s_idx, n_splits, i_idx + 1, n_imgs)


def convert_voc_to_yolo(voc_root, yolo_root, progress_cb=None):
    """把 Pascal VOC 数据集转换为标准 YOLO 布局。"""
    ann_dir = next((os.path.join(voc_root, name) for name in os.listdir(voc_root) if name == "Annotations" and os.path.isdir(os.path.join(voc_root, name))), voc_root)
    jpeg_dir = next((os.path.join(voc_root, name) for name in os.listdir(voc_root) if name == "JPEGImages" and os.path.isdir(os.path.join(voc_root, name))), voc_root)
    main_dir = next((os.path.join(voc_root, name) for name in os.listdir(voc_root) if name == "ImageSets" and os.path.isdir(os.path.join(voc_root, name))), None)

    split_files = {}
    if main_dir:
        for split in DATASET_SPLITS:
            txt = os.path.join(main_dir, "Main", f"{split}.txt")
            if os.path.isfile(txt):
                split_files[split] = txt
    if not split_files:
        xml_ids = [os.path.splitext(filename)[0] for filename in os.listdir(ann_dir) if filename.endswith(".xml")]
        if not xml_ids:
            raise ValueError("VOC 数据集无 Annotations/*.xml 文件")
        split_files["train"] = None

    all_names = set()
    xmls = {}
    for filename in os.listdir(ann_dir):
        if not filename.endswith(".xml"):
            continue
        try:
            tree = ET.parse(os.path.join(ann_dir, filename))
            root_el = tree.getroot()
            xmls[os.path.splitext(filename)[0]] = root_el
            for obj in root_el.iter("object"):
                name = obj.find("name")
                if name is not None and name.text:
                    all_names.add(name.text.strip())
        except Exception:
            continue
    if not all_names:
        raise ValueError("VOC 数据集所有 XML 解析失败或无 <object>")
    names = sorted(all_names)
    name_to_id = {name: idx for idx, name in enumerate(names)}

    os.makedirs(yolo_root, exist_ok=True)
    for split in split_files:
        os.makedirs(get_dataset_images_dir(yolo_root, split), exist_ok=True)
        os.makedirs(get_dataset_labels_dir(yolo_root, split), exist_ok=True)

    save_standard_dataset_yaml(
        yolo_root,
        {idx: name for idx, name in enumerate(names)},
        include_val=True,
        include_test=DATASET_SPLIT_TEST in split_files,
    )

    n_splits = max(1, len(split_files))
    for s_idx, (split, txt) in enumerate(split_files.items()):
        if txt:
            with open(txt, "r", encoding="utf-8") as f:
                ids = [line.strip() for line in f if line.strip()]
        else:
            ids = list(xmls.keys())
        n_imgs = max(1, len(ids))
        for i_idx, img_id in enumerate(ids):
            src_img = os.path.join(jpeg_dir, f"{img_id}.jpg")
            if os.path.isfile(src_img):
                dst_img = os.path.join(get_dataset_images_dir(yolo_root, split), f"{img_id}.jpg")
                if not os.path.exists(dst_img):
                    shutil.copyfile(src_img, dst_img)

            root_el = xmls.get(img_id)
            lines = []
            if root_el is not None:
                size = root_el.find("size")
                if size is not None:
                    width = int(float(size.findtext("width") or 0))
                    height = int(float(size.findtext("height") or 0))
                else:
                    width = height = 0
                for obj in root_el.iter("object"):
                    name_el = obj.find("name")
                    if name_el is None or not name_el.text:
                        continue
                    class_name = name_el.text.strip()
                    if class_name not in name_to_id:
                        continue
                    class_id = name_to_id[class_name]
                    bbox = obj.find("bndbox")
                    if bbox is None or width <= 0 or height <= 0:
                        continue
                    xmin = float(bbox.findtext("xmin") or 0)
                    ymin = float(bbox.findtext("ymin") or 0)
                    xmax = float(bbox.findtext("xmax") or 0)
                    ymax = float(bbox.findtext("ymax") or 0)
                    bw = xmax - xmin
                    bh = ymax - ymin
                    xc = (xmin + bw / 2.0) / width
                    yc = (ymin + bh / 2.0) / height
                    nw = bw / width
                    nh = bh / height
                    lines.append(f"{class_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

            label_path = os.path.join(get_dataset_labels_dir(yolo_root, split), f"{img_id}.txt")
            with open(label_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            if progress_cb and (i_idx % 50 == 0 or i_idx == n_imgs - 1):
                progress_cb(s_idx, n_splits, i_idx + 1, n_imgs)


def convert_roboflow_to_yolo(rf_root, yolo_root, progress_cb=None):
    """把 Roboflow 导出结果整理为标准 YOLO 结构。"""
    cfg_path = None
    for filename in ROBOFLOW_CONFIG_FILENAMES:
        candidate = os.path.join(rf_root, filename)
        if os.path.isfile(candidate):
            cfg_path = candidate
            break
    if cfg_path is None:
        raise ValueError("Roboflow 数据集无 data.yaml")

    cfg = load_yaml_file(cfg_path, default={})

    src_splits = {}
    if "train" in cfg:
        train_val = cfg.get("train")
        if train_val:
            src_splits[DATASET_SPLIT_TRAIN] = strip_dataset_images_ref(first_non_empty_text(train_val))
        val_val = cfg.get("val")
        if val_val:
            src_splits[DATASET_SPLIT_VAL] = strip_dataset_images_ref(first_non_empty_text(val_val))
        test_val = cfg.get("test")
        if test_val:
            src_splits[DATASET_SPLIT_TEST] = strip_dataset_images_ref(first_non_empty_text(test_val))
    if not src_splits:
        for split in DATASET_SPLITS:
            if os.path.isdir(get_dataset_images_dir(rf_root, split)):
                src_splits[split] = split
    if not src_splits:
        raise ValueError("Roboflow 数据集无 train/val/test 目录")

    for target_split in src_splits:
        os.makedirs(get_dataset_images_dir(yolo_root, target_split), exist_ok=True)
        os.makedirs(get_dataset_labels_dir(yolo_root, target_split), exist_ok=True)

    n_splits = max(1, len(src_splits))
    for s_idx, (target_split, source_split) in enumerate(src_splits.items()):
        src_img_dir = get_dataset_images_dir(rf_root, source_split)
        src_lbl_dir = get_dataset_labels_dir(rf_root, source_split)
        if not os.path.isdir(src_img_dir):
            src_img_dir = os.path.join(rf_root, source_split)
            src_lbl_dir = os.path.join(rf_root, source_split)

        dst_img_dir = get_dataset_images_dir(yolo_root, target_split)
        dst_lbl_dir = get_dataset_labels_dir(yolo_root, target_split)
        images = [
            filename
            for filename in os.listdir(src_img_dir)
            if filename.lower().endswith(IMAGE_FILE_EXTENSIONS) and os.path.isfile(os.path.join(src_img_dir, filename))
        ]
        n_imgs = max(1, len(images))
        for i_idx, filename in enumerate(images):
            src_img = os.path.join(src_img_dir, filename)
            dst_img = os.path.join(dst_img_dir, filename)
            if not os.path.exists(dst_img):
                shutil.copyfile(src_img, dst_img)
            stem = os.path.splitext(filename)[0]
            src_lbl = os.path.join(src_lbl_dir, stem + ".txt")
            if os.path.isfile(src_lbl):
                shutil.copyfile(src_lbl, os.path.join(dst_lbl_dir, stem + ".txt"))
            if progress_cb and (i_idx % 50 == 0 or i_idx == n_imgs - 1):
                progress_cb(s_idx, n_splits, i_idx + 1, n_imgs)

    names = cfg.get("names") or {}
    names_dict = {idx: name for idx, name in enumerate(names)} if isinstance(names, list) else names
    save_standard_dataset_yaml(
        yolo_root,
        dict(sorted(names_dict.items(), key=lambda item: int(item[0]))),
        include_val=True,
        include_test=DATASET_SPLIT_TEST in src_splits,
    )


def format_import_progress_message(phase, fmt, s_idx, n_splits, i_idx, n_imgs):
    """把导入阶段与进度格式化为可展示文案。"""
    if phase == "converting":
        return f"{fmt} 转换中 (split {s_idx + 1}/{n_splits} · {i_idx + 1}/{n_imgs})"
    if phase == "saving":
        return "落盘到项目目录..."
    if phase == "parsing":
        return "解析 zip 包..."
    return phase
