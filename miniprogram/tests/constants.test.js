// 语速档位归一化：这是真机上最容易「看起来改了其实没改」的地方，
// 旧版本 0.9/1.0/1.1 与腾讯云的语义相反，必须能正确迁移。
const test = require('node:test');
const assert = require('node:assert');

const {
  SPEAK_SPEEDS,
  DEFAULT_SPEAK_SPEED,
  normalizeSpeakSpeed,
  GAME_TYPE_TEXT,
  DIFFICULTY_TEXT,
  QUICK_PHRASES,
  PHRASE_GROUPS,
} = require('../utils/constants.js');

test('默认语速是「慢一点」', () => {
  assert.equal(DEFAULT_SPEAK_SPEED, -0.5);
});

test('缺失与非法值都回落到默认档', () => {
  ['', null, undefined, 'abc', 2, 0.5].forEach((raw) => {
    assert.equal(normalizeSpeakSpeed(raw), DEFAULT_SPEAK_SPEED, '输入：' + raw);
  });
});

test('合法档位原样保留，字符串也能转', () => {
  SPEAK_SPEEDS.forEach((item) => {
    assert.equal(normalizeSpeakSpeed(item.value), item.value);
    assert.equal(normalizeSpeakSpeed(String(item.value)), item.value);
  });
});

test('语速 0 是合法值，不能被当成缺失', () => {
  assert.equal(normalizeSpeakSpeed(0), 0);
  assert.equal(normalizeSpeakSpeed('0'), 0);
});

test('旧版偏快的 0.9/1.0/1.1 一律迁移到默认档', () => {
  [0.9, 1.0, 1.1].forEach((legacy) => {
    assert.equal(normalizeSpeakSpeed(legacy), DEFAULT_SPEAK_SPEED);
  });
});

test('题型与难度文案齐全，记录页不会露出英文 key', () => {
  assert.equal(GAME_TYPE_TEXT.memory_box, '记东西');
  assert.equal(GAME_TYPE_TEXT.category_sort, '分分类');
  assert.equal(GAME_TYPE_TEXT.number_seq, '记数字');
  assert.equal(GAME_TYPE_TEXT.common_sense, '生活常识');
  [1, 2, 3].forEach((level) => {
    assert.ok(DIFFICULTY_TEXT[level], '缺难度文案：' + level);
  });
});

test('快捷话术非空且都在短语墙里有对应分组', () => {
  assert.ok(QUICK_PHRASES.length > 0);
  const all = PHRASE_GROUPS.reduce((acc, g) => acc.concat(g.items), []);
  QUICK_PHRASES.forEach((phrase) => {
    assert.ok(all.indexOf(phrase) >= 0, '快捷话术不在短语墙里：' + phrase);
  });
});
