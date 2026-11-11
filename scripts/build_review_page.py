#!/usr/bin/env python3
"""为整理产物生成可交互的复核页面 review.html。

页面按复核标记（no_person / person_only / closeup / extreme_closeup /
product_like / dense）分组展示原图，叠加已有标注框，支持逐张标记「隔离」，
并导出可直接喂给 curate_ppe_dataset.py 的 manual_quarantine.csv。
标记结果存在浏览器 localStorage，刷新不丢。
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CURATION = REPO_ROOT / "projects/project-1/training/curation"

CLASS_NAMES = {
    0: "person",
    1: "harness",
    2: "no_harness",
    3: "helmet",
    4: "no_helmet",
    5: "vest",
    6: "no_vest",
    7: "lanyard",
    8: "hook",
}
CLASS_COLORS = {
    0: "#22d3ee",
    1: "#22c55e",
    2: "#84cc16",
    3: "#a855f7",
    4: "#d946ef",
    5: "#f59e0b",
    6: "#fb7185",
    7: "#3b82f6",
    8: "#ef4444",
}
FLAG_HINTS = {
    "no_person": "有标注框但没有 person 框：多为漏标人员，也可能是安全带产品图",
    "person_only": "只有 person 框：真实工人漏标 PPE，或鞋/人像等无关图",
    "closeup": "person 面积 ≥ 40%：特写图，PPE 可见性差",
    "extreme_closeup": "person 面积 ≥ 60%：极近特写，基本无法判定穿戴",
    "product_like": "无 person 且大面积白底：产品图/假人模特，高置信噪声",
    "dense": "单图 > 30 个框：抽查标注完整性",
}
FLAG_ORDER = ("product_like", "extreme_closeup", "person_only", "no_person", "closeup", "dense")

# 金标清单（gold_set.csv 的 priorities 列）用这套分组名和说明
PRIORITY_LABELS = {
    "harness_unjudged_vest": "已标安全带但背心状态完全未标：这批是补 no_vest / vest 的主力",
    "harness_and_no_vest": "安全带 + 无背心同框：背心和安全带解耦的证据",
    "vest_and_no_harness": "背心 + 无安全带同框：反方向解耦证据",
    "vest_and_harness": "背心和安全带同框：重叠框几何怎么画",
    "vest_present": "已有反光背心标注：稀有类，全数据集只有 311 张",
    "no_vest_present": "已标无背心：核对框的是肩到髋的可见躯干，不是整个人",
    "hook_real_scene": "真实场景（非 F13 产品图）里的钩子：按新口径只有真挂住结构物才标",
    "hook_and_lanyard": "钩子和安全绳同框：高挂低用要靠这两个框的几何推",
    "lanyard_with_person": "有安全绳且有人员：核对绳的走向和挂点高度",
    "helmet_and_no_helmet": "戴头盔与未戴同框：正负对照",
    "person_no_ppe": "有人但 PPE 一个没标：从零补标，教师最缺这类",
}


def read_review_rows(curation: Path, csv_name: str = "review.csv"):
    """读取复核/金标清单 CSV，返回带绝对路径的条目。"""
    path = curation / csv_name
    if not path.is_file():
        raise SystemExit(f"缺少 {path}，请先运行对应的整理/抽样脚本")
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            abs_path = (row.get("abs") or "").strip()
            if not abs_path:
                continue
            rows.append((Path(abs_path), row))
    return rows


def read_boxes(image_path: Path):
    """读取图片对应标签，返回 [(class_id, left%, top%, width%, height%)]。"""
    parts = list(image_path.parts)
    index = len(parts) - 1 - parts[::-1].index("images")
    parts[index] = "labels"
    label_path = Path(*parts).with_suffix(".txt")
    boxes = []
    if not label_path.is_file():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        class_id = int(float(fields[0]))
        cx, cy, w, h = (float(value) for value in fields[1:5])
        boxes.append(
            [class_id, round((cx - w / 2) * 100, 3), round((cy - h / 2) * 100, 3), round(w * 100, 3), round(h * 100, 3)]
        )
    return boxes


def build_items(rows, dataset_root: Path, tab_field: str = "flags"):
    """把 review.csv 行转成页面用的条目。"""
    items = []
    for image_path, row in rows:
        try:
            rel = image_path.relative_to(dataset_root).as_posix()
        except ValueError:
            rel = str(image_path)
        items.append(
            {
                "abs": str(image_path),
                "uri": image_path.as_uri(),
                "rel": rel,
                "split": row.get("split", ""),
                "source": row.get("source", ""),
                "flags": [flag for flag in (row.get(tab_field) or "").split(";") if flag],
                "person": int(row.get("person") or 0),
                "boxes": int(row.get("boxes") or 0),
                "personArea": round(float(row.get("person_area_max") or 0) * 100, 1),
                "white": round(float(row.get("white_ratio") or 0) * 100, 1),
                "classes": row.get("classes", ""),
                "labels": read_boxes(image_path),
            }
        )
    return items


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #0b0f14; color: #e5e7eb; font: 14px/1.5 -apple-system, "PingFang SC", sans-serif; }
  header { position: sticky; top: 0; z-index: 5; background: #0b0f14ee; backdrop-filter: blur(6px);
           border-bottom: 1px solid #1f2937; padding: 12px 18px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
  header h1 { font-size: 16px; margin: 0 12px 0 0; font-weight: 600; }
  .tabs { display: flex; flex-wrap: wrap; gap: 6px; }
  .tab { padding: 5px 10px; border-radius: 6px; border: 1px solid #273041; background: #131a24; cursor: pointer; font-size: 13px; }
  .tab.active { background: #1d4ed8; border-color: #3b82f6; color: #fff; }
  .tab .n { opacity: .7; margin-left: 4px; }
  .spacer { flex: 1; }
  button.act { padding: 6px 12px; border-radius: 6px; border: 1px solid #273041; background: #131a24; color: #e5e7eb; cursor: pointer; }
  button.act.primary { background: #b91c1c; border-color: #ef4444; color: #fff; }
  #hint { padding: 8px 18px; color: #9ca3af; font-size: 13px; border-bottom: 1px solid #1f2937; }
  #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; padding: 16px 18px; }
  .card { background: #10161f; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden; }
  .card.marked { border-color: #ef4444; box-shadow: 0 0 0 1px #ef4444 inset; }
  .shot { position: relative; width: 100%; aspect-ratio: 4 / 3; background: #05070a; }
  .shot img { width: 100%; height: 100%; object-fit: contain; display: block; }
  .box { position: absolute; border: 1.5px solid; pointer-events: none; }
  .box span { position: absolute; top: -14px; left: -1px; font-size: 10px; padding: 0 3px; background: #000000b3; white-space: nowrap; }
  .meta { padding: 8px 10px; font-size: 12px; color: #9ca3af; word-break: break-all; }
  .meta b { color: #e5e7eb; font-weight: 500; }
  .row { display: flex; gap: 6px; align-items: center; margin-top: 6px; }
  .chip { font-size: 11px; padding: 1px 6px; border-radius: 999px; background: #1f2937; color: #cbd5e1; }
  .name { font-size: 11px; color: #6b7280; margin-top: 4px; }
  #more { display: block; margin: 4px auto 28px; padding: 8px 20px; }
  .legend { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; }
  .legend i { display: inline-block; width: 10px; height: 10px; margin-right: 4px; border-radius: 2px; }
  a { color: #60a5fa; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="tabs" id="tabs"></div>
  <div class="spacer"></div>
  <select class="act" id="sort">
    <option value="">默认顺序</option>
    <option value="white">白底比例 高→低</option>
    <option value="personArea">人体占比 大→小</option>
    <option value="boxes">框数 多→少</option>
  </select>
  <div class="legend" id="legend"></div>
  <button class="act" id="hideMarked">隐藏已标记</button>
  <button class="act" id="clearMarks">清空标记</button>
  <button class="act" id="copyList">__COPY_LABEL__</button>
  <button class="act primary" id="export">导出本次标记</button>
</header>
<div id="hint"></div>
<div id="grid"></div>
<button class="act" id="more">继续加载</button>
<script>
const ITEMS = __ITEMS__;
const FLAG_ORDER = __FLAG_ORDER__;
const LABELS = __LABELS__;
const FLAG_HINTS = __FLAG_HINTS__;
const CLASS_NAMES = __CLASS_NAMES__;
const CLASS_COLORS = __CLASS_COLORS__;
const PAGE = 120;
const store = JSON.parse(localStorage.getItem('__STORAGE_KEY__') || '{}');
let tab = FLAG_ORDER.find(flag => ITEMS.some(i => i.flags.includes(flag))) || 'all';
let shown = PAGE;
let hideMarked = false;
let sortBy = '';

function save() { localStorage.setItem('ppe-review-marks', JSON.stringify(store)); }
function bucket(item) {
  if (tab === 'all') return true;
  if (tab === 'marked') return !!store[item.abs];
  return item.flags.includes(tab);
}
function list() { return ITEMS.filter(item => bucket(item) && (!hideMarked || !store[item.abs])); }
function sorted(items) {
  if (!sortBy) return items;
  return [...items].sort((a, b) => (b[sortBy] || 0) - (a[sortBy] || 0));
}

function renderTabs() {
  const counts = { all: ITEMS.length, marked: Object.values(store).filter(Boolean).length };
  FLAG_ORDER.forEach(flag => { counts[flag] = ITEMS.filter(i => i.flags.includes(flag)).length; });
  const tabs = [['all', '全部'], ...FLAG_ORDER.filter(f => counts[f]).map(f => [f, LABELS[f] || f]), ['marked', '已标记']];
  document.getElementById('tabs').innerHTML = tabs.map(([key, label]) =>
    `<div class="tab ${key === tab ? 'active' : ''}" data-tab="${key}">${label}<span class="n">${counts[key] || 0}</span></div>`).join('');
  document.querySelectorAll('.tab').forEach(el => el.onclick = () => { tab = el.dataset.tab; shown = PAGE; render(); });
}

function renderLegend() {
  document.getElementById('legend').innerHTML = Object.entries(CLASS_NAMES).map(([id, name]) =>
    `<span><i style="background:${CLASS_COLORS[id]}"></i>${name}</span>`).join('');
}

function card(item) {
  const boxes = item.labels.map(([cls, l, t, w, h]) =>
    `<div class="box" style="left:${l}%;top:${t}%;width:${w}%;height:${h}%;border-color:${CLASS_COLORS[cls] || '#fff'}">
       <span style="color:${CLASS_COLORS[cls] || '#fff'}">${CLASS_NAMES[cls] || cls}</span></div>`).join('');
  const chips = item.flags.map(f => `<span class="chip">${f}</span>`).join('');
  const marked = !!store[item.abs];
  return `<div class="card ${marked ? 'marked' : ''}">
    <div class="shot"><img loading="lazy" src="${item.uri}">${boxes}</div>
    <div class="meta">
      <div><b>${item.split}</b> · ${item.source} · person ${item.person} · 框 ${item.boxes} · 人体占比 ${item.personArea}% · 白底 ${item.white}%</div>
      <div class="row">${chips}</div>
      <div class="name">${item.rel}</div>
      <div class="row">
        <a href="${item.uri}">打开原图</a>
        <span class="spacer"></span>
        <button class="act" data-mark="${item.abs}">${marked ? '__UNMARK_LABEL__' : '__MARK_LABEL__'}</button>
      </div>
    </div>
  </div>`;
}

function render() {
  renderTabs();
  const items = sorted(list());
  const hint = tab === 'all' ? '__HINT_ALL__'
    : tab === 'marked' ? '__HINT_MARKED__'
    : (FLAG_HINTS[tab] || '');
  document.getElementById('hint').textContent = `${hint}　当前 ${items.length} 张，已显示 ${Math.min(shown, items.length)} 张。`;
  document.getElementById('grid').innerHTML = items.slice(0, shown).map(card).join('');
  document.getElementById('more').style.display = items.length > shown ? 'block' : 'none';
  document.querySelectorAll('[data-mark]').forEach(el => el.onclick = () => {
    const key = el.dataset.mark;
    if (store[key]) delete store[key]; else store[key] = tab;
    save(); render();
  });
}

function markedList() {
  return ITEMS.filter(i => store[i.abs])
    .map(i => `${i.abs},${store[i.abs]}`);
}

document.getElementById('more').onclick = () => { shown += PAGE; render(); };
document.getElementById('sort').onchange = e => { sortBy = e.target.value; shown = PAGE; render(); };
document.getElementById('hideMarked').onclick = () => { hideMarked = !hideMarked; shown = PAGE; render(); };
document.getElementById('export').onclick = () => {
  const text = 'abs,reason\\n' + markedList().join('\\n') + '\\n';
  const blob = new Blob([text], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '__EXPORT_NAME__';
  a.click();
};
document.getElementById('clearMarks').onclick = () => {
  if (!confirm('清空本页所有「__MARK_LABEL__」记录？不会改动任何文件。')) return;
  Object.keys(store).forEach(k => delete store[k]);
  save(); render();
};
document.getElementById('copyList').onclick = async () => {
  await navigator.clipboard.writeText(markedList().join('\\n'));
  document.getElementById('copyList').textContent = '已复制';
  setTimeout(() => document.getElementById('copyList').textContent = '__COPY_LABEL__', 1500);
};
renderLegend();
render();
</script>
</body>
</html>
"""


def render_page(items, opts):
    """把条目嵌入模板。"""
    html = (
        TEMPLATE
        .replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
        .replace("__FLAG_ORDER__", json.dumps(list(opts["flag_order"])))
        .replace("__FLAG_HINTS__", json.dumps(opts["hints"], ensure_ascii=False))
        .replace("__LABELS__", json.dumps(opts["labels"], ensure_ascii=False))
        .replace("__TITLE__", opts["title"])
        .replace("__STORAGE_KEY__", opts["storage_key"])
        .replace("__MARK_LABEL__", opts["mark_label"])
        .replace("__UNMARK_LABEL__", opts["unmark_label"])
        .replace("__COPY_LABEL__", opts["copy_label"])
        .replace("__EXPORT_NAME__", opts["export_name"])
        .replace("__HINT_ALL__", opts["hint_all"])
        .replace("__HINT_MARKED__", opts["hint_marked"])
        .replace("__CLASS_NAMES__", json.dumps({str(k): v for k, v in CLASS_NAMES.items()}, ensure_ascii=False))
        .replace("__CLASS_COLORS__", json.dumps({str(k): v for k, v in CLASS_COLORS.items()}, ensure_ascii=False))
    )
    return html


def main():
    parser = argparse.ArgumentParser(description="生成交互复核页面（review.html / gold.html）")
    parser.add_argument("--curation", default=str(DEFAULT_CURATION))
    parser.add_argument("--dataset", default=str(REPO_ROOT / "projects/project-1/training/dataset"))
    parser.add_argument("--out", default=None, help="输出 HTML 路径，默认 <curation>/review.html")
    parser.add_argument("--csv", default="review.csv", help="<curation> 下的清单文件名")
    parser.add_argument("--tab-field", default="flags", help="用哪一列分组，金标清单用 priorities")
    args = parser.parse_args()

    curation = Path(args.curation).resolve()
    dataset = Path(args.dataset).resolve()
    rows = read_review_rows(curation, args.csv)
    items = build_items(rows, dataset, args.tab_field)

    if args.tab_field == "flags":
        flag_order = [flag for flag in FLAG_ORDER if any(flag in item["flags"] for item in items)]
        hints = FLAG_HINTS
        labels = {}
        title = "PPE 数据集复核"
        storage_key = "ppe-review-marks"
        mark_label, unmark_label = "标记隔离", "取消标记"
        copy_label = "复制隔离清单"
        export_name = "manual_quarantine.new.csv"
        hint_all = "全部被标记过复核条件的图片。"
        hint_marked = "你已标记隔离的图片；点「导出本次标记」得到 manual_quarantine.new.csv，把它并进 curation/manual_quarantine.csv 后重跑整理脚本才生效。"
    else:
        counts = Counter(flag for item in items for flag in item["flags"])
        flag_order = [flag for flag, _ in counts.most_common()]
        hints = PRIORITY_LABELS
        labels = {key: key for key in flag_order}
        title = f"PPE 金标清单（{len(items)} 张，分层抽样）"
        storage_key = "ppe-gold-done"
        mark_label, unmark_label = "标完了", "撤回「标完了」"
        copy_label = "复制已标完清单"
        export_name = "gold_done.csv"
        hint_all = "这批图按来源 × 人数 × 现有穿戴状态分层抽出来，手工标完用来训教师模型；分组名就是它被抽进来的原因。"
        hint_marked = "你已点过「标完了」的图；导出 gold_done.csv 只做进度记录，标注结果本身已经写进数据集的 labels 目录。"
        print(f"金标页面分组：{', '.join(f'{flag} {counts[flag]}' for flag in flag_order)}")

    opts = {
        "flag_order": flag_order,
        "hints": hints,
        "labels": labels,
        "title": title,
        "storage_key": storage_key,
        "mark_label": mark_label,
        "unmark_label": unmark_label,
        "copy_label": copy_label,
        "export_name": export_name,
        "hint_all": hint_all,
        "hint_marked": hint_marked,
    }
    target = Path(args.out).resolve() if args.out else curation / "review.html"
    target.write_text(render_page(items, opts), encoding="utf-8")
    invalid = sum(1 for item in items if not Path(item["abs"]).is_file())
    print(f"页面: {target}")
    print(f"  条目 {len(items)} 张；路径失效 {invalid} 张；分组分布 " + json.dumps({flag: sum(1 for i in items if flag in i['flags']) for flag in flag_order}, ensure_ascii=False))


if __name__ == "__main__":
    main()
