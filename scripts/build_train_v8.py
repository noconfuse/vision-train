#!/usr/bin/env python3
"""重建 dataset_train_v8：把 production 视频按时间拆开，前半段进 train。

背景：v7 的 train 里没有任何真实域图，production 74 张全在 test；训练在真实域
harness/hook 上明显退化。production 74 张来自 ``video.mp4``（2402 帧/30fps/80s），
按 1fps 抽帧，因此 train/test 只能按时间切，并留缓冲帧避免相邻帧跨越边界。

规则（production 帧号 = 文件名 video_f<idx>.jpg）：
  idx <= 1500      -> train（前 50 秒，44 张）
  1500 < idx < 1800 -> 丢弃（10 秒缓冲，9 张）
  idx >= 1800      -> test（后 20 秒，21 张）
池子（v7 的 train/val/test 中非 production 部分）原样保留。

流程：删除旧 v8 -> create_empty(六类) -> 按规则复制 -> 重写 yaml；
快照由运行中的服务触发：POST /api/dataset/snapshot/start。
默认只打印计划与实测计数，加 --apply 才真写。
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "web"))

from app.config import PROJECTS_DIR  # noqa: E402
from contexts.dataset.application.use_cases import (  # noqa: E402
    create_empty_dataset,
    delete_dataset_folder,
)
from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml  # noqa: E402

PROJECT = "project-1"
TRAINING_DIR = Path(PROJECTS_DIR) / PROJECT / "training"
PROJECT_PATH = str(Path(PROJECTS_DIR) / PROJECT)
SRC = "dataset_train_v7"
FINAL = "dataset_train_v8"
CLASSES = ["person", "harness", "helmet", "vest", "lanyard", "hook"]
SPLITS = ("train", "val", "test")
TRAIN_MAX_FRAME = 1500
TEST_MIN_FRAME = 1800
PROD_FRAME_RE = re.compile(r"^video_f(\d+)$")


def split_dir(name, split):
    return TRAINING_DIR / name / split


def count(name, split):
    d = split_dir(name, split) / "images"
    return len([f for f in os.listdir(d) if os.path.isfile(d / f)]) if d.is_dir() else 0


def md5s(name, splits=SPLITS, keep=None):
    out = set()
    for s in splits:
        d = split_dir(name, s) / "images"
        if not d.is_dir():
            continue
        for f in os.listdir(d):
            p = d / f
            if p.is_file() and (keep is None or keep(f)):
                out.add(hashlib.md5(p.read_bytes()).hexdigest())
    return out


def prod_frame_index(filename):
    m = PROD_FRAME_RE.match(Path(filename).stem)
    return int(m.group(1)) if m else None


def is_prod(filename):
    return prod_frame_index(filename) is not None


def copy_split(src_name, src_split, dst_name, dst_split, keep=None):
    src_i = split_dir(src_name, src_split) / "images"
    src_l = split_dir(src_name, src_split) / "labels"
    dst_i = split_dir(dst_name, dst_split) / "images"
    dst_l = split_dir(dst_name, dst_split) / "labels"
    dst_i.mkdir(parents=True, exist_ok=True)
    dst_l.mkdir(parents=True, exist_ok=True)
    n_img = n_lbl = 0
    for f in sorted(os.listdir(src_i)):
        if not (src_i / f).is_file() or (keep is not None and not keep(f)):
            continue
        shutil.copy2(src_i / f, dst_i / f)
        n_img += 1
        lbl = src_l / (Path(f).stem + ".txt")
        if lbl.is_file():
            shutil.copy2(lbl, dst_l / lbl.name)
            n_lbl += 1
    return n_img, n_lbl


def prod_counts(name):
    train = test = dropped = 0
    d = split_dir(name, "test") / "images"
    for f in os.listdir(d) if d.is_dir() else ():
        idx = prod_frame_index(f)
        if idx is None:
            continue
        if idx <= TRAIN_MAX_FRAME:
            train += 1
        elif idx >= TEST_MIN_FRAME:
            test += 1
        else:
            dropped += 1
    return train, test, dropped


def plan():
    print("== 现状 ==")
    for s in SPLITS:
        print(f"  {SRC}/{s}: images={count(SRC, s)}")
    tr, te, drop = prod_counts(SRC)
    print(f"  production 帧(在 {SRC}/test 中): train={tr} test={te} drop={drop}")
    print("== 目标 ==")
    print(f"  {FINAL}/train = 池子 train + production<= {TRAIN_MAX_FRAME} 帧 -> {count(SRC, 'train') + tr}")
    print(f"  {FINAL}/val   = 池子 val -> {count(SRC, 'val')}")
    print(
        f"  {FINAL}/test  = 池子 test + production>= {TEST_MIN_FRAME} 帧 -> "
        f"{count(SRC, 'test') - tr - te - drop + te}"
    )
    print(f"  丢弃 production 帧 {drop} 张（{TRAIN_MAX_FRAME}-{TEST_MIN_FRAME} 之间作缓冲）")


def apply():
    if (TRAINING_DIR / FINAL).exists():
        delete_dataset_folder(PROJECT_PATH, FINAL)
        print(f"deleted old {FINAL}")
    if (TRAINING_DIR / FINAL).exists():
        raise SystemExit(f"{FINAL} 删除后仍在，停止")
    create_empty_dataset(PROJECT_PATH, FINAL, "detect", initial_classes=CLASSES)
    print(f"created {FINAL}")
    keep_pool = lambda f: not is_prod(f)  # noqa: E731
    a = copy_split(SRC, "train", FINAL, "train")
    b = copy_split(SRC, "val", FINAL, "val")
    c = copy_split(SRC, "test", FINAL, "test", keep=keep_pool)
    d = copy_split(
        SRC, "test", FINAL, "train",
        keep=lambda f: (prod_frame_index(f) is not None and prod_frame_index(f) <= TRAIN_MAX_FRAME),  # noqa: E731
    )
    e = copy_split(
        SRC, "test", FINAL, "test",
        keep=lambda f: (prod_frame_index(f) is not None and prod_frame_index(f) >= TEST_MIN_FRAME),  # noqa: E731
    )
    print(f"copied pool train={a} val={b} test={c} prod_train={d} prod_test={e} (images,labels)")
    save_standard_dataset_yaml(
        str(TRAINING_DIR / FINAL),
        list(CLASSES),
        vision_task_type="detect",
        include_val=True,
        include_test=True,
    )
    print("文件已就位；初始快照要在服务里触发：POST /api/dataset/snapshot/start")


def verify():
    ok = True
    dropped = md5s(
        SRC, ("test",),
        keep=lambda f: (prod_frame_index(f) is not None and TRAIN_MAX_FRAME < prod_frame_index(f) < TEST_MIN_FRAME),
    )
    prod_src = md5s(SRC, ("test",), keep=is_prod)
    prod_train_src = md5s(
        SRC, ("test",),
        keep=lambda f: (prod_frame_index(f) is not None and prod_frame_index(f) <= TRAIN_MAX_FRAME),
    )
    prod_test_src = md5s(
        SRC, ("test",),
        keep=lambda f: (prod_frame_index(f) is not None and prod_frame_index(f) >= TEST_MIN_FRAME),
    )
    src_all = md5s(SRC)
    dst_all = md5s(FINAL)
    dst_train = md5s(FINAL, ("train",))
    dst_test = md5s(FINAL, ("test",))
    checks = {
        "v8 图集 == v7 图集 - 9 张缓冲帧": dst_all == (src_all - dropped),
        "缓冲帧一张没进 v8": not (dst_all & dropped),
        "production train 44 张全在 train": len(prod_train_src) == 44 and prod_train_src <= dst_train,
        "production test 21 张全在 test": len(prod_test_src) == 21 and prod_test_src <= dst_test,
        "train 与 test 无交集": not (dst_train & dst_test),
        f"train == {count(SRC, 'train') + 44}": count(FINAL, "train") == count(SRC, "train") + 44,
        "val == 219": count(FINAL, "val") == count(SRC, "val"),
        f"test == {count(SRC, 'test') - 74 + 21}": count(FINAL, "test") == count(SRC, "test") - 74 + 21,
    }
    for s in SPLITS:
        checks[f"{s} labels==images"] = count(FINAL, s) == len(
            [f for f in os.listdir(split_dir(FINAL, s) / "labels") if f.endswith(".txt")]
        )
    for k, v in checks.items():
        print(f"  [{'OK' if v else 'FAIL'}] {k}")
        ok = ok and v
    print("== 最终计数 ==")
    for s in SPLITS:
        print(f"  {s}: images={count(FINAL, s)}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写；默认只打印计划")
    args = ap.parse_args()
    plan()
    if not args.apply:
        print("\n(dry-run；加 --apply 执行)")
        return
    apply()
    print("== 校验 ==")
    sys.exit(0 if verify() else 1)


if __name__ == "__main__":
    main()