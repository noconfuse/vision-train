/** 类别配色：标注画布与列表缩略图共用同一把尺子，同一个类别在哪儿都是同一个颜色。 */

export const CLASS_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#06b6d4', '#3b82f6', '#6366f1', '#a855f7', '#ec4899',
];

export const getClassColor = (idx) => CLASS_COLORS[Math.abs(Number(idx) || 0) % CLASS_COLORS.length];
