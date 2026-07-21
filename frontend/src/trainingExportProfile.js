const UNSUPPORTED_PROFILE = Object.freeze({
  default_format: 'onnx',
  formats: [],
  engine_hint_supported: '',
  engine_hint_unsupported: '当前任务类型暂未接入导出。',
  half_enabled_text: '',
  half_disabled_text: '当前任务类型暂未接入导出。',
  half_conflict_text: '',
  int8_enabled_text: '',
  int8_disabled_text: '当前任务类型暂未接入导出。',
  int8_conflict_text: '',
});

const cloneProfile = (profile) => ({
  default_format: profile?.default_format || 'onnx',
  formats: Array.isArray(profile?.formats) ? profile.formats.map((item) => ({ ...item })) : [],
  engine_hint_supported: profile?.engine_hint_supported || '',
  engine_hint_unsupported: profile?.engine_hint_unsupported || '',
  half_enabled_text: profile?.half_enabled_text || '',
  half_disabled_text: profile?.half_disabled_text || '',
  half_conflict_text: profile?.half_conflict_text || '',
  int8_enabled_text: profile?.int8_enabled_text || '',
  int8_disabled_text: profile?.int8_disabled_text || '',
  int8_conflict_text: profile?.int8_conflict_text || '',
});

export const resolveTrainingExportProfile = (valueOrRecord) => {
  const raw = valueOrRecord?.capabilities_snapshot?.export_profile
    || valueOrRecord?.export_profile
    || valueOrRecord;
  if (raw && typeof raw === 'object') {
    return cloneProfile(raw);
  }
  return cloneProfile(UNSUPPORTED_PROFILE);
};
