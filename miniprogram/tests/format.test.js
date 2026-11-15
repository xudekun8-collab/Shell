// 纯函数单测：不依赖 wx / 页面运行时，直接 node --test 跑。
// 覆盖 utils/format.js —— 回复截断、用时文案、日期文案、列表 key。
const test = require('node:test');
const assert = require('node:assert');

const { normalizeReply, formatDuration, dateLabel, listKey } = require('../utils/format.js');

test('normalizeReply：空回复给固定话术', () => {
  assert.equal(normalizeReply(''), '我这儿没听清，您再说一遍');
  assert.equal(normalizeReply('   '), '我这儿没听清，您再说一遍');
  assert.equal(normalizeReply(null), '我这儿没听清，您再说一遍');
});

test('normalizeReply：短句原样返回并去首尾空白', () => {
  assert.equal(normalizeReply('  今天天气不错。 '), '今天天气不错。');
});

test('normalizeReply：超长按句号截断，不在半句上切', () => {
  const sentence = '您今天精神真好。';
  const long = sentence.repeat(40); // 320 字，超过 300 上限
  const out = normalizeReply(long);
  assert.ok(out.length <= 300);
  assert.ok(out.endsWith('。'));
  assert.equal(out.length % sentence.length, 0);
});

test('normalizeReply：整段没有标点时硬截到 300', () => {
  const out = normalizeReply('啊'.repeat(400));
  assert.equal(out.length, 300);
});

test('formatDuration：不足一分钟只报秒', () => {
  assert.equal(formatDuration(0), '0 秒');
  assert.equal(formatDuration(59), '59 秒');
  assert.equal(formatDuration(undefined), '0 秒');
  assert.equal(formatDuration(-5), '0 秒');
});

test('formatDuration：超过一分钟报分加秒', () => {
  assert.equal(formatDuration(60), '1 分 0 秒');
  assert.equal(formatDuration(125), '2 分 5 秒');
  assert.equal(formatDuration(3600), '60 分 0 秒');
});

test('dateLabel：今天与昨天用口语', () => {
  const today = new Date(2026, 10, 15); // 2026-11-15
  assert.equal(dateLabel('2026-11-15', today), '今天');
  assert.equal(dateLabel('2026-11-14', today), '昨天');
});

test('dateLabel：七天内说几天前，更早用月-日', () => {
  const today = new Date(2026, 10, 15);
  assert.equal(dateLabel('2026-11-12', today), '3 天前');
  assert.equal(dateLabel('2026-11-08', today), '11-08'); // 满 7 天就不再口语化
  assert.equal(dateLabel('2026-01-05', today), '1-05');
});

test('dateLabel：空值与异常输入不抛错', () => {
  assert.equal(dateLabel(''), '');
  assert.equal(dateLabel(null), '');
  assert.equal(dateLabel('2026-11'), '2026-11');
});

test('listKey：拼接时间类型与序号，保证列表 key 唯一', () => {
  const key = listKey({ created_at: '2026-11-15 10:00:00', game_type: 'memory_box' }, 2);
  assert.equal(key, '2026-11-15 10:00:00|memory_box|2');
  assert.notEqual(
    listKey({ created_at: '2026-11-15 10:00:00', game_type: 'memory_box' }, 2),
    listKey({ created_at: '2026-11-15 10:00:00', game_type: 'memory_box' }, 3)
  );
  assert.equal(listKey(null, 0), '||0');
});
