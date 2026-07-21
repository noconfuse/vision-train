const UNSUPPORTED_PROFILE = Object.freeze({
  metric_guides: {},
  training_metric_cards: [],
  evaluate_metric_cards: [],
  inference: {
    supports_confidence_threshold: false,
    supports_max_det: false,
    intro_text: '',
    result_mode: 'unsupported',
    meta_mode: 'plain',
  },
  task_detail: {
    primary_metric: {},
    secondary_metric: {},
    metric_curve_title: 'Metrics',
    loss_series: [],
    metric_series: [],
  },
});

const cloneProfile = (profile) => ({
  metric_guides: { ...(profile?.metric_guides || {}) },
  training_metric_cards: Array.isArray(profile?.training_metric_cards) ? profile.training_metric_cards.map((item) => ({ ...item })) : [],
  evaluate_metric_cards: Array.isArray(profile?.evaluate_metric_cards) ? profile.evaluate_metric_cards.map((item) => ({ ...item })) : [],
  inference: { ...(profile?.inference || {}) },
  task_detail: {
    ...(profile?.task_detail || {}),
    primary_metric: { ...(profile?.task_detail?.primary_metric || {}) },
    secondary_metric: { ...(profile?.task_detail?.secondary_metric || {}) },
    loss_series: Array.isArray(profile?.task_detail?.loss_series) ? profile.task_detail.loss_series.map((item) => ({ ...item })) : [],
    metric_series: Array.isArray(profile?.task_detail?.metric_series) ? profile.task_detail.metric_series.map((item) => ({ ...item })) : [],
  },
});

export const resolveTrainingResultProfile = (valueOrRecord) => {
  const raw = valueOrRecord?.capabilities_snapshot?.result_profile
    || valueOrRecord?.result_profile
    || valueOrRecord;
  if (raw && typeof raw === 'object') {
    return cloneProfile(raw);
  }
  return cloneProfile(UNSUPPORTED_PROFILE);
};
