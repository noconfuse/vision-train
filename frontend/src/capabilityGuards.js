export const buildCapabilityGuard = ({ visible = true, enabled = true, reason = '' } = {}) => {
  const normalizedVisible = !!visible;
  const normalizedEnabled = normalizedVisible && !!enabled;
  return Object.freeze({
    visible: normalizedVisible,
    enabled: normalizedEnabled,
    reason: normalizedEnabled ? '' : String(reason || '').trim(),
  });
};

export const assertCapabilityGuard = (guard, notify) => {
  if (guard?.enabled) return true;
  const reason = String(guard?.reason || '').trim();
  if (!reason) return false;
  if (typeof notify === 'function') {
    notify(reason);
    return false;
  }
  if (notify?.warn && typeof notify.warn === 'function') {
    notify.warn(reason);
    return false;
  }
  if (notify?.error && typeof notify.error === 'function') {
    notify.error(reason);
  }
  return false;
};
