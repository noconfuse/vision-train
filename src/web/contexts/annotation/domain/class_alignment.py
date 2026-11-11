"""校验模型类别与数据集类别是否对齐，防止把模型自己的类别号写进标签。

预训练模型的类别号是它自己的编号（COCO 的 5 是大象、19 是猫），和数据集 dataset.yaml
里的编号没有对应关系。一旦把这些号写进标签，数据集类别表会长出占位类别，训练也会因
类别数对不上而报错。所以写入前必须当场校验，不匹配就停下讲清楚是哪几个号。
"""


def normalize_class_name(name):
    """归一化类别名，用于比较模型与数据集是否指的是同一个类。"""
    return str(name if name is not None else "").strip().lower()


def normalize_model_names(model_names):
    """把模型暴露的类别名统一成 {int 下标: 名称} 字典。"""
    if not model_names:
        return {}
    if isinstance(model_names, dict):
        resolved = {}
        for key, value in model_names.items():
            try:
                resolved[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
        return resolved
    if isinstance(model_names, (list, tuple)):
        return {idx: str(name) for idx, name in enumerate(model_names)}
    return {}


def class_ids_from_annotation(annotation, vision_task_type):
    """收集一次自动标注载荷里用到的类别号。"""
    payload = annotation or {}
    raw_ids = []
    if payload.get("class_id") is not None:
        raw_ids.append(payload.get("class_id"))
    for key in ("boxes", "polygons", "instances"):
        for item in payload.get(key) or []:
            if isinstance(item, dict):
                raw_ids.append(item.get("class"))
    resolved = []
    for value in raw_ids:
        try:
            resolved.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(resolved))


def class_ids_from_label_lines(lines):
    """从 YOLO 标签行首列收集类别号，用于审核与提交前的兜底校验。"""
    resolved = []
    for line in lines or []:
        tokens = str(line).split()
        if not tokens:
            continue
        try:
            resolved.append(int(float(tokens[0])))
        except ValueError:
            continue
    return sorted(set(resolved))


def describe_dataset_classes(dataset_names):
    """把数据集类别表写成一句人能读的话。"""
    names = list(dataset_names or [])
    if not names:
        return "该数据集还没有类别"
    shown = "、".join(f"{idx}:{name}" for idx, name in enumerate(names[:12]))
    if len(names) > 12:
        shown += f"…（共 {len(names)} 类）"
    return shown


def find_out_of_range_class_ids(class_ids, dataset_names):
    """返回数据集类别表里根本不存在的类别号。"""
    total = len(dataset_names or [])
    return sorted({cid for cid in class_ids if cid < 0 or cid >= total})


def find_mismatched_class_ids(model_names, dataset_names, class_ids):
    """返回类别号存在但名称对不上的项：{类别号: (模型名称, 数据集名称)}。"""
    mismatches = {}
    for class_id in class_ids:
        model_name = model_names.get(class_id)
        if model_name is None:
            mismatches[class_id] = ("", str((dataset_names or [])[class_id]))
            continue
        dataset_name = (dataset_names or [])[class_id] if class_id < len(dataset_names or []) else None
        if dataset_name is None or normalize_class_name(model_name) != normalize_class_name(dataset_name):
            mismatches[class_id] = (str(model_name), str(dataset_name))
    return dict(sorted(mismatches.items()))


def require_auto_classes_writable(model_names, dataset_names, class_ids):
    """推断结果落盘前的校验：类别号必须存在且与模型同名，否则报错停下。"""
    if not class_ids:
        return
    if not dataset_names:
        raise ValueError(
            "该数据集还没有类别表（dataset.yaml 缺 names），无法校验模型类别：请先在数据集里添加类别。"
        )
    if not model_names:
        raise ValueError(
            "无法确认模型的类别名，不能把推断结果写进标签：请使用带类别名的模型（训练产出的权重或预训练权重文件）"
        )
    out_of_range = find_out_of_range_class_ids(class_ids, dataset_names)
    if out_of_range:
        details = "、".join(
            f"{cid}（模型里叫「{model_names.get(cid, '未知')}」）" for cid in out_of_range[:6]
        )
        raise ValueError(
            f"模型类别与数据集对不上：推断结果用到了数据集里没有的类别号 {details}。"
            f"{describe_dataset_classes(dataset_names)}。"
            "请换用在该数据集上训练出的权重，或先补齐数据集类别。"
        )
    mismatches = find_mismatched_class_ids(model_names, dataset_names, class_ids)
    if mismatches:
        details = "、".join(
            f"{cid}（模型叫「{model_name}」，数据集叫「{dataset_name}」）"
            for cid, (model_name, dataset_name) in list(mismatches.items())[:6]
        )
        raise ValueError(
            f"模型类别与数据集对不上：同样的类别号在两边指的不是同一个类——{details}。"
            "推理结果不会写入，请换用在该数据集上训练出的权重。"
        )


def require_label_classes_writable(dataset_names, class_ids, source_hint=""):
    """没有模型类别名可对照时（如逐框接受）的兜底校验：类别号必须在数据集类别表内。

    数据集没有声明类别表时无从比对（dataset.yaml 缺 names），此时不设限；
    推断落盘那一步由 require_auto_classes_writable 严格要求，不会静默写入无效类别。
    """
    if not dataset_names:
        return
    out_of_range = find_out_of_range_class_ids(class_ids, dataset_names)
    if not out_of_range:
        return
    suffix = f"（出处：{source_hint}）" if source_hint else ""
    raise ValueError(
        f"这些类别号在数据集类别表里不存在：{out_of_range[:6]}{suffix}。"
        f"{describe_dataset_classes(dataset_names)}。"
        "接受它们会把标签写成无效类别，请先在数据集里补上对应类别，或直接拒绝这些框。"
    )
