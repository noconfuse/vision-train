const UNSUPPORTED_PROFILE = Object.freeze({
    supports_batch_calibration: false,
    history_metric: { key: '', label: '', format: 'plain' },
    default_config: {},
    basic_fields: [],
    advanced_fields: [],
});

const cloneProfile = (profile) => ({
  supports_batch_calibration: !!profile?.supports_batch_calibration,
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
