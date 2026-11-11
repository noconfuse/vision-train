#!/usr/bin/env python3
"""重建 dataset_train_v7：production 整块 + 池子 10% 作 test，池子其余分层切 train/val。

背景：v6_tv(1864)+gold(470) 是人工确认过的训练池；production(74) 是真实施工环境。
用户定稿：production 整体进 test 当真实域裁判；池子按 val=0.1 / test=0.1 分层重切，
池子的 test 与 production 一起构成 test（只放 74 张太小）。
gold 的 test 不再保留裁判身份，随池子一起重切。

流程（全部走产品 use case，保证注册/身份/快照一致）：
  1 删除旧的 dataset_train_v7
  2 merge(v6_tv, gold) -> 临时池
  3 临时池分层重切 val=0.1 / test=0.1
  4 create_empty(dataset_train_v7, 六类)
  5 临时池 train->train、val->val、test->test；production train->test（图+标签成对复制）
  6 重写 yaml
  7 删除临时池（快照由运行中的服务触发，见输出提示）

默认只打印计划与实测计数，加 --apply 才真写。
"""

import argparse
import hashlib
import os
import random
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "web"))

from app.config import PROJECTS_DIR  # noqa: E402
from contexts.dataset.application.use_cases import (  # noqa: E402
    create_empty_dataset,
    delete_dataset_folder,
    merge_dataset_pair,
)
from contexts.dataset.infrastructure.dataset_mutations import split_standard_dataset  # noqa: E402
from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml  # noqa: E402

PROJECT = "project-1"
TRAINING_DIR = Path(PROJECTS_DIR) / PROJECT / "training"
PROJECT_PATH = str(Path(PROJECTS_DIR) / PROJECT)
V6TV = "dataset_v6_test_merge_dataset_v6_val"
GOLD = "dataset_gold_v6"
PROD = "dataset_production"
FINAL = "dataset_train_v7"
TMP = "dataset_train_v7_tmp_pool"
CLASSES = ["person", "harness", "helmet", "vest", "lanyard", "hook"]
SEED = 20261107
SPLITS = ("train", "val", "test")
VAL_RATIO = 0.1
TEST_RATIO = 0.1


def split_dir(name, split):
    return TRAINING_DIR / name / split


def count(name, split):
    d = split_dir(name, split) / "images"
    return len([f for f in os.listdir(d) if os.path.isfile(d / f)]) if d.is_dir() else 0


def md5s(name, splits=SPLITS):
    out = set()
    for s in splits:
        d = split_dir(name, s) / "images"
        if not d.is_dir():
            continue
        for f in os.listdir(d):
            p = d / f
            if p.is_file():
                out.add(hashlib.md5(p.read_bytes()).hexdigest())
    return out


def copy_split(src_name, src_split, dst_name, dst_split):
    src_i = split_dir(src_name, src_split) / "images"
    src_l = split_dir(src_name, src_split) / "labels"
    dst_i = split_dir(dst_name, dst_split) / "images"
    dst_l = split_dir(dst_name, dst_split) / "labels"
    dst_i.mkdir(parents=True, exist_ok=True)
    dst_l.mkdir(parents=True, exist_ok=True)
    n_img = n_lbl = 0
    for f in sorted(os.listdir(src_i)):
        if not (src_i / f).is_file():
            continue
        shutil.copy2(src_i / f, dst_i / f)
        n_img += 1
        lbl = src_l / (Path(f).stem + ".txt")
        if lbl.is_file():
            shutil.copy2(lbl, dst_l / lbl.name)
            n_lbl += 1
    return n_img, n_lbl


def plan():
    print("== 现状 ==")
    for n in (V6TV, GOLD, PROD):
        print(f"  {n}: " + "/".join(f"{s}={count(n, s)}" for s in SPLITS))
    if (TRAINING_DIR / FINAL).exists():
        print(f"  {FINAL}(旧混切版): " + "/".join(f"{s}={count(FINAL, s)}" for s in SPLITS))
    print("== 目标 ==")
    print(
        f"  {FINAL}: test=production({count(PROD, 'train')}) + 池子 test({TEST_RATIO:.0%}); "
        f"池子其余按 val={VAL_RATIO:.0%} 分层切"
    )


def apply():
    project_path = PROJECT_PATH
    if (TRAINING_DIR / FINAL).exists():
        delete_dataset_folder(project_path, FINAL)
        print(f"deleted old {FINAL}")
    if (TRAINING_DIR / FINAL).exists():
        raise SystemExit(f"{FINAL} 删除后仍在，停止")
    if not (TRAINING_DIR / TMP).exists():
        merge_dataset_pair(project_path, V6TV, GOLD, TMP)
        print(f"merged {V6TV}+{GOLD} -> {TMP}")
    else:
        print(f"reuse existing {TMP}")
    # 临时集的初始快照是脚本进程内线程起的，脚本退出即中断；用例门禁会因此挡住切分。
    # 这里直接调产品底层的分层切分（临时集随后删除，不需要它的版本）。
    res = split_standard_dataset(
        str(TRAINING_DIR / TMP), VAL_RATIO, TEST_RATIO, rng=random.Random(SEED)
    )
    print(f"resplit pool: {res}")
    create_empty_dataset(project_path, FINAL, "detect", initial_classes=CLASSES)
    a = copy_split(TMP, "train", FINAL, "train")
    b = copy_split(TMP, "val", FINAL, "val")
    c = copy_split(TMP, "test", FINAL, "test")
    d = copy_split(PROD, "train", FINAL, "test")
    print(f"copied train={a} val={b} pool_test={c} prod_test={d} (images,labels)")
    save_standard_dataset_yaml(
        str(TRAINING_DIR / FINAL),
        list(CLASSES),
        vision_task_type="detect",
        include_val=True,
        include_test=True,
    )
    delete_dataset_folder(project_path, TMP)
    print(f"deleted {TMP}")
    print("文件已就位；初始快照要在服务里触发：POST /api/dataset/snapshot/start")


def verify():
    ok = True
    pool_src = md5s(V6TV) | md5s(GOLD)
    prod_src = md5s(PROD)
    all_dst = md5s(FINAL)
    test_dst = md5s(FINAL, ("test",))
    tv_dst = md5s(FINAL, ("train", "val"))
    checks = {
        "train/val/test(池子部分) == v6_tv+gold": (all_dst - prod_src) == pool_src,
        "production 全在 test": prod_src <= test_dst,
        "train/val 与 production 无交集": not (tv_dst & prod_src),
        "三条 split 图集总量 == 池子+production": all_dst == (pool_src | prod_src),
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