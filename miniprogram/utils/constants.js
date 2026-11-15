const GAME_TYPE_TEXT = {
  memory_box: '记东西',
  category_sort: '分分类',
  number_seq: '记数字',
  common_sense: '生活常识',
};
const DIFFICULTY_TEXT = { 1: '轻松一点', 2: '多动动脑', 3: '来点难的' };
// 短语墙按「话题」分三组，每组 4 条，展开时正好两列两行。
// 每条控制在 8 个汉字以内：两列宽度约 320rpx，40rpx 字号一行放 8 字，
// 超出会折行，两列就对不齐了。
// 选词的三个约束：不碰「药/剂量/病情/诊断/检查结果」（会命中规则闸门，点了只得到转介话术）；
// 不预设亲人已经离世；每组留一句正向的，别把老人框在「不舒服」里。
const PHRASE_GROUPS = [
  { title: '健康', items: ['昨晚没睡好', '身上不太舒服', '这两天有点咳', '精神头好多了'] },
  { title: '家里人', items: ['孙女快来看我了', '想跟孩子说说话', '孩子给我买了新鞋', '一家人吃了顿饭'] },
  { title: '日常', items: ['今天天气不错', '下楼走了一圈', '咱们聊会儿', '在家看看电视'] },
];
// 折叠态最常用的三句，必须都能在上面分组里找到（单测会校验）
const QUICK_PHRASES = ['咱们聊会儿', '身上不太舒服', '今天天气不错'];

// 语速直接透传给后端 /api/tts（后端限定 [-1, 1]，腾讯云：0 为正常语速，负数更慢）。
// 旧版本用的是 0.9 / 1.0 / 1.1，语义正好偏快，这里统一迁到新的默认值。
const SPEAK_SPEEDS = [
  { value: -1.0, label: '很慢' },
  { value: -0.5, label: '慢一点' },
  { value: 0, label: '正常' },
];
const DEFAULT_SPEAK_SPEED = -0.5;
const LEGACY_SPEAK_SPEEDS = [0.9, 1.0, 1.1];

function normalizeSpeakSpeed(raw) {
  if (raw === '' || raw === null || raw === undefined) return DEFAULT_SPEAK_SPEED;
  const value = Number(raw);
  if (isNaN(value)) return DEFAULT_SPEAK_SPEED;
  if (LEGACY_SPEAK_SPEEDS.indexOf(value) >= 0) return DEFAULT_SPEAK_SPEED;
  const hit = SPEAK_SPEEDS.some((item) => item.value === value);
  return hit ? value : DEFAULT_SPEAK_SPEED;
}

module.exports = {
  GAME_TYPE_TEXT,
  DIFFICULTY_TEXT,
  PHRASE_GROUPS,
  QUICK_PHRASES,
  SPEAK_SPEEDS,
  DEFAULT_SPEAK_SPEED,
  normalizeSpeakSpeed,
};
