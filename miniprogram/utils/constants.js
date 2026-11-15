const GAME_TYPE_TEXT = {
  memory_box: '记东西',
  category_sort: '分分类',
  number_seq: '记数字',
  common_sense: '生活常识',
};
const DIFFICULTY_TEXT = { 1: '轻松一点', 2: '多动动脑', 3: '来点难的' };
const PHRASE_GROUPS = [
  { title: '健康', items: ['我昨晚没睡好', '今天身上不太舒服', '我吃过了', '该怎么吃药'] },
  { title: '家里人', items: ['我孙女快来看我了', '我想我儿子了', '今天孙子给我打电话了', '我老伴以前爱唱戏'] },
  { title: '日常', items: ['今天天气不错', '我下楼走了一圈', '咱们聊会儿'] },
];
const QUICK_PHRASES = ['我吃过了', '今天身上不太舒服', '咱们聊会儿'];

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
