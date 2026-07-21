const UNSUPPORTED_PROFILE = Object.freeze({
    supports_batch_calibration: false,
    environment_hint: '当前任务类型暂未接入训练。',
    empty_calibration_hint: '当前任务类型暂未接入批次校准。',
    history_metric: { key: '', label: '', format: 'plain' },
    default_config: {},
    basic_fields: [],
    advanced_fields: [],
});

const cloneProfile = (profile) => ({
  supports_batch_calibration: !!profile?.supports_batch_calibration,
  environment_hint: profile?.environment_hint || UNSUPPORTED_PROFILE.environment_hint,
  empty_calibration_hint: profile?.empty_calibration_hint || UNSUPPORTED_PROFILE.empty_calibration_hint,
  history_metric: {
    ...(UNSUPPORTED_PROFILE.history_metric),
    ...(profile?.history_metric || {}),
  },
  default_config: { ...(profile?.default_config || {}) },
  basic_fields: Array.isArray(profile?.basic_fields) ? profile.basic_fields.map((item) => ({ ...item })) : [],
  advanced_fields: Array.isArray(profile?.advanced_fields) ? profile.advanced_fields.map((item) => ({ ...item })) : [],
});

export const resolveTrainingConfigProfile = (valueOrRecord) => {
  const raw = valueOrRecord?.capabilities_snapshot?.training_profile
    || valueOrRecord?.training_profile
    || valueOrRecord;
  if (raw && typeof raw === 'object') {
    return cloneProfile(raw);
  }
  return cloneProfile(UNSUPPORTED_PROFILE);
};
