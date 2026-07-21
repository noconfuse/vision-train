"""定义训练评估与推理展示能力表。"""

from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT


def _build_classify_recommendations(results):
    top1 = float(results.get("top1") or 0)
    top5 = float(results.get("top5") or 0)
    suggestions = []
    if top1 >= 0.8:
        suggestions.append({
            "tone": "success",
            "title": "可以进入导出验证",
            "content": "测试集分类准确率已经比较稳定，建议导出模型并用真实业务图片做抽样确认。",
        })
    elif top1 < 0.5:
        suggestions.append({
            "tone": "warn",
            "title": "建议继续补数据或重训",
            "content": "当前分类准确率偏低，优先检查类别边界、补充易混淆样本，再重新训练。",
        })
    if top5 < 0.85:
        suggestions.append({
            "tone": "warn",
            "title": "类别混淆较明显",
            "content": "Top-5 准确率偏低，说明候选类别排序也不稳定，建议重点清洗相近类别的数据。",
        })
    if not suggestions:
        suggestions.append({
            "tone": "info",
            "title": "建议结合业务样本继续验证",
            "content": "测试集结果已经可作为参考，下一步更适合拿真实业务图片做抽样确认。",
        })
    return suggestions


def _build_detect_recommendations(results):
    precision = float(results.get("precision") or 0)
    recall = float(results.get("recall") or 0)
    map50 = float(results.get("map50") or 0)
    map50_95 = float(results.get("map50_95") or 0)
    iou_gap = max(0.0, map50 - map50_95)
    suggestions = []
    if map50_95 >= 0.6 and precision >= 0.7 and recall >= 0.7:
        suggestions.append({
            "tone": "success",
            "title": "可以进入导出验证",
            "content": "测试集整体指标稳定，建议先导出模型做小范围实测，再决定是否直接上线。",
        })
    elif map50_95 < 0.35:
        suggestions.append({
            "tone": "warn",
            "title": "建议继续补数据或重训",
            "content": "测试集整体效果偏弱，继续导出意义不大，优先补充样本和检查标注质量。",
        })
    if recall < 0.6:
        suggestions.append({
            "tone": "warn",
            "title": "Recall 偏低",
            "content": "漏检偏多，建议补充难例、远景、小目标和遮挡场景数据。",
        })
    if precision < 0.6:
        suggestions.append({
            "tone": "warn",
            "title": "Precision 偏低",
            "content": "误报偏多，建议清洗标注，并补充易混淆的负样本场景。",
        })
    if iou_gap > 0.18:
        suggestions.append({
            "tone": "info",
            "title": "定位稳定性一般",
            "content": "mAP50 与 mAP50-95 差距较大，建议检查框标注精度，并适当提升输入分辨率后再观察。",
        })
    if not suggestions:
        suggestions.append({
            "tone": "info",
            "title": "建议结合业务样本继续验证",
            "content": "测试集结果已经可作为参考，下一步更适合拿真实业务场景做抽样确认。",
        })
    return suggestions


_PROFILE_MAP = {
    VISION_TASK_TYPE_CLASSIFY: {
        "metric_guides": {
            "top1": "第一候选命中率，越高越好。",
            "top5": "前五候选命中率，越高说明类别排序越稳定。",
        },
        "training_metric_cards": [
            {"key": "top1", "label": "训练 Top-1", "help_text": "看模型当前最常给出的第一候选是否正确，越高越稳。", "value_class": "text-emerald-700"},
            {"key": "top5", "label": "训练 Top-5", "help_text": "看正确类别是否能稳定出现在前五候选里，越高说明类别区分越清晰。", "value_class": "vt-text-accent"},
        ],
        "evaluate_metric_cards": [
            {"key": "top1", "label": "Top-1", "help_text": "第一候选命中率，越高越好。", "value_class": "text-emerald-700"},
            {"key": "top5", "label": "Top-5", "help_text": "前五候选命中率，越高说明类别排序越稳定。", "value_class": "vt-text-accent"},
        ],
        "inference": {
            "supports_confidence_threshold": False,
            "supports_max_det": False,
            "intro_text": "分类推理展示 Top-5 候选。",
            "result_mode": "classification",
            "meta_mode": "top1_confidence",
        },
        "task_detail": {
            "primary_metric": {"key": "top1", "label": "最新 Top-1", "value_prefix": "Top-1"},
            "secondary_metric": {"key": "top5", "label": "最新 Top-5", "value_prefix": "Top-5"},
            "metric_curve_title": "Metrics (Top-1 / Top-5)",
            "loss_series": [{"key": "train_loss", "label": "Loss", "color": "#3b82f6"}],
            "metric_series": [
                {"key": "top1", "label": "Top-1", "color": "#22c55e"},
                {"key": "top5", "label": "Top-5", "color": "#a855f7"},
            ],
        },
        "recommendations_builder": _build_classify_recommendations,
    },
    VISION_TASK_TYPE_DETECT: {
        "metric_guides": {
            "precision": "关注误报，越高越稳。\n建议区间：>= 0.70 较稳，0.55~0.70 可继续观察，< 0.55 需重点排查误报",
            "recall": "关注漏检，越高越全。\n建议区间：>= 0.70 较稳，0.55~0.70 可继续观察，< 0.55 需重点补漏检样本",
            "map50": "看整体可用性，越高越好。\n建议区间：>= 0.75 表现较好，0.55~0.75 可按场景继续验证，< 0.55 需继续迭代",
            "map50_95": "更严格，适合做最终验收。\n建议区间：>= 0.60 较稳，0.35~0.60 需结合场景验证，< 0.35 不建议直接导出上线",
        },
        "training_metric_cards": [
            {"key": "map50", "label": "训练 mAP50", "help_text": "看整体可用性，越高越好。\n建议区间：>= 0.75 表现较好，0.55~0.75 可按场景继续验证，< 0.55 需继续迭代", "value_class": "text-emerald-700"},
            {"key": "map50_95", "label": "训练 mAP50-95", "help_text": "更严格，适合做最终验收。\n建议区间：>= 0.60 较稳，0.35~0.60 需结合场景验证，< 0.35 不建议直接导出上线", "value_class": "vt-text-accent"},
        ],
        "evaluate_metric_cards": [
            {"key": "precision", "label": "Precision", "help_text": "关注误报，越高越稳。\n建议区间：>= 0.70 较稳，0.55~0.70 可继续观察，< 0.55 需重点排查误报", "value_class": "text-slate-800"},
            {"key": "recall", "label": "Recall", "help_text": "关注漏检，越高越全。\n建议区间：>= 0.70 较稳，0.55~0.70 可继续观察，< 0.55 需重点补漏检样本", "value_class": "text-slate-800"},
            {"key": "map50", "label": "mAP50", "help_text": "看整体可用性，越高越好。\n建议区间：>= 0.75 表现较好，0.55~0.75 可按场景继续验证，< 0.55 需继续迭代", "value_class": "text-emerald-700"},
            {"key": "map50_95", "label": "mAP50-95", "help_text": "更严格，适合做最终验收。\n建议区间：>= 0.60 较稳，0.35~0.60 需结合场景验证，< 0.35 不建议直接导出上线", "value_class": "vt-text-accent"},
        ],
        "inference": {
            "supports_confidence_threshold": True,
            "supports_max_det": True,
            "intro_text": "检测推理展示每张图识别出的目标数量。",
            "result_mode": "detection",
            "meta_mode": "box_count",
        },
        "task_detail": {
            "primary_metric": {"key": "map50", "label": "最新 mAP50", "value_prefix": "mAP50"},
            "secondary_metric": {"key": "map50_95", "label": "综合 mAP50-95", "value_prefix": "mAP50-95"},
            "metric_curve_title": "Metrics (mAP)",
            "loss_series": [
                {"key": "box_loss", "label": "Box", "color": "#ef4444"},
                {"key": "cls_loss", "label": "Cls", "color": "#3b82f6"},
                {"key": "dfl_loss", "label": "Dfl", "color": "#eab308"},
            ],
            "metric_series": [
                {"key": "map50", "label": "mAP50", "color": "#22c55e"},
                {"key": "map50_95", "label": "mAP50-95", "color": "#a855f7"},
            ],
        },
        "recommendations_builder": _build_detect_recommendations,
    },
}


def get_training_result_profile(vision_task_type):
    """返回任务类型对应的完整结果 profile。"""
    profile = _PROFILE_MAP.get(vision_task_type)
    if not profile:
        raise ValueError("当前任务类型暂未接入评估结果展示")
    return profile


def build_training_result_profile(vision_task_type):
    """构造可序列化的结果展示 profile。"""
    profile = get_training_result_profile(vision_task_type)
    return {
        "metric_guides": dict(profile["metric_guides"]),
        "training_metric_cards": [dict(item) for item in profile["training_metric_cards"]],
        "evaluate_metric_cards": [dict(item) for item in profile["evaluate_metric_cards"]],
        "inference": dict(profile["inference"]),
        "task_detail": {
            **profile["task_detail"],
            "primary_metric": dict(profile["task_detail"]["primary_metric"]),
            "secondary_metric": dict(profile["task_detail"]["secondary_metric"]),
            "loss_series": [dict(item) for item in profile["task_detail"]["loss_series"]],
            "metric_series": [dict(item) for item in profile["task_detail"]["metric_series"]],
        },
    }


def build_profile_evaluate_recommendations(results, vision_task_type):
    """按 profile 规则生成评估建议。"""
    return get_training_result_profile(vision_task_type)["recommendations_builder"](results)
