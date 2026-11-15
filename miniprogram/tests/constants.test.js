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

test('每组都是 4 条，两列正好两行', () => {
  PHRASE_GROUPS.forEach((group) => {
    assert.equal(group.items.length, 4, group.title + ' 不是 4 条');
  });
});

test('短语不超过 8 个汉字，两列不会折行', () => {
  PHRASE_GROUPS.forEach((group) => {
    group.items.forEach((phrase) => {
      assert.ok(phrase.length <= 8, group.title + ' 里「' + phrase + '」超过 8 字，两列会对不齐');
    });
  });
});

test('短语不碰会被规则闸门拦下的词', () => {
  // 命中医疗规则后前端只会拿到固定转介话术，老人点了等于白点
  const forbidden = ['药', '剂量', '停药', '偏方', '病情', '诊断', '检查结果', '化疗', '手术', '血压'];
  const all = PHRASE_GROUPS.reduce((acc, g) => acc.concat(g.items), []);
  all.forEach((phrase) => {
    forbidden.forEach((word) => {
      assert.equal(phrase.indexOf(word), -1, '「' + phrase + '」含「' + word + '」，会触发安全规则');
    });
  });
});

test('短语不预设亲人已经离世', () => {
  // 与后端 ber_2 规则的关键词对齐：「下楼走了一圈」里的「走了」不算，
  // 规则本身也只匹配「老伴走了 / 他走了 / 人走了」这类复合词
  const forbidden = ['去世', '过世', '老伴走了', '他走了', '她走了', '人走了', '走了以后', '葬礼', '墓地', '不在了'];
  const all = PHRASE_GROUPS.reduce((acc, g) => acc.concat(g.items), []);
  all.forEach((phrase) => {
    forbidden.forEach((word) => {
      assert.equal(phrase.indexOf(word), -1, '「' + phrase + '」含「' + word + '」');
    });
  });
});
