"""解析评估数据集配置并生成结果建议。"""

from contexts.dataset.infrastructure.dataset_schema import load_dataset_yaml_ref


def resolve_evaluate_split(data_yaml):
    """Pick the evaluation split, preferring `test` when the dataset declares it."""
    config = load_dataset_yaml_ref(data_yaml, default={})
    test_split = str(config.get('test') or '').strip()
    if test_split:
        return 'test'
    return 'val'


def build_evaluate_recommendations(results):
    """Generate lightweight product-facing suggestions from evaluation metrics."""
    precision = float(results.get('precision') or 0)
    recall = float(results.get('recall') or 0)
    map50 = float(results.get('map50') or 0)
    map50_95 = float(results.get('map50_95') or 0)
    iou_gap = max(0.0, map50 - map50_95)
    suggestions = []

    if map50_95 >= 0.6 and precision >= 0.7 and recall >= 0.7:
        suggestions.append({
            'tone': 'success',
            'title': '可以进入导出验证',
            'content': '测试集整体指标稳定，建议先导出模型做小范围实测，再决定是否直接上线。',
        })
    elif map50_95 < 0.35:
        suggestions.append({
            'tone': 'warn',
            'title': '建议继续补数据或重训',
            'content': '测试集整体效果偏弱，继续导出意义不大，优先补充样本和检查标注质量。',
        })

    if recall < 0.6:
        suggestions.append({
            'tone': 'warn',
            'title': 'Recall 偏低',
            'content': '漏检偏多，建议补充难例、远景、小目标和遮挡场景数据。',
        })

    if precision < 0.6:
        suggestions.append({
            'tone': 'warn',
            'title': 'Precision 偏低',
            'content': '误报偏多，建议清洗标注，并补充易混淆的负样本场景。',
        })

    if iou_gap > 0.18:
        suggestions.append({
            'tone': 'info',
            'title': '定位稳定性一般',
            'content': 'mAP50 与 mAP50-95 差距较大，建议检查框标注精度，并适当提升输入分辨率后再观察。',
        })

    if not suggestions:
        suggestions.append({
            'tone': 'info',
            'title': '建议结合业务样本继续验证',
            'content': '测试集结果已经可作为参考，下一步更适合拿真实业务场景做抽样确认。',
        })

    return suggestions
