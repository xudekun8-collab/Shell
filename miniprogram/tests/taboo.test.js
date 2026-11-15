// 忌讳词匹配：家属填的常常是整句（「不要提去世的老伴」），
// 这里锁住「剥噪声词后仍能命中短语墙」的行为，避免改文案时静默失效。
const test = require('node:test');
const assert = require('node:assert');

const { normalizeTaboo, shouldHidePhrase } = require('../utils/taboo.js');

test('剥掉噪声词和的了，只留关键词', () => {
  assert.equal(normalizeTaboo('不要提去世的老伴'), '老伴');
  assert.equal(normalizeTaboo('别提老伴了'), '老伴');
  assert.equal(normalizeTaboo(''), '');
  assert.equal(normalizeTaboo(null), '');
});

test('整句忌讳能命中带同关键词的短语', () => {
  const phrase = '我老伴以前爱唱戏';
  assert.equal(shouldHidePhrase(phrase, ['不要提去世的老伴']), true);
});

test('词直接出现在短语里也算命中', () => {
  assert.equal(shouldHidePhrase('我孙女快来看我了', ['孙女']), true);
});

test('不相关的忌讳不误伤', () => {
  assert.equal(shouldHidePhrase('今天天气不错', ['不要提去世的老伴']), false);
});

test('空忌讳列表一律放行', () => {
  assert.equal(shouldHidePhrase('今天天气不错', []), false);
  assert.equal(shouldHidePhrase('今天天气不错', null), false);
  assert.equal(shouldHidePhrase('今天天气不错', ['', null]), false);
});

test('只有一个字的忌讳不做子串匹配，避免大面积误伤', () => {
  // 单字剥完噪声后长度 < 2，不该拿去做包含判断
  assert.equal(shouldHidePhrase('今天天气不错', ['不']), false);
});
